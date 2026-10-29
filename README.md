# TV Wi-Fi

**TL;DR :** affiche ton écran sur une TV de la salle, en **Full HD, sans son**, via le Wi-Fi. Choisis une TV détectée ou entre son IP, puis active l’interrupteur. Désactive-le ou ferme la fenêtre pour déconnecter.

## Mac — installation rapide

1. [Télécharge la version Mac](https://github.com/ElGrandeXu/tv-wifi/releases/latest/download/TV-WiFi-macOS.zip) et décompresse-la.
2. **Une seule fois :** ouvre `Installer les prérequis.command`. Il te guide pour Python avec Tk et FFmpeg, en réutilisant les outils déjà installés.
3. Ouvre **TV Wi-Fi.app**, autorise le **réseau local** et l’**enregistrement de l’écran** lorsque macOS le demande.
4. Choisis la TV et l’écran du Mac, puis coche **Partager mon écran**.

Mac Intel et Apple Silicon visés. Après la préparation initiale, il suffit d’ouvrir l’app. Si macOS demande une autorisation, utilise ses réglages normaux ; ne désactive pas ses protections. [Guide Mac détaillé](macos/README.txt).

## Linux

[Télécharge la version Linux](https://github.com/ElGrandeXu/tv-wifi/releases/latest/download/TV-WiFi-Linux.zip), décompresse, puis lance `Installer le raccourci.sh`. Ouvre ensuite **TV Wi-Fi** sur le Bureau, ou `Lancer TV Wi-Fi.sh` dans le dossier.

Cette version utilise **X11 + NVIDIA NVENC**, Python 3/GTK 3 et GStreamer avec `nvcudah264enc` ; Wayland et les autres encodeurs ne sont pas pris en charge. [Prérequis Linux](linux/README.md).

## À savoir

- Le PC/Mac et la TV doivent communiquer sur le même réseau ; la TV doit accepter la vidéo **DLNA**. Ce n’est pas un client AirPlay/Chromecast.
- Tout l’écran est partagé en **1920 × 1080, 30 images/s**, sans caméra, microphone ni son. Quelques secondes de retard sont possibles.
- Le flux n’est pas enregistré ; son accès est limité à l’IP choisie et à une URL aléatoire. Le transport local HTTP n’est pas chiffré.
- Linux a été essayé en conditions réelles. Le portage Mac et son paquet ont des tests locaux, mais **pas encore de validation sur un vrai Mac**.

### Sources et tests

Sources : [`linux/`](linux/) et [`macos/`](macos/). Tests sans vraie TV :

```bash
python3 -m unittest discover -s linux -p 'test_*.py' -v
python3 -m unittest discover -s macos -p 'test_*.py' -v
```

Pour reconstruire les téléchargements : `python3 build_release.py` (résultat dans `dist/`).
