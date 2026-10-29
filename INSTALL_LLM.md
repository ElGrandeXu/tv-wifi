# Installation par un assistant IA disposant d’un terminal

Objectif : installer l’application, vérifier qu’elle s’ouvre et laisser l’utilisateur choisir sa TV. Ne pas démarrer de diffusion sans son choix explicite.

## 1. Identifier la machine

```bash
uname -s
uname -m
```

- `Darwin` : macOS, Intel ou Apple Silicon ; suivre la préparation Mac.
- `Linux` : X11 et carte NVIDIA fonctionnelle avec NVENC sont requis. Vérifier la session avec `printf '%s\n' "$XDG_SESSION_TYPE"` et le pilote avec `nvidia-smi`. Si c’est Wayland ou une autre carte, expliquer la limite ; ne pas changer la session ni installer un pilote.
- Windows : non pris en charge ; ne pas exécuter cet installateur.

## 2. Préparer les dépendances

### Mac

Réutiliser les installations existantes. Python 3.11+ doit avoir `tkinter` ; FFmpeg doit proposer AVFoundation et VideoToolbox.

Si Homebrew est déjà installé :

```bash
brew install python-tk@3.14 ffmpeg@7
```

Hors Terminal, utiliser si nécessaire `/opt/homebrew/bin/brew` (Apple Silicon) ou `/usr/local/bin/brew` (Intel). Le Python installé se trouve notamment dans `/opt/homebrew/opt/python@3.14/bin/python3.14` ou `/usr/local/opt/python@3.14/bin/python3.14`. Le lanceur connaît ces chemins et ceux de Python.org.

Si Homebrew est absent et les dépendances manquent, utiliser les installateurs officiels avec l’utilisateur ou son administrateur, sans prétendre que tout est installé. Le fichier `Installer les prérequis.command` du paquet guide un humain vers Python.org et Homebrew : **il est interactif ; ne pas le lancer dans un agent qui attend un traitement sans saisie**.

Contrôler avec les chemins trouvés :

```bash
python3 -c 'import sys, tkinter; assert sys.version_info >= (3, 11)'
ffmpeg -hide_banner -devices
ffmpeg -hide_banner -encoders
```

Chercher `avfoundation` dans les périphériques et `h264_videotoolbox` dans les encodeurs. Python/FFmpeg ne sont pas embarqués. L’app n’est pas signée/notariée par Apple : utiliser les autorisations normales décrites dans le [guide Mac](macos/README.txt), sans désactiver Gatekeeper, le pare-feu ou la confidentialité.

### Linux Ubuntu / Mint / Debian

Après vérification de NVIDIA et X11, si les dépendances manquent et si l’installation de paquets est autorisée :

```bash
sudo apt-get update
sudo apt-get install -y curl unzip python3-gi gir1.2-gtk-3.0 \
  gstreamer1.0-tools gstreamer1.0-x gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad
gst-inspect-1.0 nvcudah264enc
```

Le dernier contrôle doit réussir. Pour une autre distribution, utiliser ses paquets équivalents ; ne pas lancer `apt-get` au hasard. Aucun pilote NVIDIA n’est installé par ces commandes.

## 3. Installer l’application sans interaction

Prérequis de l’installateur : `bash`, `curl`, `unzip`, `awk`, et `shasum` sur Mac ou `sha256sum` sur Linux.

```bash
curl -fL https://raw.githubusercontent.com/ElGrandeXu/tv-wifi/main/install.sh -o /tmp/tv-wifi-install.sh
# Lire le script téléchargé avant de l’exécuter.
bash /tmp/tv-wifi-install.sh
```

Il télécharge la version publiée de ce dépôt, contrôle son SHA256 et installe dans le compte utilisateur. Il ne lance ni navigateur, ni demande de saisie, ni capture. Il n’installe pas de dépendance système : les préparer à l’étape 2.

| Système | Emplacement par défaut |
| --- | --- |
| Mac | `~/Applications/TV-WiFi/current/TV Wi-Fi macOS/TV Wi-Fi.app` |
| Linux | `~/.local/share/tv-wifi/current/TV Wi-Fi Linux/` et raccourci Bureau `TV Wi-Fi` |

Options : `--prefix CHEMIN` pour un autre dossier dédié ; `--no-shortcut` pour éviter le raccourci Linux. Les dossiers non vides étrangers à cet installateur sont refusés et les anciennes versions sont conservées. Une sortie 2 après téléchargement indique notamment un prérequis restant à préparer ; lire le message, corriger la cause puis réessayer.

## 4. Ouvrir et vérifier sans choisir une TV à la place de l’utilisateur

Mac :

```bash
open "$HOME/Applications/TV-WiFi/current/TV Wi-Fi macOS/TV Wi-Fi.app"
```

Linux :

```bash
bash "$HOME/.local/share/tv-wifi/current/TV Wi-Fi Linux/Lancer TV Wi-Fi.sh"
```

L’agent peut devoir obtenir l’autorisation d’ouvrir une fenêtre. Vérifier qu’elle apparaît, puis expliquer le choix de TV et le bouton de partage. Sur Mac, laisser l’utilisateur accorder lui-même **Réseau local** et **Enregistrement de l’écran**. Ne pas annoncer une autorisation accordée sans l’avoir constatée.

Un agent sans terminal local doit guider l’utilisateur plutôt qu’annoncer une installation fictive. Le téléchargement et les tests du dépôt ne prouvent pas le bon fonctionnement de la capture native sur le Mac de l’utilisateur.
