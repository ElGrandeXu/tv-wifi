# TV Wi-Fi sur Linux

Python 3.11+, GTK 3/PyGObject et GStreamer 1.22+ sont nécessaires. Le bureau est capturé avec X11 (`ximagesrc`) ou, sous Wayland, avec le portail de consentement ScreenCast et PipeWire (`pipewiresrc`). Le portail permet de sélectionner un écran ou une fenêtre ; X11 partage tout le bureau. Aucun changement de session ou de pilote n’est effectué.

L’encodeur NVIDIA `nvcudah264enc` est utilisé s’il réussit un test synthétique. Sinon, `x264enc` fonctionne en logiciel, **y compris sur Intel/AMD**. Le mode « Sans GPU » force ce choix ; 720p réduit la charge. L’app ajoute des bandes plutôt que déformer le format de l’écran.

## Installer

Sur Ubuntu/Mint/Debian récents, télécharger le `.deb` et `SHA256SUMS` de la même release, vérifier l’empreinte puis ouvrir le paquet dans le gestionnaire de logiciels. Il crée une entrée dans le menu des applications ; aucun service ni partage ne démarre. Retrait : `sudo apt remove tv-wifi` ; les préférences utilisateur sont conservées.

Pour le ZIP utilisateur, préparer les dépendances décrites dans [INSTALL_LLM.md](https://github.com/ElGrandeXu/tv-wifi/blob/main/INSTALL_LLM.md), décompresser et lancer `bash "Installer le raccourci.sh"`. Garder le dossier en place. Depuis les sources : `python3 linux/tv_wifi.py`. Diagnostic sans capture : ajouter `--diagnose`.

Wayland exige `gstreamer1.0-pipewire` et un backend xdg-desktop-portal fournissant **ScreenCast** pour votre bureau. Le portail GTK seul peut ne pas suffire. Un refus dans la fenêtre système annule le partage ; les autorisations ne sont pas mémorisées pour une reprise silencieuse. Ne pas modifier les services de portail au hasard.

## Son et arrêt

Le son est désactivé au lancement. La case dédiée capture seulement le **moniteur de la sortie audio par défaut au moment de la connexion**, via PulseAudio ou la compatibilité PulseAudio de PipeWire. `pactl`, `pulsesrc` et un encodeur AAC (`avenc_aac` ou `voaacenc`) sont nécessaires. Aucun micro de secours n’est sélectionné si le moniteur manque. Changer de sortie audio pendant le partage demande une reconnexion. Le son continue aussi localement ; le délai de la TV peut créer un écho : ajuster le volume du lecteur/ordinateur selon le cours, sans changer les réglages système automatiquement.

Fermer la fenêtre, couper le bouton ou envoyer SIGTERM arrête les processus de capture et le serveur. Un Stop distant n’est envoyé que si la TV utilise encore l’URL de cette session. La dernière TV est proposée sans connexion automatique. Préférences privées : `${XDG_STATE_HOME:-~/.local/state}/tv-wifi/preferences.json`.

## Si la TV n’apparaît pas

La TV doit offrir un récepteur vidéo DLNA, pas seulement AirPlay/Chromecast/Miracast. Essayer son IP ne contourne pas un réseau invité isolé ni une politique de l’établissement. L’app ne scanne pas tous les ports et n’ouvre aucune règle de pare-feu : demander au responsable réseau si les appareils sont isolés. Le flux HTTP reste non chiffré, réservé à l’IP choisie et à un chemin aléatoire ; utiliser un réseau de confiance.
