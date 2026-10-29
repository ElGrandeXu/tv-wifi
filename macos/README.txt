TV WI-FI SUR MAC — version 1.1.0

1. Décompressez le ZIP, ou ouvrez le DMG et copiez le dossier TV Wi-Fi macOS
   dans votre compte utilisateur. Ne lancez pas les prérequis depuis le DMG
   en lecture seule : travaillez dans la copie.
2. La première fois, ouvrez « Installer les prérequis.command » : Python 3.11+
   avec Tk et FFmpeg avec AVFoundation/VideoToolbox doivent être disponibles.
   Ils ne sont pas embarqués. Mac Intel et Apple Silicon sont prévus.
3. Ouvrez TV Wi-Fi.app. Autorisez normalement Réseau local et Enregistrement
   de l’écran. Choisissez l’écran, la TV DLNA, puis activez le partage.

Le paquet est NON SIGNÉ et NON NOTARIÉ. Un DMG ne supprime ni Gatekeeper ni
les permissions d’écran ; aucun contournement n’est fourni. Les permissions
peuvent être attribuées par macOS à Python, FFmpeg ou au lanceur effectivement
utilisé. Après autorisation, une fermeture/réouverture peut être nécessaire.
Si une politique de l’établissement bloque l’app, passer par l’administrateur.
Le contrôle natif des permissions, de la capture et de la réception TV n’a
pas été réalisé sur un Mac utilisateur ; les tests de commandes ne le remplacent pas.

SON OPTIONNEL (désactivé au démarrage)

L’app ne propose que les entrées virtuelles BlackHole 2ch, 16ch ou 64ch.
Aucun microphone physique n’est proposé ; l’app ne modifie pas le routage.

Pour le son système : installer BlackHole depuis son projet officiel, puis
suivre son guide pour une sortie multiple (haut-parleurs + BlackHole) dans
Configuration audio et MIDI. Choisir cette sortie pour la lecture, relancer
TV Wi-Fi et sélectionner BlackHole dans le menu Son. Pour revenir en arrière,
rechoisir votre ancienne sortie audio. BlackHole est facultatif ; aucun pilote
ou périphérique virtuel n’est installé automatiquement par TV Wi-Fi.

macOS peut demander une autorisation nommée « Microphone » pour accéder à
l’entrée audio virtuelle via AVFoundation : elle ne signifie pas que l’app
sélectionne un micro. Si BlackHole n’est pas routé, le son sera silencieux.
Guide officiel : https://github.com/ExistentialAudio/BlackHole

L’image est en 1080p30 ou 720p30, sans étirement du format. Plusieurs secondes
de décalage sont possibles. Fermer la fenêtre coupe la diffusion. La TV et
le Mac doivent être sur le même réseau de confiance et la TV doit recevoir
la vidéo DLNA. AirPlay seul ne suffit pas. Ne pas désactiver le pare-feu pour
résoudre un réseau scolaire isolé.

Préférences : ~/Library/Application Support/TV Wi-Fi/preferences.json
Diagnostic sans capture : python3 tv_wifi_macos.py --diagnose (dans les sources
ou dans TV Wi-Fi.app/Contents/Resources avec un Python adapté).
Retrait : supprimer le dossier installé ; conserver les préférences si souhaité.
