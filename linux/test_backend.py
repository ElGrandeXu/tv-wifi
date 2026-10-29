"""Sélection des capacités et média synthétique, sans capture réelle."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]/'common'))
import dlna
import linux_backend as backend


class BackendTests(unittest.TestCase):
    def test_no_gpu_or_broken_driver_falls_back_to_software(self):
        for plugins, works in [({'x264enc'}, {'x264enc'}),
                               ({'x264enc', 'nvcudah264enc'}, {'x264enc'})]:
            with patch.object(backend, 'has_plugin', side_effect=lambda p: p in plugins), \
                    patch.object(backend, 'encoder_works', side_effect=lambda p: p in works):
                self.assertEqual(backend.choose_encoder(), 'x264enc')

    def test_software_mode_never_touches_nvidia(self):
        with patch.object(backend, 'has_plugin', return_value=True), \
                patch.object(backend, 'encoder_works', return_value=True) as probe:
            self.assertEqual(backend.choose_encoder('software'), 'x264enc')
        self.assertEqual(probe.call_args_list[0].args, ('x264enc',))

    def test_missing_encoders_actionable_error(self):
        with patch.object(backend, 'has_plugin', return_value=False), self.assertRaisesRegex(dlna.TVError, 'ugly'):
            backend.choose_encoder()

    def test_audio_uses_real_monitor_mapping_never_default_input(self):
        sinks = [{'index': 5, 'name': 'output', 'monitor_source': 'output.monitor'}]
        sources = [{'name': 'input', 'monitor_source': ''},
                   {'name': 'output.monitor', 'monitor_source': 'output'}]
        outputs = ['output\n', json.dumps(sinks), json.dumps(sources)]
        with patch.object(backend.subprocess, 'check_output', side_effect=outputs):
            self.assertEqual(backend.monitor_source(), 'output.monitor')
        sources[1]['monitor_source'] = ''
        with patch.object(backend.subprocess, 'check_output', side_effect=[
                'output\n', json.dumps(sinks), json.dumps(sources)]), self.assertRaisesRegex(dlna.TVError, 'micro'):
            backend.monitor_source()

    def test_wayland_passes_portal_fd_and_serial_and_closes_on_preparation_error(self):
        from unittest.mock import MagicMock
        import portal
        fake = MagicMock(fd=19, node=42, serial=9876)
        with patch.dict(os.environ, XDG_SESSION_TYPE='wayland'), \
                patch.object(backend, 'choose_encoder', return_value='x264enc'), \
                patch.object(backend, 'has_plugin', return_value=True), \
                patch.object(portal, 'ScreenCastPortal', return_value=fake):
            capture = backend.prepare_capture(threading.Event())
            self.assertIn('fd=19', capture.command)
            self.assertIn('target-object=9876', capture.command)
            self.assertEqual(capture.pass_fds, (19,))
            capture.close()
            fake.close.assert_called_once()
            fake.close.reset_mock()
            with self.assertRaises(dlna.TVError):
                backend.prepare_capture(threading.Event(), profile='invalid')
            fake.close.assert_called_once()

    def test_default_capture_has_no_audio_and_preserves_aspect_ratio(self):
        command = backend.build_pipeline(['videotestsrc'], 'x264enc')
        self.assertNotIn('pulsesrc', command)
        self.assertIn('add-borders=true', command)
        with self.assertRaises(dlna.TVError):
            backend.build_pipeline(['videotestsrc'], 'x264enc', audio='default ! filesink')

    def test_x11_preparation_without_audio_does_not_request_monitor(self):
        with patch.dict(os.environ, XDG_SESSION_TYPE='x11', DISPLAY=':test'), \
                patch.object(backend, 'choose_encoder', return_value='x264enc'), \
                patch.object(backend, 'has_plugin', return_value=True), \
                patch.object(backend, 'monitor_source') as monitor:
            capture = backend.prepare_capture(threading.Event())
            self.assertIn('ximagesrc', capture.command)
            self.assertEqual(capture.pass_fds, ())
            self.assertFalse(monitor.called)
            capture.close()

    def test_cancelled_preparation_has_no_effect(self):
        event = threading.Event()
        event.set()
        with patch.object(backend, 'choose_encoder') as choose, self.assertRaises(dlna.TVError):
            backend.prepare_capture(event)
        self.assertFalse(choose.called)


@unittest.skipUnless(sys.platform == 'linux' and backend.has_plugin('x264enc')
                     and backend.has_plugin('avenc_aac'), 'Modules GStreamer de test absents')
class MediaTests(unittest.TestCase):
    def test_real_h264_and_aac_mux_with_synthetic_sources(self):
        command = backend.build_pipeline(
            ['videotestsrc', 'num-buffers=30', '!', 'video/x-raw,width=640,height=480,framerate=30/1'],
            'x264enc', '720p', 'test.monitor')
        index = command.index('pulsesrc')
        command[index:index+3] = ['audiotestsrc', 'num-buffers=47', 'samplesperbuffer=1024']
        with tempfile.TemporaryDirectory() as folder:
            media = Path(folder)/'test.ts'
            i = command.index('fdsink')
            command[i:i+2] = ['filesink', 'location='+str(media)]
            result = subprocess.run(command, capture_output=True, timeout=25)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
            import gi
            gi.require_version('Gst', '1.0')
            gi.require_version('GstPbutils', '1.0')
            from gi.repository import Gst, GstPbutils
            Gst.init(None)
            info = GstPbutils.Discoverer.new(10 * Gst.SECOND).discover_uri(media.as_uri())
            videos, audios = info.get_video_streams(), info.get_audio_streams()
            self.assertEqual(len(videos), 1)
            self.assertEqual((videos[0].get_width(), videos[0].get_height()), (1280, 720))
            self.assertEqual(len(audios), 1)
            self.assertIn('video/x-h264', videos[0].get_caps().to_string())
            self.assertIn('audio/mpeg', audios[0].get_caps().to_string())
