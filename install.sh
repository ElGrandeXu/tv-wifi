#!/bin/bash
# Installateur versionné : téléchargement complet, SHA256, extraction contrôlée.
set -eu
VERSION='v1.1.1'
BASE_URL="https://github.com/ElGrandeXu/tv-wifi/releases/download/$VERSION"
prefix=''
shortcut=1
while [ "$#" -gt 0 ]; do
    case "$1" in
        --prefix)
            [ "$#" -ge 2 ] || { echo 'Valeur manquante après --prefix.' >&2; exit 2; }
            prefix="$2"; shift 2 ;;
        --no-shortcut) shortcut=0; shift ;;
        --help|-h)
            echo 'Usage: bash install.sh [--prefix DOSSIER_DEDIE] [--no-shortcut]'
            echo 'Installe TV Wi-Fi v1.1.1, sans dépendance, pilote ou capture.'
            exit 0 ;;
        *) echo "Option inconnue : $1" >&2; exit 2 ;;
    esac
done
platform="$(uname -s)"
case "$platform" in
    Darwin)
        asset='TV-WiFi-macOS.zip'; root_folder='TV Wi-Fi macOS'
        prefix="${prefix:-$HOME/Applications/TV-WiFi}" ;;
    Linux)
        asset='TV-WiFi-Linux.zip'; root_folder='TV Wi-Fi Linux'
        prefix="${prefix:-${XDG_DATA_HOME:-$HOME/.local/share}/tv-wifi}" ;;
    *) echo 'Système non pris en charge : macOS et Linux uniquement.' >&2; exit 2 ;;
esac
for tool in curl python3; do
    command -v "$tool" >/dev/null 2>&1 || { echo "Outil manquant : $tool. Consultez INSTALL_LLM.md." >&2; exit 2; }
done
# Précontrôle en lecture seule : aucun téléchargement pour un dossier étranger.
python3 - "$prefix" <<'PY'
import os
from pathlib import Path
import sys
p = Path(os.path.abspath(sys.argv[1]))
marker = p/'.tv-wifi-install'
if p.is_symlink() or (p.exists() and (not p.is_dir() or
        (any(p.iterdir()) and (marker.is_symlink() or not marker.is_file() or
         marker.read_text().strip() != 'https://github.com/ElGrandeXu/tv-wifi')))):
    sys.exit('Le dossier choisi contient des fichiers étrangers. Choisissez un autre --prefix.')
PY
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/tv-wifi.XXXXXXXX")"
readonly work_dir
trap 'rm -rf "$work_dir"' EXIT
for name in "$asset" SHA256SUMS; do
    curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
        --tlsv1.2 --connect-timeout 15 --max-time 180 --retry 2 \
        --output "$work_dir/$name" "$BASE_URL/$name"
done
python3 - "$work_dir" "$asset" "$root_folder" "$prefix" "$platform" "$shortcut" <<'PY'
import fcntl
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

work, asset, root_folder, prefix, platform, shortcut = sys.argv[1:]
work = Path(work)
prefix = Path(os.path.abspath(prefix))
try:
    sums = (work/'SHA256SUMS').read_text(encoding='ascii')
    matches = [line.split()[0] for line in sums.splitlines()
               if len(line.split()) == 2 and line.split()[1] == asset]
    expected = matches[0] if len(matches) == 1 else ''
    if not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ValueError('Empreinte SHA256 absente ou invalide ; installation annulée.')
    if hashlib.sha256((work/asset).read_bytes()).hexdigest() != expected:
        raise ValueError('Le téléchargement ne correspond pas à son empreinte ; installation annulée.')
    files = {}
    total = 0
    with zipfile.ZipFile(work/asset) as archive:
        if len(archive.infolist()) > 256:
            raise ValueError('Paquet trop volumineux ; installation annulée.')
        for item in archive.infolist():
            path = PurePosixPath(item.filename)
            total += item.file_size
            mode = item.external_attr >> 16
            if (len(files) >= 256 or total > 64 * 1024 * 1024 or path.is_absolute()
                    or '..' in path.parts or '\\' in item.filename or not path.parts
                    or path.parts[0] != root_folder or item.filename != str(path)
                    or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))
                    or item.filename in files):
                raise ValueError('Chemin ou contenu dangereux dans le paquet ; installation annulée.')
            if not item.is_dir():
                files[item.filename] = (archive.read(item), mode)
    required = (['tv_wifi.py', 'Lancer TV Wi-Fi.sh', 'Installer le raccourci.sh'] if platform == 'Linux'
                else ['TV Wi-Fi.app/Contents/MacOS/tv-wifi', 'Installer les prérequis.command',
                      'Lancer TV Wi-Fi.command'])
    if not all(root_folder+'/'+name in files for name in required):
        raise ValueError('Paquet incomplet ; installation annulée.')
    prefix.mkdir(parents=True, exist_ok=True)
    lock_path = prefix/'.install-lock'
    if lock_path.is_symlink():
        raise ValueError('Verrou incohérent ; aucun fichier remplacé.')
    with lock_path.open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        marker = prefix/'.tv-wifi-install'
        if marker.exists() and (marker.is_symlink() or marker.read_text().strip() !=
                                'https://github.com/ElGrandeXu/tv-wifi'):
            raise ValueError('Marqueur étranger ; aucun fichier remplacé.')
        if not marker.exists() and any(p != lock_path for p in prefix.iterdir()):
            raise ValueError('Dossier modifié pendant le téléchargement ; aucun fichier remplacé.')
        versions = prefix/'versions'
        if versions.is_symlink():
            raise ValueError('Le dossier versions est un lien ; aucun fichier remplacé.')
        versions.mkdir(exist_ok=True)
        release = versions/expected
        current = prefix/'current'
        if os.path.lexists(current) and (not current.is_symlink() or current.resolve().parent != versions.resolve()):
            raise ValueError('Le chemin current est étranger ; aucun fichier remplacé.')
        if os.path.lexists(release):
            if release.is_symlink() or not release.is_dir():
                raise ValueError('Version existante incohérente ; aucun fichier remplacé.')
            for name, (data, mode) in files.items():
                target = release/name
                if target.is_symlink() or not target.is_file() or target.read_bytes() != data:
                    raise ValueError('Version existante modifiée ; aucun fichier remplacé.')
        else:
            with tempfile.TemporaryDirectory(prefix='.staging-', dir=versions) as staging:
                folder = Path(staging)/'release'
                folder.mkdir()
                for name, (data, mode) in files.items():
                    target = folder/name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    target.chmod(0o755 if mode & 0o111 or name.endswith(('.sh', '.command'))
                                 or name.endswith('/MacOS/tv-wifi') else 0o644)
                folder.rename(release)
        marker.write_text('https://github.com/ElGrandeXu/tv-wifi\n')
        temporary_link = prefix/('.current-' + os.urandom(8).hex())
        try:
            temporary_link.symlink_to(release)
            os.replace(temporary_link, current)
        finally:
            temporary_link.unlink(missing_ok=True)
        if platform == 'Linux' and shortcut == '1':
            result = subprocess.run(['bash', str(current/root_folder/'Installer le raccourci.sh')])
            if result.returncode:
                sys.exit('Application installée ; préparez les dépendances avant de créer le raccourci (INSTALL_LLM.md).')
    print('Application installée :', current/root_folder)
    print('Aucun partage d’écran lancé. Les versions précédentes sont conservées.')
except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
    print(str(error), file=sys.stderr)
    sys.exit(1)
PY
