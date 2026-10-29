"""Cohérence du manifeste, des versions et des paquets réellement construits."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build_release


class ReleaseTests(unittest.TestCase):
    def test_manifest_points_to_real_entrypoints_and_respects_boundaries(self):
        manifest = json.loads((ROOT/'agent.json').read_text())
        self.assertEqual(manifest['version'], build_release.VERSION)
        self.assertIn("VERSION='v"+build_release.VERSION+"'", (ROOT/'install.sh').read_text())
        for args in manifest['entrypoints'].values():
            self.assertEqual(args[0], 'python3')
            self.assertTrue((ROOT/args[1]).is_file())
        self.assertFalse(manifest['boundaries']['auto_start_sharing'])
        self.assertFalse(manifest['boundaries']['physical_microphone'])
        schema = json.loads((ROOT/'agent.schema.json').read_text())
        self.assertEqual(set(manifest), set(schema['required']))
        try:
            import jsonschema
        except ImportError:
            return  # La CI Linux exécute aussi la validation JSON Schema complète.
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(manifest, schema)

    def test_built_archives_include_common_engine_and_matching_checksums(self):
        result = subprocess.run([sys.executable, str(ROOT/'build_release.py')],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        dist = ROOT/'dist'
        for line in (dist/'SHA256SUMS').read_text().splitlines():
            digest, name = line.split()
            self.assertEqual(hashlib.sha256((dist/name).read_bytes()).hexdigest(), digest)
        for name, member in [('TV-WiFi-Linux.zip', 'TV Wi-Fi Linux/dlna.py'),
                             ('TV-WiFi-macOS.zip', 'TV Wi-Fi macOS/TV Wi-Fi.app/Contents/Resources/dlna.py')]:
            with zipfile.ZipFile(dist/name) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(archive.read(member), (ROOT/'common/dlna.py').read_bytes())
        if shutil.which('dpkg-deb'):
            package = dist/f'tv-wifi_{build_release.VERSION}_all.deb'
            fields = subprocess.check_output(['dpkg-deb', '-f', str(package)], text=True)
            self.assertIn('gstreamer1.0-plugins-ugly', fields)
            self.assertNotIn('nvidia-driver', fields)
            self.assertIn('Architecture: all', fields)
            contents = subprocess.check_output(['dpkg-deb', '-c', str(package)], text=True)
            self.assertIn('./usr/lib/tv-wifi/dlna.py', contents)
            self.assertIn('./usr/bin/tv-wifi', contents)
            control = subprocess.check_output(['dpkg-deb', '--ctrl-tarfile', str(package)])
            import io, tarfile
            with tarfile.open(fileobj=io.BytesIO(control)) as archive:
                self.assertEqual([n.lstrip('./') for n in archive.getnames() if n not in ('.', './')], ['control'])
