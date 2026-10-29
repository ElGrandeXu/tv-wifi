#!/bin/bash
# Lanceur Finder : ne dépend pas du PATH d'un Terminal interactif.
set -u
CONTENTS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
export PATH="/opt/homebrew/opt/ffmpeg@7/bin:/usr/local/opt/ffmpeg@7/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONDONTWRITEBYTECODE=1
if [ "$(uname -s)" != Darwin ]; then
    echo 'Ce lanceur est réservé à macOS.' >&2
    exit 1
fi
PYTHON_BIN=''
for candidate in /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
    /usr/local/bin/python3 /opt/homebrew/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.*/bin/python3 \
    /opt/homebrew/opt/python@3.14/bin/python3.14 /usr/local/opt/python@3.14/bin/python3.14; do
    if [ -x "$candidate" ] && "$candidate" -c 'import sys,tkinter; sys.exit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done
if [ -z "$PYTHON_BIN" ]; then
    /usr/bin/osascript -e 'display dialog "Python 3 avec Tk est nécessaire. Lancez Installer les prérequis.command dans le dossier TV Wi-Fi macOS, puis rouvrez cette application." with title "TV Wi-Fi" buttons {"OK"} default button "OK"'
    exit 1
fi
umask 077
mkdir -p "$HOME/Library/Logs"
exec "$PYTHON_BIN" "$RESOURCES_DIR/tv_wifi_macos.py" 2>> "$HOME/Library/Logs/TV Wi-Fi.log"
