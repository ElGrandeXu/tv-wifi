# TV Wi-Fi

**Affichez l’écran de votre ordinateur sur la TV de votre salle, sans câble HDMI.**

L’image est en Full HD, **sans son**. L’ordinateur et la TV doivent être sur le même réseau.

## Comment ça marche ?

1. Ouvrez **TV Wi-Fi**.
2. Choisissez votre TV dans la liste, ou entrez son adresse IP si vous la connaissez.
3. Activez le partage. Pour arrêter, désactivez le bouton ou fermez la fenêtre.

## Installer avec votre assistant IA / LLM

**Donnez le lien de ce dépôt à votre assistant et copiez ce message :**

```text
Installe TV Wi-Fi sur mon ordinateur depuis https://github.com/ElGrandeXu/tv-wifi.
Lis le README et INSTALL_LLM.md, détecte mon système, installe les prérequis
et utilise l’installateur prévu. Ouvre ensuite l’application, sans lancer
le partage d’écran à ma place. Guide-moi pour les autorisations nécessaires.
Ne modifie pas mes pilotes ni mes protections de sécurité.
```

Votre assistant doit pouvoir exécuter des commandes sur votre ordinateur. Sinon, il peut vous guider pas à pas.

## Installer sur Mac, sans assistant

1. **[Téléchargez la version Mac](https://github.com/ElGrandeXu/tv-wifi/releases/latest/download/TV-WiFi-macOS.zip)** et décompressez le fichier.
2. **La première fois seulement**, ouvrez `Installer les prérequis.command`. Il vous aide à installer les outils nécessaires s’ils manquent.
3. Ouvrez **TV Wi-Fi.app**. Acceptez les autorisations **Réseau local** et **Enregistrement de l’écran** demandées par le Mac.

Les fois suivantes, ouvrez simplement **TV Wi-Fi.app**. Aucun son n’est capturé, même si le nom du réglage macOS mentionne aussi l’audio. [Besoin d’aide sur Mac ?](macos/README.txt)

## Installer sur Linux, sans assistant

**[Téléchargez la version Linux](https://github.com/ElGrandeXu/tv-wifi/releases/latest/download/TV-WiFi-Linux.zip)**, décompressez-la et ouvrez `Installer le raccourci.sh`. Le raccourci **TV Wi-Fi** apparaît sur votre Bureau.

Cette version nécessite une **carte NVIDIA** et une session **X11**. Si vous ne savez pas si votre ordinateur convient, demandez à votre assistant de le vérifier. [Prérequis Linux](linux/README.md).

## Pour les assistants IA : commandes exactes

**Procédure complète : [INSTALL_LLM.md](INSTALL_LLM.md)** — détection du système, prérequis, chemins de lancement et vérifications.

Après avoir vérifié les prérequis de ce guide, utilisez ces mêmes commandes sur Mac et Linux :

```bash
curl -fL https://raw.githubusercontent.com/ElGrandeXu/tv-wifi/main/install.sh -o /tmp/tv-wifi-install.sh
bash /tmp/tv-wifi-install.sh
```

L’installateur choisit la bonne version, vérifie le téléchargement et installe l’application dans le compte utilisateur. Il **ne demande aucune saisie interactive**, n’installe pas de pilote et ne lance pas le partage. Si un outil manque, consultez le guide ci-dessus.

## À savoir avant votre cours

- La TV doit accepter la réception vidéo **DLNA** : c’est la fonction utilisée pour recevoir l’image. Toutes les TV ne sont pas compatibles ; ce programme ne remplace pas AirPlay ou Chromecast.
- Il peut y avoir quelques secondes de retard entre l’ordinateur et la TV.
- Tout l’écran est partagé. Aucune image n’est enregistrée ; le flux local n’est pas chiffré.
- La chaîne vidéo Linux a été utilisée en conditions réelles. **La version Mac reste à valider sur un vrai Mac.**

<details>
<summary>Sources et tests, pour les développeurs</summary>

Sources : [`linux/`](linux/) et [`macos/`](macos/).

```bash
python3 -m unittest discover -s linux -p 'test_*.py' -v
python3 -m unittest discover -s macos -p 'test_*.py' -v
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Reconstruire les paquets : `python3 build_release.py` ; les fichiers sont créés dans `dist/`.

</details>
