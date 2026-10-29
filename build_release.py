#!/usr/bin/env python3
"""Construire les archives et, si disponible, le paquet Debian sans privilèges."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

VERSION = '1.1.0'
ROOT = Path(__file__).resolve().parent


def linux_files():
    return {'tv_wifi.py': ROOT/'linux/tv_wifi.py',
            'linux_backend.py': ROOT/'linux/linux_backend.py',
            'portal.py': ROOT/'linux/portal.py', 'dlna.py': ROOT/'common/dlna.py',
            'Lancer TV Wi-Fi.sh': ROOT/'linux/launch.sh',
            'Installer le raccourci.sh': ROOT/'linux/install.sh',
            'README.md': ROOT/'linux/README.md'}


def build_deb(dist):
    with tempfile.TemporaryDirectory(prefix='tv-wifi-deb-') as temporary:
        package = Path(temporary)
        app = package/'usr/lib/tv-wifi'
        app.mkdir(parents=True)
        for name, source in linux_files().items():
            if name.endswith('.py'):
                shutil.copyfile(source, app/name)
        binary = package/'usr/bin/tv-wifi'
        binary.parent.mkdir(parents=True)
        binary.write_text('#!/bin/sh\nexec /usr/bin/python3 /usr/lib/tv-wifi/tv_wifi.py "$@"\n')
        binary.chmod(0o755)
        desktop = package/'usr/share/applications/tv-wifi.desktop'
        desktop.parent.mkdir(parents=True)
        desktop.write_text('[Desktop Entry]\nType=Application\nName=TV Wi-Fi\n'
                           'Comment=Partager son écran sur une TV DLNA\nExec=tv-wifi\n'
                           'Icon=video-display\nTerminal=false\nCategories=AudioVideo;\n')
        doc = package/'usr/share/doc/tv-wifi'
        doc.mkdir(parents=True)
        shutil.copyfile(ROOT/'linux/README.md', doc/'README.md')
        control = package/'DEBIAN/control'
        control.parent.mkdir()
        control.write_text(f'Package: tv-wifi\nVersion: {VERSION}\nArchitecture: all\n'
            'Section: video\nPriority: optional\nMaintainer: TV Wi-Fi contributors\n'
            'Homepage: https://github.com/ElGrandeXu/tv-wifi\n'
            'Depends: python3 (>= 3.11), python3-gi, gir1.2-gtk-3.0, gstreamer1.0-tools, '
            'gstreamer1.0-x, gstreamer1.0-plugins-base, gstreamer1.0-plugins-good, '
            'gstreamer1.0-plugins-bad, gstreamer1.0-plugins-ugly, iproute2\n'
            'Recommends: gstreamer1.0-pipewire, xdg-desktop-portal, pulseaudio-utils, gstreamer1.0-libav\n'
            'Description: Screen sharing to a DLNA television with optional system audio\n'
            ' X11 or consent-based Wayland capture, H.264/MPEG-TS. No GPU driver required.\n')
        result = dist/f'tv-wifi_{VERSION}_all.deb'
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(package), str(result)], check=True)
        return result


def write_checksums(dist):
    assets = sorted(p for p in dist.iterdir() if p.suffix in {'.zip', '.deb', '.dmg'} or p.name == 'install.sh')
    sums = ''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in assets)
    (dist/'SHA256SUMS').write_text(sums, encoding='ascii')
    return sums


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-deb', action='store_true')
    args = parser.parse_args()
    dist = ROOT/'dist'
    dist.mkdir(exist_ok=True)
    with zipfile.ZipFile(dist/'TV-WiFi-Linux.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, source in linux_files().items():
            info = zipfile.ZipInfo('TV Wi-Fi Linux/'+name)
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith(('.sh', '.py')) else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())
    spec = importlib.util.spec_from_file_location('build_macos', ROOT/'macos/build.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.build(dist/'TV-WiFi-macOS.zip')
    shutil.copyfile(ROOT/'install.sh', dist/'install.sh')
    if shutil.which('dpkg-deb'):
        build_deb(dist)
    elif args.require_deb:
        parser.error('dpkg-deb est nécessaire pour --require-deb.')
    print(write_checksums(dist), end='')


if __name__ == '__main__':
    main()
