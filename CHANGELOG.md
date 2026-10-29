# Changements

## 1.1.0

- Linux : capture Wayland avec consentement ScreenCast/PipeWire ; repli logiciel x264 sans NVIDIA obligatoire, test synthétique de l’encodeur et mode sans GPU.
- Audio optionnel : moniteur de la sortie par défaut Linux ; entrées BlackHole explicitement reconnues sur Mac. Aucun micro physique ni activation automatique.
- Profil 720p, conservation du format d’image, annulation pendant la connexion, arrêt SIGTERM et prise en compte de la révocation du portail Linux.
- Moteur DLNA commun : validation des URL et IP LAN, XML défensif, détection des SOAP Fault, limites de connexions et erreurs de capture bornées en mémoire. Nettoyage après échec de connexion.
- Installation épinglée à une version, checksum de l’installateur inclus, téléchargement HTTPS strict, ZIP vérifié et extraction sans chemins dangereux, bascule atomique de version.
- Paquet Debian sans scripts de maintenance privilégiés, build DMG sur Mac et préparation facultative de signature avec identité existante. Les paquets publiés sont non signés/non notariés.
- Diagnostic JSON sans capture, manifeste agent avec schéma, guides et intégration continue Linux/Mac. Les tests ne valent pas recette matérielle Mac/Wayland/TV.

## 1.0.0

Premières versions Linux X11/NVIDIA et macOS AVFoundation/VideoToolbox, vidéo sans audio et réception DLNA sur le réseau local.
