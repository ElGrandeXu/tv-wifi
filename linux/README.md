# Linux

Cette version reprend une chaîne validée sur Linux Mint/Xfce avec une carte NVIDIA.
Elle nécessite une session **X11**, **Python 3.11+**, **GTK 3/PyGObject**, **GStreamer**
et un pilote NVIDIA avec l’encodeur GStreamer `nvcudah264enc` disponible.

Sur une base Ubuntu/Mint, les dépendances graphiques et GStreamer s’installent avec :

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gstreamer1.0-tools \
  gstreamer1.0-x gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad
```

Le pilote NVIDIA doit déjà fonctionner. L’outil ne l’installe et ne le reconfigure
pas. Vérification de l’encodeur : `gst-inspect-1.0 nvcudah264enc`.

Depuis l’archive décompressée, lancer `Installer le raccourci.sh`, puis ouvrir
**TV Wi-Fi** sur le Bureau. Le dossier de l’application doit rester à sa place
pour que le raccourci continue de fonctionner. Sans installation de raccourci,
`Lancer TV Wi-Fi.sh` ou `python3 linux/tv_wifi.py` depuis les sources fonctionne aussi.

Sélectionner la TV ou saisir son IP, puis activer l’interrupteur. Fermer la fenêtre
arrête la capture, le serveur et la lecture distante si elle utilise toujours notre
vidéo. La dernière TV est proposée, jamais connectée automatiquement.

Les TV doivent offrir un récepteur vidéo DLNA sur le même réseau. Une IP manuelle
déclenche une recherche ciblée du service, pas un scan de tous les ports. Aucun
son, caméra ou microphone n’est capturé. Préférences privées sous
`~/.local/state/tv-wifi/preferences.json`.
