#!/bin/bash
# Installer uniquement le raccourci utilisateur, sans changer les pilotes.
set -eu
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if ! /usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "3.0"); from gi.repository import Gtk' 2>/dev/null; then
    echo 'Python 3, PyGObject et GTK 3 sont nécessaires. Consultez linux/README.md.' >&2
    exit 1
fi
if ! command -v gst-inspect-1.0 >/dev/null 2>&1 || ! gst-inspect-1.0 nvcudah264enc >/dev/null 2>&1; then
    echo 'GStreamer et son encodeur NVIDIA nvcudah264enc sont nécessaires. Consultez le guide Linux.' >&2
    exit 1
fi
/usr/bin/python3 - "$SCRIPT_DIR" <<'PY'
from pathlib import Path
import os
import subprocess
import sys
source = Path(sys.argv[1])/'tv_wifi.py'
desktop = os.environ.get('TV_WIFI_DESKTOP_DIR')
if not desktop:
    try:
        desktop = subprocess.check_output(['xdg-user-dir', 'DESKTOP'], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        desktop = str(Path.home()/'Desktop')
folder = Path(desktop)
folder.mkdir(parents=True, exist_ok=True)
argument = str(source).replace('%', '%%')
for char in ['\\', '"', '`', '$']:
    argument = argument.replace(char, '\\'+char)
launcher = folder/'TV Wi-Fi.desktop'
launcher.write_text('[Desktop Entry]\nVersion=1.0\nType=Application\nName=TV Wi-Fi\n'
                    'Comment=Partager son écran en Full HD, sans son\n'
                    'Exec=/usr/bin/python3 "'+argument+'"\n'
                    'Icon=video-display\nTerminal=false\nCategories=AudioVideo;\n')
launcher.chmod(0o755)
try:
    subprocess.run(['gio', 'set', str(launcher), 'metadata::trusted', 'true'],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
except (OSError, subprocess.CalledProcessError):
    print('Si le bureau le demande, autorisez le lancement du raccourci TV Wi-Fi.')
print('Raccourci installé :', launcher)
PY
