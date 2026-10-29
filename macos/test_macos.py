"""Tests de portage sans écran Mac ni commande à une TV réelle."""
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).parents[1]/'common'))
import dlna
import mac_backend as backend
import build

# Rejouer les essais réseau contre le moteur livré dans l'archive, pas celui du MSI.
original = Path(__file__).parents[1]/'linux/test_tv_wifi.py'
spec = importlib.util.spec_from_file_location('protocol_suite', original)
protocol = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'tv_wifi': dlna}):
    spec.loader.exec_module(protocol)


class ProtocolMacTests(protocol.Tests):
    test_existing_stream_can_be_stopped_when_tv_is_offline = None  # Reprise /proc propre au MSI.



class FakeSession:
    created = []

    def __init__(self, tv, cancel, command):
        self.tv, self.cancel, self.command = tv, cancel, command
        self.bytes = 0
        self.last_data = time.monotonic()
        self.closed = False
        self.error = None
        self.created.append(self)

    def start(self):
        if self.cancel.is_set():
            raise dlna.TVError('Connexion annulée.')
        self.bytes = 1316

    def stop(self):
        self.closed = True


class MacTests(unittest.TestCase):
    def test_screen_parser_excludes_camera_and_microphone(self):
        log = '''[AVFoundation indev] AVFoundation video devices:
[AVFoundation indev] [0] FaceTime HD Camera
[AVFoundation indev] [1] Camera USB
[AVFoundation indev] [2] Capture screen 0
[AVFoundation indev] [3] Capture screen 1
[AVFoundation indev] AVFoundation audio devices:
[AVFoundation indev] [0] Microphone du Mac
'''
        self.assertEqual(backend.parse_screens(log), [('Capture screen 0', 'Écran 1'),
                                                    ('Capture screen 1', 'Écran 2')])
        self.assertEqual(backend.parse_screens(''), [])

    def test_capture_is_full_hd_hardware_video_without_audio(self):
        with patch.object(backend, 'find_ffmpeg', return_value='/fake path/ffmpeg'):
            command = backend.capture_command('Capture screen 1')
        self.assertEqual(command[0], '/fake path/ffmpeg')
        self.assertEqual(command[command.index('-i')+1], 'Capture screen 1:none')
        self.assertIn('-an', command)
        self.assertEqual(command[command.index('-framerate')+1], '30')
        self.assertEqual(command[command.index('-c:v')+1], 'h264_videotoolbox')
        self.assertIn('1920:1080', command[command.index('-vf')+1])
        self.assertEqual(command[-1], 'pipe:1')
        for invalid in ['default', 'FaceTime HD Camera', '0', 'Capture screen -1', 'Capture screen 1:0']:
            with self.assertRaises(dlna.TVError):
                backend.capture_command(invalid)


    def test_audio_parser_excludes_all_microphones_and_unknown_loopbacks(self):
        log = """AVFoundation video devices:
[AVFoundation indev] [0] BlackHole 2ch
AVFoundation audio devices:
[AVFoundation indev] [0] MacBook Pro Microphone
[AVFoundation indev] [1] BlackHole 2ch
[AVFoundation indev] [2] BlackHole 16ch
[AVFoundation indev] [3] BlackHole microphone
"""
        self.assertEqual(backend.parse_loopbacks(log), ['BlackHole 2ch', 'BlackHole 16ch'])
        with patch.object(backend, 'find_ffmpeg', return_value='/ffmpeg'), \
                patch.object(backend, 'list_audio', return_value=['BlackHole 2ch']):
            command = backend.capture_command('Capture screen 0', 'BlackHole 2ch', '720p')
            self.assertIn('Capture screen 0:BlackHole 2ch', command)
            self.assertIn('aac', command)
            self.assertNotIn('-an', command)
            self.assertIn('1280:720', command[command.index('-vf')+1])
            for device in ['default', 'Built-in Microphone', 'BlackHole 2ch:0', 'BlackHole 16ch']:
                with self.assertRaises(dlna.TVError):
                    backend.capture_command('Capture screen 0', device)

    def test_mac_network_interfaces_not_linux_ip_command(self):
        result = subprocess.CompletedProcess([], 0, stdout='''lo0: flags
 inet 127.0.0.1 netmask 0xff000000
en0: flags
 inet 10.1.2.3 netmask 0xffffff00 broadcast 10.1.2.255
en1: flags
 inet 192.168.1.20 netmask 0xffffff00 broadcast 192.168.1.255
''')
        with patch.object(backend.subprocess, 'run', return_value=result) as run:
            self.assertEqual(backend.network_interfaces(), ['10.1.2.3', '192.168.1.20'])
            self.assertEqual(run.call_args.args[0], ['/sbin/ifconfig', '-a'])

    def test_ffmpeg_paths_include_both_mac_architectures(self):
        for executable in ['/opt/homebrew/opt/ffmpeg@7/bin/ffmpeg', '/usr/local/opt/ffmpeg@7/bin/ffmpeg']:
            with patch.object(backend.shutil, 'which', return_value=None), \
                    patch.object(backend.os.path, 'isfile', side_effect=lambda p: p == executable), \
                    patch.object(backend.os, 'access', return_value=True):
                self.assertEqual(backend.find_ffmpeg(), executable)

    def test_controller_can_disconnect_and_connect_again(self):
        tv = dlna.TV('Salle', '10.1.2.3', '', '', '')
        controller = backend.Controller()
        with patch.object(dlna, 'CastSession', FakeSession), patch.object(dlna, 'resolve_tv', return_value=tv), \
                patch.object(dlna, 'save_preferences'), patch.object(backend, 'capture_command', return_value=['fake']):
            for _ in range(2):
                controller.connect(tv.ip, 'Capture screen 0', [])
                controller.worker.join(timeout=2)
                self.assertEqual(controller.state, 'connected')
                session = controller.session
                controller.disconnect()
                controller.worker.join(timeout=2)
                self.assertEqual(controller.state, 'idle')
                self.assertTrue(session.closed)
                self.assertIsNone(controller.session)

    def test_close_during_resolution_cannot_start_capture_later(self):
        tv = dlna.TV('Salle', '10.1.2.3', '', '', '')
        entered, release = threading.Event(), threading.Event()
        def resolving(*args):
            entered.set()
            release.wait(2)
            return tv
        controller = backend.Controller()
        FakeSession.created = []
        with patch.object(dlna, 'CastSession', FakeSession), patch.object(dlna, 'resolve_tv', side_effect=resolving), \
                patch.object(backend, 'capture_command', return_value=['fake']):
            controller.connect(tv.ip, 'Capture screen 0', [])
            self.assertTrue(entered.wait(1))
            controller.disconnect()
            release.set()
            controller.worker.join(timeout=2)
        self.assertEqual(controller.state, 'idle')
        self.assertIsNone(controller.session)
        self.assertTrue(all(s.closed and s.bytes == 0 for s in FakeSession.created))

    def test_native_permission_is_never_bypassed_on_linux(self):
        with patch.object(backend.sys, 'platform', 'linux'), self.assertRaises(dlna.TVError):
            backend.request_screen_permission()

    def test_mac_bundle_manifest_modes_and_no_msi_dependency(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = build.build(Path(folder)/'TV-WiFi-macOS.zip')
            with zipfile.ZipFile(archive) as z:
                self.assertIsNone(z.testzip())
                root = 'TV Wi-Fi macOS/'
                info = plistlib.loads(z.read(root+'TV Wi-Fi.app/Contents/Info.plist'))
                self.assertEqual(info['CFBundleExecutable'], 'tv-wifi')
                self.assertIn('NSLocalNetworkUsageDescription', info)
                manifest = json.loads(z.read(root+'SHA256.json'))
                for name, digest in manifest.items():
                    data = z.read(root+name)
                    self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
                    if name.endswith('.py'):
                        compile(data, name, 'exec')
                        self.assertNotIn(b'/home/', data)
                        self.assertNotIn(b'gi.repository', data)
                for name in ['TV Wi-Fi.app/Contents/MacOS/tv-wifi', 'Installer les prérequis.command',
                             'Lancer TV Wi-Fi.command']:
                    entry = z.getinfo(root+name)
                    self.assertTrue((entry.external_attr >> 16) & 0o111)
                    script = Path(folder)/'check.sh'
                    script.write_bytes(z.read(entry))
                    subprocess.run(['bash', '-n', str(script)], check=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
