# Construire et publier une version

Les paquets contiennent le code Python et les lanceurs, pas les bibliothèques système. Ne pas publier de mémoire privée ou de configuration utilisateur. Adapter ensemble la version de `build_release.py`, `install.sh`, `macos/build.py`, `agent.json`, les exemples et le changelog.

1. Exécuter les suites de `docs/TESTING.md` sur le commit à publier et vérifier la CI Linux/Mac.
2. Sur Linux : `python3 build_release.py --require-deb`. Les fichiers du `.deb` appartiennent à root dans l’archive ; le build ne nécessite pas root et n’installe rien. Les dépendances sont déclarées, sans scripts post-install ni changement de services.
3. Sur Mac : `python3 build_release.py`, puis `python3 macos/build_dmg.py`. Le DMG contient le dossier d’app et ses prérequis interactifs ; il ne rend pas l’app autonome ou signée. Le construire sur un runner Mac donne un DMG montable, pas une recette des permissions ou de la TV.
4. Réunir les artefacts du même commit, **ne pas écraser une release existante**, puis recalculer `SHA256SUMS` sur tous les ZIP/DEB/DMG et `install.sh`. Publier le tag et les artefacts seulement après les contrôles. Télécharger les assets publiés et refaire les empreintes ; vérifier une installation utilisateur isolée sans capture.

## Signature Apple : préalable externe, pas une promesse du build

La signature/notarisation nécessite un compte développeur Apple, une identité **Developer ID Application** et les droits correspondants. Le dépôt ne contient ni clé ni certificat et le build par défaut ne cherche pas de secrets. Aucune signature n’est fabriquée pour donner une fausse assurance.

Sur un Mac de maintenance déjà équipé, options facultatives :

```bash
python3 macos/build_dmg.py --identity 'Developer ID Application: IDENTITÉ EXISTANTE' \
  --notary-profile 'PROFIL DÉJÀ CONFIGURÉ'
```

Le script appelle codesign, vérifie la signature du bundle, soumet le DMG à notarytool et agrafe le ticket. Cette voie reste à qualifier avec une véritable identité et le paquet final : le lanceur dépend de Python/FFmpeg externes, dont les permissions et l’identité TCC ne sont pas rendues stables par la signature du wrapper. Pour une distribution Apple autonome, il faudra embarquer les exécutables adaptés aux architectures, vérifier leurs licences, signer chaque binaire et réaliser une recette Gatekeeper/TCC. Ne pas annoncer une notarisation réussie sans ces preuves.

Une somme SHA256 est une vérification d’intégrité, pas une signature Debian ni un dépôt APT de confiance. Le `.deb` publié est non signé ; aucun dépôt système n’est ajouté.
