#!/usr/bin/env python3
"""Construire les paquets distribués depuis un checkout indépendant."""
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile


def main():
    root = Path(__file__).resolve().parent
    dist = root/'dist'
    dist.mkdir(exist_ok=True)
    linux = dist/'TV-WiFi-Linux.zip'
    mapping = {'tv_wifi.py': root/'linux/tv_wifi.py',
               'Lancer TV Wi-Fi.sh': root/'linux/launch.sh',
               'Installer le raccourci.sh': root/'linux/install.sh',
               'README.md': root/'linux/README.md'}
    with zipfile.ZipFile(linux, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, source in mapping.items():
            info = zipfile.ZipInfo('TV Wi-Fi Linux/'+name)
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith(('.sh', '.py')) else 0o100644) << 16
            archive.writestr(info, source.read_bytes())
    spec = importlib.util.spec_from_file_location('build_macos', root/'macos/build.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    mac = builder.build(dist/'TV-WiFi-macOS.zip')
    sums = ''.join(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name+'\n'
                   for path in [linux, mac])
    (dist/'SHA256SUMS').write_text(sums)
    print(sums, end='')


if __name__ == '__main__':
    main()
