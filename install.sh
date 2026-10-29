#!/bin/bash
# Installation utilisateur automatisable : ni dépendance, ni pilote, ni capture.
set -eu
BASE_URL='https://github.com/ElGrandeXu/tv-wifi/releases/latest/download'
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
            echo 'Installe TV Wi-Fi, sans installer ses dépendances ni le lancer.'
            exit 0 ;;
        *) echo "Option inconnue : $1" >&2; exit 2 ;;
    esac
done
platform="$(uname -s)"
case "$platform" in
    Darwin)
        asset='TV-WiFi-macOS.zip'; root_folder='TV Wi-Fi macOS'
        prefix="${prefix:-$HOME/Applications/TV-WiFi}"; hash_tool='shasum' ;;
    Linux)
        if [ "${XDG_SESSION_TYPE:-}" = wayland ]; then
            echo 'La version Linux nécessite X11 ; aucune session ne sera modifiée.' >&2
            exit 2
        fi
        asset='TV-WiFi-Linux.zip'; root_folder='TV Wi-Fi Linux'
        prefix="${prefix:-$HOME/.local/share/tv-wifi}"; hash_tool='sha256sum' ;;
    *) echo 'Système non pris en charge : macOS et Linux uniquement.' >&2; exit 2 ;;
esac
for tool in curl unzip awk "$hash_tool"; do
    command -v "$tool" >/dev/null 2>&1 || { echo "Outil manquant : $tool. Consultez INSTALL_LLM.md." >&2; exit 2; }
done
if [ -d "$prefix" ] && [ -n "$(ls -A "$prefix")" ] && [ ! -f "$prefix/.tv-wifi-install" ]; then
    echo 'Le dossier choisi contient des fichiers étrangers à cette installation. Choisissez un autre --prefix.' >&2
    exit 2
fi
if [ -e "$prefix/current" ] && [ ! -L "$prefix/current" ]; then
    echo 'Le chemin current existe sans être un lien de cette installation ; aucun fichier remplacé.' >&2
    exit 2
fi
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/tv-wifi.XXXXXXXX")"
readonly work_dir
trap 'rm -rf "$work_dir"' EXIT
curl --fail --silent --show-error --location --proto '=https' --output "$work_dir/$asset" "$BASE_URL/$asset"
curl --fail --silent --show-error --location --proto '=https' --output "$work_dir/SHA256SUMS" "$BASE_URL/SHA256SUMS"
expected="$(awk -v name="$asset" '$2 == name {print $1}' "$work_dir/SHA256SUMS")"
if ! [[ "$expected" =~ ^[0-9a-f]{64}$ ]]; then
    echo 'Empreinte SHA256 absente ou invalide ; installation annulée.' >&2
    exit 1
fi
if [ "$platform" = Darwin ]; then
    actual="$(shasum -a 256 "$work_dir/$asset" | awk '{print $1}')"
else
    actual="$(sha256sum "$work_dir/$asset" | awk '{print $1}')"
fi
if [ "$actual" != "$expected" ]; then
    echo 'Le téléchargement ne correspond pas à son empreinte ; installation annulée.' >&2
    exit 1
fi
unzip -q "$work_dir/$asset" -d "$work_dir/unpacked"
[ -d "$work_dir/unpacked/$root_folder" ] || { echo 'Paquet incomplet ; installation annulée.' >&2; exit 1; }
mkdir -p "$prefix/versions"
prefix="$(cd "$prefix" && pwd)"
printf '%s\n' 'https://github.com/ElGrandeXu/tv-wifi' > "$prefix/.tv-wifi-install"
release_dir="$prefix/versions/$expected"
if [ ! -d "$release_dir" ]; then
    mv "$work_dir/unpacked" "$release_dir"
fi
ln -sfn "$release_dir" "$prefix/current"
if [ "$platform" = Darwin ]; then
    chmod +x "$prefix/current/$root_folder/TV Wi-Fi.app/Contents/MacOS/tv-wifi" \
        "$prefix/current/$root_folder/Installer les prérequis.command" \
        "$prefix/current/$root_folder/Lancer TV Wi-Fi.command"
    printf '%s\n' "Application installée : $prefix/current/$root_folder/TV Wi-Fi.app"
    echo 'Préparez Python/Tk et FFmpeg si nécessaire (INSTALL_LLM.md), puis ouvrez TV Wi-Fi.app.'
else
    if [ "$shortcut" -eq 1 ]; then
        if ! bash "$prefix/current/$root_folder/Installer le raccourci.sh"; then
            echo "Application téléchargée dans $prefix/current ; préparez les dépendances (INSTALL_LLM.md)." >&2
            exit 2
        fi
    fi
    printf '%s\n' "Application installée : $prefix/current/$root_folder"
fi
echo 'Aucun partage d’écran lancé.'
