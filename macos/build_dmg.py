#!/usr/bin/env python3
"""Créer un DMG sur macOS ; signature/notarisation seulement avec identité fournie."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity', help='Identité Developer ID Application déjà dans le trousseau')
    parser.add_argument('--notary-profile', help='Profil notarytool déjà configuré par le mainteneur')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('La création du DMG et sa signature nécessitent macOS.')
    if args.notary_profile and not args.identity:
        parser.error('La notarisation exige --identity.')
    dist = Path(__file__).resolve().parents[1]/'dist'
    archive = build.build(dist/'TV-WiFi-macOS.zip')
    with tempfile.TemporaryDirectory(prefix='tv-wifi-dmg-') as temporary:
        staging = Path(temporary)
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(staging)
            for item in zipped.infolist():
                (staging/item.filename).chmod((item.external_attr >> 16) & 0o777 or 0o644)
        content = staging/'TV Wi-Fi macOS'
        app = content/'TV Wi-Fi.app'
        if args.identity:
            subprocess.run(['codesign', '--force', '--timestamp', '--options', 'runtime',
                            '--sign', args.identity, str(app)], check=True)
            subprocess.run(['codesign', '--verify', '--strict', '--verbose=2', str(app)], check=True)
        target = dist/'TV-WiFi-macOS.dmg'
        subprocess.run(['hdiutil', 'create', '-volname', 'TV Wi-Fi', '-srcfolder', str(staging),
                        '-format', 'UDZO', '-ov', str(target)], check=True)
        if args.identity:
            subprocess.run(['codesign', '--timestamp', '--sign', args.identity, str(target)], check=True)
        if args.notary_profile:
            subprocess.run(['xcrun', 'notarytool', 'submit', str(target), '--keychain-profile',
                            args.notary_profile, '--wait'], check=True)
            subprocess.run(['xcrun', 'stapler', 'staple', str(target)], check=True)
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from build_release import write_checksums
        write_checksums(dist)
        print(target)
        if not args.identity:
            print('DMG NON SIGNÉ : ne pas le présenter comme signé ou notarié.')


if __name__ == '__main__':
    main()
