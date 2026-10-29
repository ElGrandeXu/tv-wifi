"""Essais de l'installateur avec téléchargements simulés et dossiers temporaires."""
import hashlib
import os
from pathlib import Path
import subprocess
import stat
import tempfile
import unittest
import zipfile

INSTALLER = Path(__file__).resolve().parents[1]/'install.sh'


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tv-wifi installer ')
        self.root = Path(self.temp.name)
        self.bin = self.root/'bin'
        self.bin.mkdir()
        self.fixtures = self.root/'downloads'
        self.fixtures.mkdir()
        self.prefix = self.root/'application avec espaces'
        self.env = dict(os.environ, PATH=str(self.bin)+os.pathsep+os.environ['PATH'],
                        TV_WIFI_TEST_PLATFORM='Linux', XDG_SESSION_TYPE='x11',
                        TV_WIFI_TEST_FIXTURES=str(self.fixtures),
                        TV_WIFI_TEST_CURL_LOG=str(self.root/'curl.log'),
                        TV_WIFI_TEST_SHORTCUT=str(self.root/'shortcut'),
                        TV_WIFI_TEST_OPEN=str(self.root/'unexpected-open'))
        self.executable('uname', '#!/bin/bash\nprintf "%s\\n" "$TV_WIFI_TEST_PLATFORM"\n')
        self.executable('open', '#!/bin/bash\ntouch "$TV_WIFI_TEST_OPEN"\n')
        self.executable('curl', '''#!/usr/bin/env python3
import os,sys
from pathlib import Path
args=sys.argv[1:]
output=Path(args[args.index('--output')+1])
name=args[-1].rsplit('/',1)[-1]
with Path(os.environ['TV_WIFI_TEST_CURL_LOG']).open('a') as log:log.write(name+'\\n')
data=(Path(os.environ['TV_WIFI_TEST_FIXTURES'])/name).read_bytes()
if os.environ.get('TV_WIFI_TEST_CORRUPT') and name.endswith('.zip'):data=b'corrupted'
output.write_bytes(data)
''')
        self.make_packages()

    def executable(self, name, content):
        path = self.bin/name
        path.write_text(content)
        path.chmod(0o755)

    def make_packages(self, version='first'):
        linux = {'TV Wi-Fi Linux/tv_wifi.py': '# '+version,
                 'TV Wi-Fi Linux/Lancer TV Wi-Fi.sh': '#!/bin/bash\nexit 77\n',
                 'TV Wi-Fi Linux/Installer le raccourci.sh':
                 '#!/bin/bash\nprintf done > "$TV_WIFI_TEST_SHORTCUT"\n'}
        mac = {name: '#!/bin/bash\nexit 77\n' for name in [
            'TV Wi-Fi macOS/TV Wi-Fi.app/Contents/MacOS/tv-wifi',
            'TV Wi-Fi macOS/Installer les prérequis.command',
            'TV Wi-Fi macOS/Lancer TV Wi-Fi.command']}
        sums = []
        for name, files in [('TV-WiFi-Linux.zip', linux), ('TV-WiFi-macOS.zip', mac)]:
            path = self.fixtures/name
            with zipfile.ZipFile(path, 'w') as archive:
                for filename, data in files.items():
                    archive.writestr(filename, data)
            sums.append(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+name)
        (self.fixtures/'SHA256SUMS').write_text('\n'.join(sums)+'\n')

    def tearDown(self):
        self.temp.cleanup()

    def run_installer(self, *extra):
        return subprocess.run(['bash', str(INSTALLER), '--prefix', str(self.prefix), *extra],
                              env=self.env, text=True, capture_output=True, timeout=10)

    def test_linux_install_repeated_install_and_update_preserve_versions(self):
        for _ in range(2):
            result = self.run_installer()
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list((self.prefix/'versions').iterdir())), 1)
        first = (self.prefix/'current').resolve()
        self.assertTrue((self.root/'shortcut').exists())
        self.assertFalse((self.root/'unexpected-open').exists())
        self.make_packages(version='second')
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(first.is_dir())
        self.assertNotEqual(first, (self.prefix/'current').resolve())
        self.assertEqual(len(list((self.prefix/'versions').iterdir())), 2)

    def test_no_shortcut_does_not_run_the_desktop_installer(self):
        result = self.run_installer('--no-shortcut')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root/'shortcut').exists())

    def test_mac_branch_preserves_executables_without_launch_or_input(self):
        self.env['TV_WIFI_TEST_PLATFORM'] = 'Darwin'
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stderr)
        app = self.prefix/'current/TV Wi-Fi macOS/TV Wi-Fi.app/Contents/MacOS/tv-wifi'
        self.assertTrue(app.stat().st_mode & 0o111)
        self.assertFalse((self.root/'unexpected-open').exists())
        self.assertFalse((self.root/'shortcut').exists())

    def test_corrupt_download_is_rejected_before_installing(self):
        self.env['TV_WIFI_TEST_CORRUPT'] = '1'
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('empreinte', result.stderr)
        self.assertFalse(self.prefix.exists())

    def test_foreign_directory_is_preserved_without_download(self):
        self.prefix.mkdir()
        (self.prefix/'cours.txt').write_text('à conserver')
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.prefix/'cours.txt').read_text(), 'à conserver')
        self.assertFalse((self.root/'curl.log').exists())

    def test_wayland_is_supported_without_changing_session(self):
        self.env['XDG_SESSION_TYPE'] = 'wayland'
        result = self.run_installer('--no-shortcut')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.env['XDG_SESSION_TYPE'], 'wayland')

    def test_unsupported_system_does_not_download(self):
        self.env['TV_WIFI_TEST_PLATFORM'] = 'OtherOS'
        self.assertEqual(self.run_installer().returncode, 2)
        self.assertFalse((self.root/'curl.log').exists())


    def alter_zip(self, name, data=b'attack', symlink=False):
        archive = self.fixtures/'TV-WiFi-Linux.zip'
        with zipfile.ZipFile(archive, 'a') as zipped:
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = ((stat.S_IFLNK | 0o777) if symlink else (stat.S_IFREG | 0o644)) << 16
            zipped.writestr(info, data)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        (self.fixtures/'SHA256SUMS').write_text(digest+'  TV-WiFi-Linux.zip\n')

    def test_path_traversal_absolute_paths_and_zip_symlinks_rejected_after_hash_check(self):
        for name, link in [('TV Wi-Fi Linux/../../escaped', False), ('/tmp/escaped', False),
                           ('TV Wi-Fi Linux/link', True), ('other-root/file', False)]:
            self.make_packages()
            self.alter_zip(name, symlink=link)
            with self.subTest(name=name):
                result = self.run_installer('--no-shortcut')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('dangereux', result.stderr)
                self.assertFalse(self.prefix.exists())

    def test_foreign_current_is_preserved(self):
        self.assertEqual(self.run_installer('--no-shortcut').returncode, 0)
        current = self.prefix/'current'
        current.unlink()
        current.write_text('foreign')
        self.assertNotEqual(self.run_installer('--no-shortcut').returncode, 0)
        self.assertEqual(current.read_text(), 'foreign')

    def test_modified_installed_version_is_not_silently_reused(self):
        self.assertEqual(self.run_installer('--no-shortcut').returncode, 0)
        source = self.prefix/'current/TV Wi-Fi Linux/tv_wifi.py'
        source.write_text('changed locally')
        result = self.run_installer('--no-shortcut')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('modifiée', result.stderr)
        self.assertEqual(source.read_text(), 'changed locally')

    def test_download_uses_immutable_release_and_https_redirect_policy(self):
        installer = INSTALLER.read_text()
        self.assertIn("VERSION='v1.1.0'", installer)
        self.assertIn('--proto-redir', installer)
        self.assertNotIn('releases/latest', installer)


if __name__ == '__main__':
    unittest.main(verbosity=2)
