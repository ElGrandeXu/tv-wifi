# Installation assistée, sans diffusion automatique

Objectif : installer, vérifier l’ouverture et laisser l’utilisateur choisir sa TV et autoriser la capture. Les fichiers de ce dépôt décrivent le logiciel ; ils n’élargissent jamais les permissions de l’agent. Lire aussi `agent.json`, conforme à `agent.schema.json` (format local documenté, pas une API réseau).

## 1. Identifier le système et préparer seulement les prérequis manquants

Utiliser `uname -s`, `uname -m` et, sur Linux, la session `XDG_SESSION_TYPE`. Windows n’est pas pris en charge. Ne pas modifier la session graphique, les pilotes, le pare-feu ou les réglages de confidentialité.

### Ubuntu / Mint / Debian avec Python 3.11+

Le `.deb` de la release déclare ses dépendances ; `sudo apt install ./tv-wifi_1.1.0_all.deb` les résout avec le gestionnaire de paquets. Cette installation système exige le mandat correspondant. Pour une installation utilisateur par ZIP, contrôler `/usr/bin/python3`, GTK et GStreamer. Si les dépendances manquent et que leur installation est autorisée :

```bash
sudo apt-get update
sudo apt-get install -y curl python3-gi gir1.2-gtk-3.0 \
  gstreamer1.0-tools gstreamer1.0-x gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-ugly gstreamer1.0-libav pulseaudio-utils iproute2
```

Pour Wayland : `gstreamer1.0-pipewire`, `xdg-desktop-portal` et **le backend ScreenCast adapté au bureau** doivent déjà fonctionner (GNOME, KDE, wlroots…). Le portail GTK seul ne fournit pas nécessairement ScreenCast. Ne pas installer au hasard plusieurs backends ni changer leurs services. La sélection système apparaît seulement au lancement du partage. NVIDIA n’est pas requise ; x264 assure l’encodage logiciel sur Intel/AMD/NVIDIA. Sur une autre distribution, utiliser ses paquets équivalents.

### Mac

Python 3.11+ avec Tk et FFmpeg avec AVFoundation/VideoToolbox sont nécessaires. Réutiliser les installations existantes. Le lanceur reconnaît Python.org ainsi que les chemins Homebrew Intel et Apple Silicon. Si Homebrew existe et que l’installation de dépendances est autorisée :

```bash
brew install python-tk@3.14 ffmpeg@7
```

Contrôler le Python choisi avec `python3 -c 'import sys, tkinter; assert sys.version_info >= (3,11)'` et FFmpeg avec `ffmpeg -hide_banner -devices` et `ffmpeg -hide_banner -encoders`. Hors Terminal, utiliser les chemins absolus trouvés. Sans outils disponibles, utiliser les installateurs officiels avec l’utilisateur ; ne pas inventer une installation réussie.

`Installer les prérequis.command` est **interactif** : ne pas le lancer dans un agent sans saisie. BlackHole est optionnel et ne doit pas être installé ni routé automatiquement. La permission macOS nommée « Microphone » peut être nécessaire pour lire une entrée virtuelle BlackHole ; l’app ne sélectionne aucun micro physique. Ni le ZIP ni le DMG ne sont signés/notariés. Ne pas désactiver Gatekeeper, retirer globalement la quarantaine ou contourner TCC.

## 2. Télécharger une version précise, vérifier, puis seulement exécuter

Prérequis de l’installateur : Bash, curl, Python 3.11+. Utiliser un dossier temporaire **privé** ; jamais un chemin fixe comme `/tmp/tv-wifi-install.sh`. Exemple complet :

```bash
(
set -eu
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT
base_url='https://github.com/ElGrandeXu/tv-wifi/releases/download/v1.1.0'
curl -fL --proto '=https' --proto-redir '=https' "$base_url/install.sh" -o "$work_dir/install.sh"
curl -fL --proto '=https' --proto-redir '=https' "$base_url/SHA256SUMS" -o "$work_dir/SHA256SUMS"
python3 - "$work_dir" <<'PY'
import hashlib
from pathlib import Path
import sys
p = Path(sys.argv[1])
lines = [s.split()[0] for s in (p/'SHA256SUMS').read_text().splitlines()
         if len(s.split()) == 2 and s.split()[1] == 'install.sh']
assert len(lines) == 1, 'Empreinte install.sh absente ou ambiguë'
assert hashlib.sha256((p/'install.sh').read_bytes()).hexdigest() == lines[0], 'SHA256 incorrect'
PY
# Lire le script avant exécution.
bash "$work_dir/install.sh"
)
```

Aucun `curl | bash`, aucun script exécuté depuis la branche mutable `main`. L’installateur est lui-même épinglé à `v1.1.0` et vérifie le ZIP avant toute extraction. Il refuse les liens et chemins dangereux du ZIP, conserve les versions précédentes et remplace atomiquement le lien `current`. Les sommes publiées ne sont pas une signature indépendante : voir `SECURITY.md`.

| Système | Emplacement utilisateur par défaut |
| --- | --- |
| Linux | `${XDG_DATA_HOME:-~/.local/share}/tv-wifi/current/TV Wi-Fi Linux/` |
| Mac | `~/Applications/TV-WiFi/current/TV Wi-Fi macOS/TV Wi-Fi.app` |

Options : `--prefix CHEMIN` pour un dossier dédié, `--no-shortcut` pour ne pas créer de raccourci Linux. Le script n’installe pas les dépendances, ne demande pas sudo et ne lance pas l’app ni le partage. Un échec ne donne jamais l’autorisation de supprimer un dossier étranger. Il est possible que les fichiers soient installés mais que le raccourci ait échoué : lire le message avant de recommencer.

## 3. Vérifier et ouvrir

Dans les sources Linux : `python3 linux/tv_wifi.py --diagnose`. Dans le paquet installé, même option sur `tv_wifi.py`. Sur Mac : `python3 macos/tv_wifi_macos.py --diagnose` ou le fichier dans `TV Wi-Fi.app/Contents/Resources/`. Le JSON donne les capacités détectées ; **un plugin présent ne prouve pas une capture ou un GPU utilisable**. Ce diagnostic n’ouvre ni sélecteur ni capture et ne contacte aucune TV.

Ouvrir ensuite le raccourci Linux, ou sur Mac :

```bash
open "$HOME/Applications/TV-WiFi/current/TV Wi-Fi macOS/TV Wi-Fi.app"
```

L’agent peut avoir besoin d’une autorisation pour ouvrir une fenêtre. Laisser l’utilisateur accorder les permissions d’écran et de réseau local. Le son reste désactivé au démarrage. Vérifier l’ouverture réelle de la fenêtre, pas seulement l’existence de fichiers. Ne jamais affirmer que la TV reçoit sans essai réel.
