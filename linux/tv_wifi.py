#!/usr/bin/env python3
"""TV Wi-Fi : bureau X11 en Full HD, sans son, vers un récepteur DLNA."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import http.server
import ipaddress
import json
import os
from pathlib import Path
import secrets
import select
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

PREFS = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'tv-wifi/preferences.json'
MULTICAST = ('239.255.255.250', 1900)
DEVICE_NS = {'d': 'urn:schemas-upnp-org:device-1-0'}
PIPELINE = ['gst-launch-1.0', '-q', 'ximagesrc', 'use-damage=false',
            'show-pointer=true', '!', 'video/x-raw,framerate=30/1', '!',
            'videoscale', '!', 'videoconvert', '!',
            'video/x-raw,width=1920,height=1080,format=NV12', '!',
            'nvcudah264enc', 'preset=p4', 'tune=low-latency', 'bitrate=12000',
            'gop-size=30', '!', 'video/x-h264,profile=baseline', '!',
            'h264parse', 'config-interval=-1', '!', 'mpegtsmux', 'alignment=7',
            '!', 'fdsink', 'fd=1', 'sync=false']


class TVError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise TVError('La TV redirige vers une autre adresse ; connexion refusée.')


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def parse_ip(value):
    try:
        address = ipaddress.IPv4Address(value.strip())
        if not address.is_private or address.is_loopback or address.is_unspecified:
            raise ValueError()
        return str(address)
    except ValueError:
        raise TVError('Saisissez une adresse IP locale, par exemple 192.168.1.100.') from None


def checked_url(url, peer):
    try:
        p = urllib.parse.urlsplit(url)
        ip = ipaddress.IPv4Address(p.hostname)
        if (p.scheme != 'http' or str(ip) != peer or not ip.is_private
                or ip.is_unspecified or p.username or p.password or p.fragment
                or (p.port is not None and not 0 < p.port < 65536)):
            raise ValueError()
    except (ValueError, TypeError):
        raise TVError('Adresse de service incohérente avec la TV sélectionnée.') from None
    return url


def xml_request(request):
    try:
        with OPENER.open(request, timeout=4) as response:
            data = response.read(262145)
        if len(data) > 262144 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
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
        if kind.startswith('urn:schemas-upnp-org:service:AVTransport:'):
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
    if not lines or '200' not in lines[0]:
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


class CastSession:
    def __init__(self, tv, cancel=None):
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

    def start(self):
        if not shutil.which('gst-launch-1.0'):
            raise TVError('GStreamer est absent de ce PC.')
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
                errors = tempfile.TemporaryFile()
                try:
                    with session.lock:
                        if session.cancel.is_set():
                            return
                        process = subprocess.Popen(PIPELINE, stdout=subprocess.PIPE,
                                                   stderr=errors,
                                                   env=dict(os.environ, GST_XINITTHREADS='1'))
                        session.processes.add(process)
                        session.connections.add(self.connection)
                    self.stream_headers()
                    while not session.cancel.is_set():
                        data = process.stdout.read(1316)
                        if not data:
                            break
                        self.wfile.write(data)
                        session.bytes += len(data)
                        session.last_data = time.monotonic()
                except (OSError, ValueError):
                    pass
                finally:
                    if process:
                        terminate(process)
                        process.stdout.close()
                        if not session.cancel.is_set():
                            errors.seek(0)
                            detail = errors.read(1500).decode(errors='replace').strip()
                            session.error = ('La diffusion a été interrompue par la TV.'
                                             if session.bytes else
                                             'Encodage ou réception vidéo impossible. ' + detail)
                        with session.lock:
                            session.processes.discard(process)
                            session.connections.discard(self.connection)
                    errors.close()
                    session.stream_lock.release()

        bind = local_address(self.tv.ip)
        self.server = http.server.ThreadingHTTPServer((bind, 0), Handler)
        self.server.daemon_threads = True
        self.server_thread = threading.Thread(target=self.server.serve_forever,
                                              kwargs={'poll_interval': .1}, daemon=True)
        self.server_thread.start()
        self.uri = f'http://{bind}:{self.server.server_port}{token_path}'
        metadata = ('<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
                    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
                    'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
                    '<item id="1" parentID="0" restricted="1"><dc:title>Écran MSI</dc:title>'
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


def create_application():
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, Gio, GLib

    class Application(Gtk.Application):
        def __init__(self):
            super().__init__(application_id='org.marc.TVWifi', flags=Gio.ApplicationFlags.FLAGS_NONE)
            self.window = None
            self.session = None
            self.cancel = threading.Event()
            self.busy = False
            self.closing = False
            self.updating = False
            self.known = []
            self.searching = False
            self.search_cancel = threading.Event()

        def do_activate(self):
            if self.window:
                self.window.present()
                return
            self.window = Gtk.ApplicationWindow(application=self, title='TV Wi-Fi')
            self.window.set_default_size(530, 350)
            self.window.set_border_width(22)
            self.window.connect('delete-event', self.on_close)
            layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
            self.window.add(layout)
            heading = Gtk.Label(xalign=0)
            heading.set_markup('<big><b>Votre écran sur la TV</b></big>')
            layout.pack_start(heading, False, False, 0)
            layout.pack_start(Gtk.Label(label='Full HD 1080p · 30 images/s · Sans son', xalign=0), False, False, 0)
            row = Gtk.Box(spacing=8)
            self.combo = Gtk.ComboBoxText()
            self.combo.set_hexpand(True)
            self.combo.connect('changed', self.on_selected)
            self.search = Gtk.Button(label='Rechercher les TV')
            self.search.connect('clicked', lambda *_: self.search_tvs())
            row.pack_start(self.combo, True, True, 0)
            row.pack_start(self.search, False, False, 0)
            layout.pack_start(row, False, False, 0)
            self.entry = Gtk.Entry()
            self.entry.set_placeholder_text('Ou saisissez l’adresse IP de la TV')
            self.entry.set_input_purpose(Gtk.InputPurpose.FREE_FORM)
            prefs = load_preferences()
            self.entry.set_text(str(prefs.get('last_ip', '')))
            try:
                remembered = TV(**prefs['last_tv'])
                checked_url(remembered.location, remembered.ip)
                self.known.append(remembered)
            except (KeyError, TypeError, TVError):
                pass
            layout.pack_start(self.entry, False, False, 0)
            connect_row = Gtk.Box(spacing=12)
            self.connection_label = Gtk.Label(label='Diffusion de l’écran', xalign=0)
            self.switch = Gtk.Switch()
            self.switch.set_valign(Gtk.Align.CENTER)
            self.switch.connect('state-set', self.on_switch)
            connect_row.pack_start(self.connection_label, True, True, 0)
            connect_row.pack_end(self.switch, False, False, 0)
            layout.pack_start(connect_row, False, False, 2)
            self.status = Gtk.Label(label='Choisissez la TV de votre salle, puis activez la diffusion.', xalign=0)
            self.status.set_line_wrap(True)
            self.status.set_selectable(True)
            layout.pack_start(self.status, False, False, 0)
            note = Gtk.Label(label='Même réseau que la TV · Plusieurs secondes de décalage possibles.\n'
                             'Tout l’écran est partagé. Fermer cette fenêtre coupe la diffusion.', xalign=0)
            note.set_line_wrap(True)
            note.get_style_context().add_class('dim-label')
            layout.pack_start(note, False, False, 0)
            self.window.show_all()
            GLib.timeout_add_seconds(1, self.monitor)
            self.busy = True
            self.update_controls()

            GLib.idle_add(self.ready)

        def ready(self):
            self.busy = False
            if self.closing:
                self.window.destroy()
                return False
            self.update_controls()
            self.search_tvs()
            return False

        def update_controls(self):
            on = self.session is not None
            self.updating = True
            self.switch.set_state(on)
            self.switch.set_active(on)
            self.updating = False
            self.switch.set_sensitive(not self.busy)
            self.entry.set_sensitive(not on and not self.busy)
            self.combo.set_sensitive(not on and not self.busy)
            self.search.set_sensitive(not self.busy and not self.searching)

        def search_tvs(self):
            if self.busy or self.closing or self.searching:
                return
            self.searching = True
            self.search.set_sensitive(False)
            self.search.set_label('Recherche…')
            def worker():
                try:
                    found, error = discover(cancel=self.search_cancel), None
                except Exception as exc:
                    found, error = [], str(exc)
                GLib.idle_add(self.searched, found, error)
            threading.Thread(target=worker, daemon=True).start()

        def searched(self, found, error):
            if self.closing:
                return False
            self.searching = False
            self.combo.remove_all()
            by_ip = {tv.ip: tv for tv in self.known}
            by_ip.update({tv.ip: tv for tv in found})
            self.known = list(by_ip.values())
            for tv in found:
                self.combo.append(tv.ip, f'{tv.name} — {tv.ip}')
            self.search.set_label('Rechercher les TV')
            self.search.set_sensitive(not self.busy)
            if not self.session and not self.busy:
                self.status.set_text(error or (f'{len(found)} TV disponible(s). Choisissez celle de votre salle.'
                                               if found else 'Aucune TV détectée. Essayez son adresse IP ou relancez la recherche.'))
            return False

        def on_selected(self, combo):
            if not self.session:
                ip = combo.get_active_id()
                if ip:
                    self.entry.set_text(ip)

        def on_switch(self, widget, active):
            if self.updating or self.busy:
                return True
            if active:
                try:
                    ip = parse_ip(self.entry.get_text())
                except TVError as exc:
                    self.status.set_text(str(exc))
                    self.update_controls()
                    return True
                self.cancel = threading.Event()
                self.busy = True
                self.status.set_text('Connexion à ' + ip + '…')
                self.update_controls()
                known = list(self.known)
                def connect():
                    session = None
                    try:
                        tv = resolve_tv(ip, known, self.cancel)
                        session = CastSession(tv, self.cancel)
                        session.start()
                        GLib.idle_add(self.connected, session)
                    except Exception as exc:
                        if session:
                            session.stop()
                        GLib.idle_add(self.failed, str(exc))
                threading.Thread(target=connect, daemon=False).start()
            else:
                self.disconnect()
            return True

        def connected(self, session):
            self.busy = False
            self.session = session
            if self.closing:
                self.disconnect()
                return False
            try:
                save_preferences(session.tv)
            except OSError:
                pass  # Une préférence non sauvegardée ne doit pas couper le cours.
            self.status.set_text('Connecté à ' + session.tv.name + ' — ' + session.tv.ip)
            self.update_controls()
            return False

        def failed(self, message):
            self.busy = False
            self.session = None
            if self.closing:
                self.window.destroy()
            else:
                self.status.set_text(message)
                self.update_controls()
            return False

        def disconnect(self, reason=None):
            self.cancel.set()
            self.busy = True
            self.status.set_text('Déconnexion…')
            self.update_controls()
            session = self.session
            def worker():
                error = None
                try:
                    if session:
                        session.stop()
                except Exception as exc:
                    error = str(exc)
                GLib.idle_add(self.disconnected, reason or error)
            threading.Thread(target=worker, daemon=False).start()

        def disconnected(self, message):
            self.session = None
            self.busy = False
            if self.closing:
                self.window.destroy()
            else:
                self.status.set_text(message or 'Déconnecté. Votre écran n’est plus partagé.')
                self.update_controls()
            return False

        def monitor(self):
            if self.session and not self.busy:
                if self.session.error or time.monotonic() - self.session.last_data > 20:
                    self.disconnect(self.session.error or 'La TV ne reçoit plus la vidéo. Reconnectez-vous.')
            return not self.closing

        def on_close(self, *unused):
            self.closing = True
            self.cancel.set()
            self.search_cancel.set()
            if self.busy:
                self.status.set_text('Arrêt de la diffusion…')
            elif self.session:
                self.disconnect()
            else:
                return False
            return True

    return Application()


def run_gui():
    application = create_application()
    return application.run(None)


if __name__ == '__main__':
    raise SystemExit(run_gui())
