#!/usr/bin/env python3
"""Découverte, commandes DLNA et serveur éphémère, partagés par Linux et macOS."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import http.server
import ipaddress
import json
import os
from pathlib import Path
import secrets
import select
import socket
import subprocess
import tempfile
import re
from collections import deque
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

import sys

PREFS = (Path.home() / 'Library/Application Support/TV Wi-Fi/preferences.json'
         if sys.platform == 'darwin' else
         Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'tv-wifi/preferences.json')
MULTICAST = ('239.255.255.250', 1900)
DEVICE_NS = {'d': 'urn:schemas-upnp-org:device-1-0'}


class TVError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise TVError('La TV redirige vers une autre adresse ; connexion refusée.')


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def parse_ip(value):
    try:
        address = ipaddress.IPv4Address(value.strip())
        networks = ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16')
        if not any(address in ipaddress.IPv4Network(n) for n in networks):
            raise ValueError()
        return str(address)
    except (ValueError, AttributeError):
        raise TVError('Saisissez une adresse IP locale, par exemple 192.168.1.100.') from None


def checked_url(url, peer):
    try:
        peer = parse_ip(peer)
        if not isinstance(url, str) or any(ord(c) < 33 or ord(c) == 127 for c in url):
            raise ValueError()
        p = urllib.parse.urlsplit(url)
        ip = ipaddress.IPv4Address(p.hostname)
        if (p.scheme != 'http' or str(ip) != peer or not ip.is_private
                or ip.is_unspecified or p.username is not None or p.password is not None or p.fragment
                or (p.port is not None and not 0 < p.port < 65536)):
            raise ValueError()
    except (ValueError, TypeError):
        raise TVError('Adresse de service incohérente avec la TV sélectionnée.') from None
    return url


def xml_request(request):
    try:
        with OPENER.open(request, timeout=4) as response:
            data = response.read(262145)
        # NUL interdit aussi les encodages UTF-16/32 qui masqueraient une DTD.
        if (len(data) > 262144 or b'\x00' in data or b'<!DOCTYPE' in data.upper()
                or b'<!ENTITY' in data.upper()):
            raise TVError('Réponse de la TV invalide ou trop volumineuse.')
        return ET.fromstring(data)
    except urllib.error.HTTPError as error:
        raise TVError(f'La TV refuse la commande (HTTP {error.code}).') from None
    except (OSError, ET.ParseError) as error:
        raise TVError(f'La TV ne répond pas correctement : {error}.') from None


@dataclass(frozen=True)
class TV:
    name: str
    ip: str
    location: str
    control: str
    service: str


def describe(location, peer):
    checked_url(location, peer)
    root = xml_request(location)
    for service in root.findall('.//d:service', DEVICE_NS):
        kind = service.findtext('d:serviceType', namespaces=DEVICE_NS) or ''
        if re.fullmatch(r'urn:schemas-upnp-org:service:AVTransport:[1-9]\d{0,2}', kind):
            control = service.findtext('d:controlURL', namespaces=DEVICE_NS)
            if not control:
                continue
            base = root.findtext('d:URLBase', namespaces=DEVICE_NS) or location
            checked_url(base, peer)
            control = checked_url(urllib.parse.urljoin(base, control), peer)
            name = root.findtext('.//d:friendlyName', namespaces=DEVICE_NS) or 'TV'
            return TV(name[:100], peer, location, control, kind)
    raise TVError('Cette TV ne propose pas de réception vidéo DLNA.')


def soap(tv, action, values):
    checked_url(tv.control, tv.ip)
    if not re.fullmatch(r'urn:schemas-upnp-org:service:AVTransport:[1-9]\d{0,2}', tv.service):
        raise TVError('Type de service DLNA invalide.')
    fields = ''.join(f'<{k}>{escape(str(v))}</{k}>' for k, v in values.items())
    body = ('<?xml version="1.0"?><s:Envelope '
            'xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
            f'<s:Body><u:{action} xmlns:u="{tv.service}">{fields}'
            f'</u:{action}></s:Body></s:Envelope>').encode()
    req = urllib.request.Request(tv.control, data=body, headers={
        'Content-Type': 'text/xml; charset="utf-8"',
        'SOAPAction': f'"{tv.service}#{action}"'})
    result = xml_request(req)
    if any(e.tag.split('}')[-1] == 'Fault' for e in result.iter()):
        raise TVError('La TV a signalé une erreur DLNA (SOAP Fault).')
    return {e.tag.split('}')[-1]: e.text for e in result.iter() if len(e) == 0}


def interfaces():
    try:
        p = subprocess.run(['ip', '-j', '-4', 'addr', 'show', 'up'],
                           capture_output=True, text=True, timeout=3, check=True)
        return [a['local'] for dev in json.loads(p.stdout)
                for a in dev.get('addr_info', []) if a.get('scope') == 'global'
                and ipaddress.IPv4Address(a['local']).is_private]
    except (OSError, ValueError, subprocess.SubprocessError):
        return ['0.0.0.0']


def ssdp_location(data, peer):
    lines = data.decode('utf-8', errors='replace').splitlines()
    if not lines or not re.fullmatch(r'HTTP/1\.[01] 200(?: .*)?', lines[0]):
        return None
    headers = {k.strip().lower(): v.strip() for line in lines[1:] if ':' in line
               for k, v in [line.split(':', 1)]}
    location = headers.get('location')
    if location:
        try:
            return checked_url(location, peer)
        except TVError:
            pass
    return None


def discover(target=None, cancel=None, duration=4):
    cancel = cancel or threading.Event()
    sockets, locations = [], set()
    packet = (b'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\n'
              b'MAN: "ssdp:discover"\r\nMX: 2\r\n'
              b'ST: urn:schemas-upnp-org:device:MediaRenderer:1\r\n\r\n')
    try:
        for address in interfaces():
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.bind((address, 0))
                s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
                if address != '0.0.0.0':
                    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF,
                                 socket.inet_aton(address))
                s.sendto(packet, MULTICAST)
                if target:
                    s.sendto(packet, (target, 1900))
                sockets.append(s)
            except OSError:
                s.close()
        end = time.monotonic() + duration
        while sockets and time.monotonic() < end and not cancel.is_set():
            ready, _, _ = select.select(sockets, [], [], min(.2, max(0, end-time.monotonic())))
            for s in ready:
                data, (peer, _) = s.recvfrom(16384)
                if target and peer != target:
                    continue
                location = ssdp_location(data, peer)
                if location and len(locations) < 64:
                    locations.add((location, peer))
    finally:
        for s in sockets:
            s.close()

    def inspect(pair):
        if cancel.is_set():
            return None
        try:
            return describe(*pair)
        except TVError:
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        found = [tv for tv in pool.map(inspect, locations) if tv]
    return sorted({tv.ip: tv for tv in found}.values(), key=lambda tv: (tv.name, tv.ip))


def resolve_tv(ip, known, cancel):
    if cancel.is_set():
        raise TVError('Connexion annulée.')
    for tv in known:
        if tv.ip == ip:
            try:
                return describe(tv.location, ip)
            except TVError:
                break
    if cancel.is_set():
        raise TVError('Connexion annulée.')
    found = discover(ip, cancel)
    if not found:
        raise TVError('TV introuvable à cette adresse. Vérifiez le Wi-Fi de la TV '
                      'et son mode de réception vidéo / DLNA, puis réessayez.')
    return found[0]


def local_address(target):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((target, 1900))
        return s.getsockname()[0]


class StreamServer(http.server.ThreadingHTTPServer):
    """Borne les clients lents avant même la lecture de leurs en-têtes."""
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, *args):
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(*args)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


class CastSession:
    def __init__(self, tv, cancel=None, command=None, pass_fds=(), cleanup=None):
        self.tv = tv
        self.cancel = cancel or threading.Event()
        self.bytes = 0
        self.last_data = time.monotonic()
        self.error = None
        self.uri = None
        self.server = None
        self.processes, self.connections = set(), set()
        self.lock = threading.Lock()
        self.cleanup_lock = threading.Lock()
        self.stream_lock = threading.Lock()
        self.closed = False
        self.command = command
        self.pass_fds = pass_fds
        self.cleanup = cleanup

    def start(self):
        try:
            self._start()
        except BaseException:
            self.stop()
            raise

    def _start(self):
        if not self.command:
            raise TVError('La commande de capture est absente.')
        if self.cancel.is_set():
            raise TVError('Connexion annulée.')
        session = self
        token_path = '/' + secrets.token_urlsafe(24) + '/desktop.ts'

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def valid(self):
                self.connection.settimeout(5)
                if (self.client_address[0] != session.tv.ip or self.path != token_path
                        or session.cancel.is_set()):
                    self.send_error(403)
                    return False
                return True

            def stream_headers(self):
                self.send_response(200)
                self.send_header('Content-Type', 'video/mpeg')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Connection', 'close')
                self.send_header('transferMode.dlna.org', 'Streaming')
                self.end_headers()

            def do_HEAD(self):
                if self.valid():
                    self.stream_headers()

            def do_GET(self):
                if not self.valid():
                    return
                if not session.stream_lock.acquire(blocking=False):
                    self.send_error(503)
                    return
                process = None
                errors = deque(maxlen=8)
                error_thread = None
                try:
                    with session.lock:
                        if session.cancel.is_set():
                            return
                        process = subprocess.Popen(session.command, stdout=subprocess.PIPE,
                                                   stderr=subprocess.PIPE, pass_fds=session.pass_fds,
                                                   env=dict(os.environ, GST_XINITTHREADS='1'))
                        session.processes.add(process)
                        session.connections.add(self.connection)
                    def drain_errors():
                        while True:
                            chunk = process.stderr.read(512)
                            if not chunk:
                                break
                            errors.append(chunk)
                    error_thread = threading.Thread(target=drain_errors, daemon=True)
                    error_thread.start()
                    self.stream_headers()
                    while not session.cancel.is_set():
                        data = process.stdout.read(1316)
                        if not data:
                            break
                        self.wfile.write(data)
                        session.bytes += len(data)
                        session.last_data = time.monotonic()
                except (OSError, ValueError) as error:
                    if not session.cancel.is_set():
                        session.error = 'La diffusion est impossible : ' + str(error)
                finally:
                    if process:
                        terminate(process)
                        process.stdout.close()
                        error_thread.join(timeout=2)
                        process.stderr.close()
                        if not session.cancel.is_set():
                            detail = b''.join(errors)[-1500:].decode(errors='replace').strip()
                            session.error = ('La diffusion a été interrompue par la TV.'
                                             if session.bytes else
                                             'Encodage ou réception vidéo impossible. ' + detail)
                        with session.lock:
                            session.processes.discard(process)
                            session.connections.discard(self.connection)
                    session.stream_lock.release()

        bind = local_address(self.tv.ip)
        self.server = StreamServer((bind, 0), Handler)
        self.server.daemon_threads = True
        self.server_thread = threading.Thread(target=self.server.serve_forever,
                                              kwargs={'poll_interval': .1}, daemon=True)
        self.server_thread.start()
        self.uri = f'http://{bind}:{self.server.server_port}{token_path}'
        metadata = ('<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
                    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
                    'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
                    '<item id="1" parentID="0" restricted="1"><dc:title>TV Wi-Fi</dc:title>'
                    '<upnp:class>object.item.videoItem</upnp:class>'
                    f'<res protocolInfo="http-get:*:video/mpeg:*">{escape(self.uri)}</res>'
                    '</item></DIDL-Lite>')
        if self.cancel.is_set():
            raise TVError('Connexion annulée.')
        soap(self.tv, 'SetAVTransportURI', {'InstanceID': 0, 'CurrentURI': self.uri,
                                           'CurrentURIMetaData': metadata})
        if self.cancel.is_set():
            raise TVError('Connexion annulée.')
        soap(self.tv, 'Play', {'InstanceID': 0, 'Speed': 1})
        deadline = time.monotonic() + 30
        while not self.bytes:
            if self.cancel.wait(.1):
                raise TVError('Connexion annulée.')
            if self.error:
                raise TVError(self.error)
            if time.monotonic() > deadline:
                raise TVError('La TV accepte la commande mais ne reçoit pas la vidéo.')

    def stop(self):
        # Arrêter la capture avant tout appel réseau, même si la TV ne répond plus.
        self.cancel.set()
        with self.cleanup_lock:
            if self.closed:
                return
            self.closed = True
            with self.lock:
                processes, connections = list(self.processes), list(self.connections)
            for connection in connections:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            for process in processes:
                terminate(process)
            if self.server:
                self.server.shutdown()
                self.server.server_close()
                self.server_thread.join(timeout=2)
            if self.cleanup:
                self.cleanup()
            if self.uri:
                try:
                    current = soap(self.tv, 'GetMediaInfo', {'InstanceID': 0})
                    # Une autre personne peut avoir repris la TV depuis notre connexion.
                    if current.get('CurrentURI') == self.uri:
                        soap(self.tv, 'Stop', {'InstanceID': 0})
                except TVError:
                    pass


def terminate(process):
    if process.poll() is None:
        try:
            process.terminate()
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


def load_preferences():
    try:
        value = json.loads(PREFS.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_preferences(tv):
    PREFS.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    data = json.dumps({'last_ip': tv.ip, 'last_tv': tv.__dict__}, ensure_ascii=False)
    fd, name = tempfile.mkstemp(dir=PREFS.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(data)
        os.replace(name, PREFS)
    finally:
        if os.path.exists(name):
            os.unlink(name)
