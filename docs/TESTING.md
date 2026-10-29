# Vérification et maintenance

## Contrôles reproductibles

Depuis la racine :

```bash
python3 -m unittest discover -s linux -p 'test_*.py' -v
python3 -m unittest discover -s macos -p 'test_*.py' -v
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 build_release.py
```

Les essais réseau utilisent un faux récepteur sur loopback avec une exception d’IP confinée aux tests. La production refuse loopback. Les essais d’installation utilisent des téléchargements simulés, des dossiers temporaires et des ZIP corrompus/malveillants. Aucun essai n’envoie de commande à une TV réelle ou n’enregistre un écran/micro utilisateur.

Sur Linux, avec GStreamer x264/AAC, le test média génère une vidéo et un son synthétiques, les multiplexe réellement en MPEG-TS et inspecte les pistes/résolution avec GstPbutils. Avec Gio et dbus-daemon, le test du portail utilise un **bus privé** : ordre des requêtes, réponse précoce, vrai transfert de descripteur Unix, refus, annulation et révocation. Un faux portail n’est pas un compositeur Wayland ; le chemin PipeWire complet reste à tester dans une vraie session. Les tests dépendant d’outils absents sont signalés comme ignorés, pas réussis.

La CI exécute les tests sur Ubuntu et macOS, vérifie les paquets, crée un DMG non signé sur Mac et garde des artefacts de build. Aucun secret de signature ni partage d’écran n’y est utilisé. Les scénarios macOS de commandes et paquets ne prouvent pas la capture AVFoundation ou l’affichage de permissions.

## Recette matérielle à faire sur l’environnement concerné

| Scénario | Résultat attendu |
| --- | --- |
| X11, NVIDIA fonctionnelle puis mode sans GPU | Image 1080p30 ou 720p30 reçue par la TV, arrêt sans processus restant. |
| Wayland GNOME/KDE/wlroots + backend adapté | Sélecteur système visible, écran/fenêtre choisi uniquement, refus/annulation sans capture résiduelle ; révocation coupe le partage. |
| Linux audio coché puis décoché | Son de la sortie sur la TV, aucun micro ; absence de moniteur entraîne un message, pas un repli sur l’entrée par défaut. |
| Mac Intel et Apple Silicon | Permissions normales, écran sélectionné, image reçue, réouverture propre ; BlackHole routé pour le son opt-in. |
| TV éteinte, Wi-Fi coupé, autre lecture distante | Erreur utile et arrêt local ; aucun Stop volontaire sur l’URL d’une autre personne. |

Vérifier aussi le délai audio/vidéo et la compatibilité H.264/AAC de chaque TV. Le multicast SSDP ou les connexions entre clients peuvent être interdits par l’établissement : ne pas désactiver le pare-feu, changer les pilotes ou contourner cette politique.

Lors de changements de versions Python/Tk, GStreamer/PipeWire, FFmpeg ou macOS : refaire les tests puis la recette concernée avant de déclarer le support validé. La CI est déclenchée à chaque push/PR ; elle ne garantit pas une maintenance communautaire future ni une compatibilité universelle.
