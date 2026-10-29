# TV Wi-Fi

**Votre écran sur la TV de la salle, sans câble HDMI.**

1. Ouvrez **TV Wi-Fi**.
2. Choisissez la TV, ou saisissez son adresse IP.
3. Activez le partage. Désactivez-le ou fermez la fenêtre pour arrêter.

La TV doit recevoir la vidéo **DLNA** sur le même réseau. Ce n’est pas un émetteur AirPlay, Chromecast ou Miracast. Plusieurs secondes de décalage restent possibles : adapté aux cours et présentations, pas aux jeux ou visioconférences. Aucune connexion automatique.

## Télécharger

**[Version 1.1.0 : téléchargements et SHA256SUMS](https://github.com/ElGrandeXu/tv-wifi/releases/tag/v1.1.0)**

| Votre ordinateur | Paquet | Fonctionnement |
| --- | --- | --- |
| Ubuntu / Mint / Debian récents | `tv-wifi_1.1.0_all.deb` ou `TV-WiFi-Linux.zip` | X11 ; Wayland via portail ScreenCast/PipeWire. NVIDIA **facultative** : repli logiciel x264 sur Intel/AMD/NVIDIA. |
| Mac Intel / Apple Silicon | `TV-WiFi-macOS.zip` ou `.dmg` | Python 3.11+ avec Tk et FFmpeg à préparer une fois ; capture AVFoundation, encodage VideoToolbox. |

Sur Linux, ouvrez le `.deb` avec votre gestionnaire de paquets, ou décompressez le ZIP et lancez `Installer le raccourci.sh`. Sur Mac, ouvrez `Installer les prérequis.command`, puis **TV Wi-Fi.app**. Les paquets ne démarrent aucun partage. [Guide Linux](linux/README.md) · [Guide Mac](macos/README.txt).

**Le son est optionnel et désactivé au démarrage.** Linux : cochez « Partager aussi le son du système ». Mac : routez votre sortie vers [BlackHole](https://github.com/ExistentialAudio/BlackHole), puis sélectionnez cette entrée dans l’app. Aucun microphone physique n’est proposé. Choisissez 720p si le réseau ou l’ordinateur peine ; le mode « Sans GPU » contourne un encodeur NVIDIA défaillant.

**Limites de qualification :** les tests automatiques vérifient le protocole, les commandes Mac, le contrat D-Bus du portail et un vrai flux vidéo/audio synthétique Linux. Ils ne remplacent pas un essai de réception sur votre TV, de capture dans une session Wayland réelle ou des permissions/captures sur un Mac. Le DMG et le `.deb` sont **non signés** ; le DMG n’est pas notarié et n’embarque pas Python/FFmpeg. Un DMG ne supprime pas les autorisations de confidentialité Apple.

## Vérifier avant d’installer

Téléchargez un paquet et `SHA256SUMS` depuis **la même version** ci-dessus. Dans le dossier contenant ces deux fichiers :

```bash
# Linux, par exemple pour le paquet Debian
sha256sum --ignore-missing -c SHA256SUMS
# Mac, par exemple pour le ZIP
shasum -a 256 TV-WiFi-macOS.zip
# Comparez exactement cette empreinte à la ligne correspondante de SHA256SUMS.
```

Un SHA256 détecte une corruption ou une différence ; téléchargé depuis le même compte GitHub, il ne protège pas contre un compte éditeur compromis. [Sécurité et réseau](SECURITY.md).

## Installer avec un assistant IA / LLM

Donnez-lui ce dépôt et ce message :

```text
Installe TV Wi-Fi depuis https://github.com/ElGrandeXu/tv-wifi.
Lis INSTALL_LLM.md et agent.json. Identifie mon système et vérifie les prérequis.
Télécharge une version précise et vérifie son SHA256 avant d’exécuter quoi que ce soit.
Installe dans mon compte utilisateur, puis ouvre l’application sans choisir de TV
ni démarrer le partage à ma place. Ne change ni pilotes, protections, session
ou routage audio. Demande-moi les permissions système réellement nécessaires.
```

N’accordez pas de droits administrateur généraux à un assistant. L’application ne nécessite pas d’IA pour fonctionner. [Procédure et commandes exactes](INSTALL_LLM.md) · [Description machine lisible](agent.json).

## Développer et vérifier

Une seule implémentation réseau dans [`common/dlna.py`](common/dlna.py), avec interfaces et capture propres à chaque OS dans `linux/` et `macos/`.

```bash
python3 -m unittest discover -s linux -p 'test_*.py' -v
python3 -m unittest discover -s macos -p 'test_*.py' -v
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 build_release.py
```

Le build produit les ZIP, l’installateur et `SHA256SUMS` dans `dist/`, plus un `.deb` si `dpkg-deb` existe. Le [build Mac](docs/RELEASING.md) crée le DMG sur macOS. [Changements](CHANGELOG.md) · [Vérification et maintenance](docs/TESTING.md).
