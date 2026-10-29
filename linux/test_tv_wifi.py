"""Essais locaux : aucune TV réelle et aucune capture du bureau."""
import http.client
import http.server
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).parents[1]/'common'))
import dlna as app
REAL_PARSE_IP = app.parse_ip


class Receiver:
    def __init__(self, reject_play=False):
        self.uri = ''
        self.actions = []
        self.read_bytes = 0
        self.reject_play = reject_play
        self.stop_reading = threading.Event()
        self.client = None
        receiver = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                body = ('<root xmlns="urn:schemas-upnp-org:device-1-0"><device>'
                        '<friendlyName>Salle de test</friendlyName><serviceList><service>'
                        '<serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType>'
                        '<controlURL>/control</controlURL></service></serviceList></device></root>').encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                root = ET.fromstring(body)
                fields = {e.tag.split('}')[-1]: e.text for e in root.iter() if len(e) == 0}
                action = self.headers['SOAPAction'].strip('"').split('#')[-1]
                receiver.actions.append(action)
                if action == 'Play' and receiver.reject_play:
                    self.send_error(500)
                    return
                if action == 'SetAVTransportURI':
                    receiver.uri = fields['CurrentURI']
                    # Vérifie l'échappement XML à travers les deux couches de métadonnées.
                    ET.fromstring(fields['CurrentURIMetaData'])
                if action == 'Play':
                    receiver.client = threading.Thread(target=receiver.read_stream, daemon=True)
                    receiver.client.start()
                extra = '<CurrentURI>' + app.escape(receiver.uri) + '</CurrentURI>' if action == 'GetMediaInfo' else ''
                data = ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
                        f'<s:Body><Response>{extra}</Response></s:Body></s:Envelope>').encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.location = f'http://127.0.0.1:{self.server.server_port}/description'

    def read_stream(self):
        try:
            with urllib.request.urlopen(self.uri, timeout=4) as response:
                while not self.stop_reading.is_set():
                    data = response.read(1316)
                    if not data:
                        break
                    self.read_bytes += len(data)
        except OSError:
            pass

    def close(self):
        self.stop_reading.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        if self.client:
            self.client.join(timeout=2)


FAKE_ENCODER = [sys.executable, '-u', '-c',
                'import os,time\nwhile True:\n os.write(1,b"x"*1316)\n time.sleep(.01)']


class Tests(unittest.TestCase):
    def setUp(self):
        self.ip_patch = patch.object(app, 'parse_ip', side_effect=lambda v: v if v == '127.0.0.1' else REAL_PARSE_IP(v))
        self.ip_patch.start()
        self.addCleanup(self.ip_patch.stop)
        self.receiver = Receiver()
        self.tv = app.describe(self.receiver.location, '127.0.0.1')

    def tearDown(self):
        self.receiver.close()

    def test_discovery_and_manual_ip_resolve_dynamic_service(self):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.bind(('127.0.0.1', 0))
        udp.settimeout(2)
        def answer():
            try:
                for _ in range(2):
                    _, peer = udp.recvfrom(4096)
                    data = ('HTTP/1.1 200 OK\r\nLOCATION: ' + self.receiver.location + '\r\n\r\n').encode()
                    udp.sendto(data, peer)
            except OSError:
                pass
        worker = threading.Thread(target=answer, daemon=True)
        worker.start()
        try:
            with patch.object(app, 'interfaces', return_value=['127.0.0.1']), \
                    patch.object(app, 'MULTICAST', udp.getsockname()):
                found = app.discover(duration=.2)
                self.assertEqual(found, [self.tv])
                # Une saisie IP garde la découverte des ports dynamiques, sans scan.
                original = app.discover
                with patch.object(app, 'discover', side_effect=lambda ip, cancel: original(ip, cancel, .2)):
                    self.assertEqual(app.resolve_tv('127.0.0.1', [], threading.Event()), self.tv)
        finally:
            udp.close()
            worker.join(timeout=2)

    def test_stream_receives_and_disconnect_releases_capture_and_server(self):
        session = app.CastSession(self.tv, command=FAKE_ENCODER)
        try:
            session.start()
            processes = list(session.processes)
            self.assertTrue(session.bytes > 0)
            p = urllib.parse.urlsplit(session.uri)
            # Même la bonne TV ne peut pas lire un autre chemin.
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(f'http://{p.netloc}/wrong', timeout=2)
            self.assertEqual(caught.exception.code, 403)
            session.stop()
            session.stop()  # Idempotence : pas de deuxième Stop distant.
            self.assertTrue(all(process.poll() is not None for process in processes))
            self.assertEqual(self.receiver.actions.count('Stop'), 1)
            with self.assertRaises(OSError):
                socket.create_connection((p.hostname, p.port), timeout=.2)
        finally:
            session.stop()


    @unittest.skipIf(sys.platform == 'darwin', 'Adresse loopback secondaire absente sur Mac sans configuration root')
    def test_other_peer_cannot_read_even_with_the_correct_token(self):
        session = app.CastSession(self.tv, command=FAKE_ENCODER)
        try:
            session.start()
            p = urllib.parse.urlsplit(session.uri)
            conn = http.client.HTTPConnection(p.hostname, p.port, timeout=2,
                                              source_address=('127.0.0.2', 0))
            conn.request('HEAD', p.path)
            self.assertEqual(conn.getresponse().status, 403)
            conn.close()
        finally:
            session.stop()

    def test_capture_spawn_error_is_reported_and_fully_cleaned(self):
        session = app.CastSession(self.tv, command=['/nonexistent-tv-wifi-encoder'])
        with self.assertRaises(app.TVError):
            session.start()
        self.assertTrue(session.closed)
        self.assertFalse(session.processes)
        parsed = urllib.parse.urlsplit(session.uri)
        with self.assertRaises(OSError):
            socket.create_connection((parsed.hostname, parsed.port), timeout=.2)

    def test_disconnect_does_not_stop_someone_elses_content(self):
        session = app.CastSession(self.tv, command=FAKE_ENCODER)
        try:
            session.start()
            self.receiver.uri = 'http://another-computer/lecture.mp4'
            session.stop()
            self.assertNotIn('Stop', self.receiver.actions)
        finally:
            session.stop()

    def test_rejected_play_is_cleaned_up(self):
        self.receiver.reject_play = True
        session = app.CastSession(self.tv, command=FAKE_ENCODER)
        try:
            with self.assertRaisesRegex(app.TVError, 'HTTP 500'):
                session.start()
        finally:
            session.stop()
        self.assertFalse(session.processes)
        self.assertTrue(session.closed)

    def test_cancelled_connection_does_not_send_commands(self):
        cancel = threading.Event()
        cancel.set()
        session = app.CastSession(self.tv, cancel, FAKE_ENCODER)
        try:
            with self.assertRaisesRegex(app.TVError, 'annulée'):
                session.start()
        finally:
            session.stop()
        self.assertEqual(self.receiver.actions, [])

    def test_no_cross_host_descriptions_or_credentials(self):
        bad = [self.receiver.location.replace('127.0.0.1', '127.0.0.2'),
               'http://user:password@127.0.0.1:80/', 'http://example.com/',
               'file:///etc/passwd', 'http://127.0.0.1:99999/']
        for url in bad:
            with self.subTest(url=url), self.assertRaises(app.TVError):
                app.checked_url(url, '127.0.0.1')
        packet = b'HTTP/1.1 200 OK\r\nLocation: http://127.0.0.2/a\r\n\r\n'
        self.assertIsNone(app.ssdp_location(packet, '127.0.0.1'))

    def test_preferences_private_and_corrupt_file_preserved_on_read(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'PREFS', Path(folder)/'state/prefs.json'):
            app.save_preferences(self.tv)
            self.assertEqual(app.load_preferences()['last_ip'], self.tv.ip)
            self.assertEqual(app.PREFS.stat().st_mode & 0o777, 0o600)
            app.PREFS.write_text('{invalide')
            self.assertEqual(app.load_preferences(), {})
            self.assertEqual(app.PREFS.read_text(), '{invalide')

    def test_invalid_manual_ip_rejected_before_network(self):
        self.assertEqual(REAL_PARSE_IP(' 192.168.1.100 '), '192.168.1.100')
        for value in ['example.com', '8.8.8.8', '127.0.0.1', '0.0.0.0', '192.168.1.999']:
            with self.subTest(ip=value), self.assertRaises(app.TVError):
                REAL_PARSE_IP(value)



if __name__ == '__main__':
    unittest.main(verbosity=2)
