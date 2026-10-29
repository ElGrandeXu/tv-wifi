"""Construire l'archive Mac sans outil Apple, sans embarquer de binaire Linux."""
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import zipfile


def build(destination=None):
    if destination is None:
        destination = Path(__file__).resolve().parents[1]/'dist/TV-WiFi-macOS.zip'
    source = Path(__file__).parent
    staging = source/'distribution/TV Wi-Fi macOS'
    resources = staging/'TV Wi-Fi.app/Contents/Resources'
    executable = staging/'TV Wi-Fi.app/Contents/MacOS/tv-wifi'
    resources.mkdir(parents=True, exist_ok=True)
    executable.parent.mkdir(parents=True, exist_ok=True)
    for name in ['dlna.py', 'mac_backend.py', 'tv_wifi_macos.py']:
        shutil.copyfile(source.parent/'common'/name if name == 'dlna.py' else source/name, resources/name)
    shutil.copyfile(source/'launch.sh', executable)
    executable.chmod(0o755)
    info = {'CFBundleName': 'TV Wi-Fi', 'CFBundleDisplayName': 'TV Wi-Fi',
            'CFBundleIdentifier': 'org.marc.TVWifiMac', 'CFBundleExecutable': 'tv-wifi',
            'CFBundlePackageType': 'APPL', 'CFBundleShortVersionString': '1.1.0',
            'CFBundleVersion': '2', 'LSMinimumSystemVersion': '10.15',
            'NSHighResolutionCapable': True,
            'NSLocalNetworkUsageDescription': 'Rechercher les téléviseurs de votre salle et leur transmettre votre écran.',
            'NSScreenCaptureUsageDescription': 'Partager l’écran choisi sur votre TV.',
            'NSMicrophoneUsageDescription': 'Lire le son système routé vers BlackHole, seulement si vous activez le son. Aucun microphone physique n’est sélectionné.'}
    with (executable.parent.parent/'Info.plist').open('wb') as stream:
        plistlib.dump(info, stream, sort_keys=True)
    shutil.copyfile(source/'README.txt', staging/'LIRE-MOI.txt')
    installer = staging/'Installer les prérequis.command'
    shutil.copyfile(source/'install.command', installer)
    installer.chmod(0o755)
    launcher = staging/'Lancer TV Wi-Fi.command'
    launcher.write_text('#!/bin/bash\nROOT_DIR="$(cd "$(dirname "$0")" && pwd)"\n'
                        'exec "$ROOT_DIR/TV Wi-Fi.app/Contents/MacOS/tv-wifi"\n')
    launcher.chmod(0o755)
    python_launcher = staging/'TV Wi-Fi.py'
    python_launcher.write_text('#!/usr/bin/env python3\nfrom pathlib import Path\nimport sys\n'
                               'sys.path.insert(0, str(Path(__file__).resolve().parent / '
                               '"TV Wi-Fi.app/Contents/Resources"))\n'
                               'from tv_wifi_macos import main\nraise SystemExit(main())\n')
    python_launcher.chmod(0o755)
    # Liste fermée : aucun cache, état utilisateur ou artefact d'un ancien build.
    files = [*sorted(resources.glob('*.py')), executable, executable.parent.parent/'Info.plist',
             staging/'LIRE-MOI.txt', installer, launcher, python_launcher]
    manifest = {str(path.relative_to(staging)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    (staging/'SHA256.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    files.append(staging/'SHA256.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, str(path.relative_to(staging.parent)))
    temporary.replace(destination)
    print(json.dumps({'archive': str(destination), 'size': destination.stat().st_size,
                      'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
                      'files': len(files)}, ensure_ascii=False))
    return destination


if __name__ == '__main__':
    build()
