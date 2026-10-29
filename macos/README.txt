TV WI-FI — VERSION MAC
======================

1. Décompressez TV-WiFi-macOS.zip sur le Mac.
2. La première fois seulement, ouvrez « Installer les prérequis.command ».
   Si nécessaire, il vous guide vers Python (python.org) et Homebrew, puis installe
   FFmpeg 7. Les outils déjà présents sont réutilisés. Une connexion Internet et,
   selon le Mac de l’école, l’aide de son administrateur peuvent être nécessaires.
3. Ouvrez « TV Wi-Fi.app ». Pour les utilisations suivantes, seule cette étape reste.
   Vous pouvez déplacer le dossier complet sur votre Bureau ou dans Applications.

Choisissez la TV dans la liste ou saisissez son adresse IP. Choisissez l’écran
du Mac à partager, puis activez « Partager mon écran ». La vidéo est transmise
en Full HD (1920 × 1080), 30 images/s, sans son, sans caméra ni microphone.
La dernière TV est mémorisée, mais aucune connexion n’est lancée automatiquement.
Décochez l’interrupteur ou fermez la fenêtre pour couper la diffusion.

LE MAC DEMANDE DES AUTORISATIONS

Acceptez l’accès au réseau local et à l’enregistrement de l’écran pour l’application
qui le demande (TV Wi-Fi, Python ou l’outil de capture selon le lancement).
Les réglages se trouvent dans Réglages Système → Confidentialité et sécurité :
« Réseau local » et « Enregistrement de l’écran et des sons du système ».
L’intitulé macOS mentionne le son, mais ce programme ne capture aucun son.
Après une autorisation d’écran, il peut être nécessaire de quitter puis rouvrir
TV Wi-Fi. Aucun réglage de sécurité n’est désactivé automatiquement.

L’application n’est pas signée/notariée par Apple. Si macOS la bloque, utilisez
les options normales « Ouvrir quand même » de Confidentialité et sécurité pour
ce programme que vous avez choisi, ou faites valider le paquet par votre école.
Ne désactivez pas Gatekeeper. « Lancer TV Wi-Fi.command » et le fichier Python
sont aussi fournis pour un lancement explicite depuis le dossier complet.

COMPATIBILITÉ ET LIMITES

- Code compatible Mac Intel et Apple Silicon ; Python 3.11+ avec Tk et FFmpeg
  compilé pour le Mac sont nécessaires. macOS récent, 14 ou ultérieur conseillé
  pour les outils de préparation actuels. Aucun binaire Linux ou NVIDIA inclus.
- TV avec récepteur vidéo DLNA, accessible sur le même réseau. Ce n’est pas
  un client AirPlay/Chromecast et l’IP seule n’active pas une fonction absente.
- Plusieurs secondes de décalage restent possibles. La mise en mémoire tampon
  du lecteur TV ne se règle pas entièrement depuis cette application.
- Tout l’écran sélectionné est partagé. Le flux n’est pas enregistré ; seuls
  l’IP choisie et un chemin aléatoire peuvent le recevoir. Transport local HTTP,
  non chiffré. Le serveur s’arrête avec la déconnexion ou la fermeture.
- Une autre personne qui reprend la TV ne voit pas sa lecture arrêtée par notre
  bouton : la commande Stop ne part que si la TV utilise encore notre URL.

Ce paquet a été construit et ses éléments testables contrôlés sur Linux.
La capture AVFoundation, les autorisations et l’interface native Mac ne peuvent
pas être validées matériellement sans un Mac. Ne pas confondre ces contrôles
avec une recette réussie dans toutes les salles de l’école.

Préférences privées : ~/Library/Application Support/TV Wi-Fi/preferences.json
Journal technique : ~/Library/Logs/TV Wi-Fi.log (pas d’image enregistrée).

Sources techniques officielles consultées pour le portage :
https://docs.python.org/3/using/mac.html
https://www.ffmpeg.org/doxygen/trunk/avfoundation_8m_source.html
https://www.ffmpeg.org/doxygen/7.1/videotoolboxenc_8c_source.html
https://formulae.brew.sh/formula/ffmpeg@7
https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy
https://support.apple.com/fr-be/guide/mac-help/mchld6aa7d23/mac
