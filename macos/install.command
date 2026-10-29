#!/bin/bash
# Une préparation sur le Mac ; aucune action n'est exécutée sur le MSI.
set -e
if [ "$(uname -s)" != Darwin ]; then
    echo 'Cet installateur est réservé à macOS.'
    exit 1
fi
export PATH="/opt/homebrew/opt/ffmpeg@7/bin:/usr/local/opt/ffmpeg@7/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
printf '%s\n' 'TV Wi-Fi — préparation du Mac' '' 'Cette étape prépare Python avec son interface graphique et FFmpeg.'
python_ready() {
    for candidate in /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
        /usr/local/bin/python3 /opt/homebrew/bin/python3 \
        /Library/Frameworks/Python.framework/Versions/3.*/bin/python3 \
        /opt/homebrew/opt/python@3.14/bin/python3.14 /usr/local/opt/python@3.14/bin/python3.14; do
        if [ -x "$candidate" ] && "$candidate" -c 'import sys,tkinter; sys.exit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
            return 0
        fi
    done
    return 1
}
if ! python_ready; then
    printf '%s\n' '' 'Installez Python depuis python.org avec les options par défaut.' 'Le programme signé et universel fonctionne sur Mac Intel et Apple Silicon.'
    /usr/bin/open 'https://www.python.org/downloads/macos/'
    read -r -p 'Quand Python est installé, appuyez sur Entrée pour continuer. ' answer
    if ! python_ready; then
        echo 'Python avec Tk est encore introuvable. Relancez cet installateur après installation.'
        exit 1
    fi
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
    if ! command -v brew >/dev/null 2>&1; then
        printf '%s\n' '' 'FFmpeg est nécessaire. Installez Homebrew depuis son site officiel.'
        /usr/bin/open 'https://brew.sh/'
        read -r -p 'Quand Homebrew est installé, appuyez sur Entrée. ' answer
    fi
    if ! command -v brew >/dev/null 2>&1; then
        echo 'Homebrew est introuvable. Relancez cet installateur une fois Homebrew installé.'
        exit 1
    fi
    echo 'Installation de FFmpeg 7 via Homebrew ; le mot de passe peut être demandé par les outils du Mac.'
    brew install ffmpeg@7
fi
if ! ffmpeg -hide_banner -devices 2>&1 | /usr/bin/grep -q 'avfoundation'; then
    echo 'Ce FFmpeg ne propose pas la capture macOS AVFoundation.'
    exit 1
fi
if ! ffmpeg -hide_banner -encoders 2>&1 | /usr/bin/grep -q 'h264_videotoolbox'; then
    echo 'Ce FFmpeg ne propose pas l’encodage macOS VideoToolbox.'
    exit 1
fi
printf '%s\n' '' 'Préparation terminée. Ouvrez TV Wi-Fi.app.' 'À la première connexion, autorisez le réseau local et la capture de l’écran.'
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
/usr/bin/open "$ROOT_DIR/TV Wi-Fi.app"
