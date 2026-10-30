# Sécurité et confidentialité

## Périmètre

TV Wi-Fi est un outil local : aucun compte, serveur cloud, télémétrie, IA embarquée ou accès distant permanent. La capture ne démarre qu’après activation du partage et requête vidéo de la TV choisie. Le son est opt-in et non mémorisé. Aucun pilote, service, pare-feu, autorisation ou routage audio n’est modifié par l’app.

Le flux MPEG-TS est servi en HTTP **non chiffré** sur l’interface menant à la TV. Le serveur vérifie son IP et un chemin aléatoire de session ; il refuse les autres clients et les redirections. Ce contrôle IP n’authentifie pas cryptographiquement une TV et ne protège pas contre un équipement réseau hostile ou une usurpation sur le LAN. Utiliser un réseau de confiance, éviter les documents/notifications privés et couper le partage dès qu’il n’est plus utile. Aucun port fixe ni règle réseau permanente n’est créé.

Les réponses SSDP/XML et les URL DLNA sont non fiables : IP IPv4 LAN explicite, hôte cohérent, pas de proxy système, de redirection, de credentials, de DTD ou d’entités XML. Les réponses et le nombre de connexions sont bornés. Fermer la fenêtre arrête d’abord les captures, puis le serveur, avant les appels Stop réseau. SIGKILL ou un crash machine ne permettent pas un nettoyage applicatif garanti ; ne pas prétendre que toutes les coupures sont contrôlées. Un Stop n’est envoyé que si l’URL distante est encore celle de la session (une course avec une autre télécommande reste possible).

## Installer

Préférer une **release précise**, télécharger complètement et comparer SHA256 avant exécution. Le script distribué vérifie également le ZIP et refuse traversées de chemin, liens et dossiers étrangers. Un checksum téléchargé du même dépôt ne garantit pas l’identité de l’éditeur si ce dépôt est compromis. Les versions 1.1.x sont non signées, et le DMG non notarié. Ne pas contourner Gatekeeper ou TCC ; faire intervenir l’administrateur si nécessaire.

Un assistant IA n’a besoin d’aucun droit supplémentaire propre à TV Wi-Fi. Une installation utilisateur ne requiert pas sudo ; l’installation de dépendances et du `.deb` relève du gestionnaire système et du mandat de l’utilisateur. Aucun manifeste du dépôt n’autorise une élévation de privilèges ou le démarrage du partage.

## Signaler un défaut

Pour un défaut ordinaire, ouvrir une issue avec OS, session graphique, version et message d’erreur. Retirer IP, noms de salle et URLs de session. Pour une vulnérabilité, préférer le signalement privé GitHub si disponible ; ne pas publier de données de cours, contenu capturé, secrets ou preuve permettant l’accès à un partage actif.
