---
name: regen
description: Met à jour les outils de l'atelier (plugin aoi : serveurs MCP, add-ins Rhino et Revit) à la version validée par l'IT dans la console, sans relancer installer-poste.ps1. Utiliser quand l'utilisateur tape /regen, demande de récupérer les nouveaux serveurs MCP ou outils de l'atelier, ou quand /plugin signale que le catalogue aoi n'est pas autorisé.
---

# /regen : récupérer la version validée des outils de l'atelier

La commande se tape `/regen`. Si une autre commande porte déjà ce nom, utiliser `/aoi:regen`.

La version des outils est choisie par l'IT dans la console d'administration (étiquette du dépôt `itmaster-aoi/outils-ia` dans les managed settings). Cette skill aligne le poste sur cette étiquette. Elle ne choisit jamais une version elle-même et n'installe rien d'autre que le plugin `aoi`.

## Ce que tu fais quand on t'appelle

1. Lance l'état du poste, sans rien changer, avec le Python embarqué du plugin, `controle/runtime` (le poste n'a pas forcément de Python) :
   ```
   "<dossier de cette skill>/../../controle/runtime/python.exe" "<dossier de cette skill>/scripts/maj.py"
   ```
2. Si l'état est « catalogue à jour », que les add-ins sont à jour et qu'aucune « ANCIENNES VERSIONS » n'est signalée, dis-le en une ligne et arrête-toi.
3. Sinon, annonce la mise à jour (étiquette actuelle et étiquette imposée), puis lance :
   ```
   "<dossier de cette skill>/../../controle/runtime/python.exe" "<dossier de cette skill>/scripts/maj.py" --appliquer
   ```
   Le script réinscrit le catalogue à l'étiquette imposée, met le plugin à jour et recopie les add-ins Rhino et Revit qui ont changé, si Rhino et Revit sont fermés.
   Le script commence toujours par faire relire les règles de la console (ligne « Règles de la console ») : une étiquette changée dans la console est vue sans redémarrer la session.
   Après la mise à jour, il efface les anciennes versions du plugin gardées dans le cache (environ 300 Mo chacune), sauf celle dont tourne la session en cours : elle partira au `/regen` suivant.
4. Présente le résultat : version avant et après, **nouveaux serveurs**, serveurs retirés, **nouvelles skills**, add-ins recopiés ou en attente, place libérée dans le cache. Termine par la consigne de **quitter et relancer Claude Code** : les serveurs ne se chargent qu'au démarrage.
5. En cas d'échec (« RÈGLES NON REÇUES », inscription refusée, plugin introuvable) :
   - ne tente **aucune autre source** : pas d'autre dépôt, pas d'autre étiquette, pas de `git clone`, pas d'installation manuelle ;
   - propose de lancer `installer-poste.cmd`, ou de contacter l'IT si le problème persiste.

## Pour l'IT

- **Au démarrage de chaque session** (crochet `SessionStart` du plugin, `hooks/hooks.json`) : `maj.py --demarrage` affiche une ligne à l'utilisateur, sans rien transmettre à Claude : « Outils IA atelier oï, v<version> : <serveurs> · Python <version>, <chemin> · vos librairies sont à jour » (ou « nouveaux outils : … » par rapport à la session précédente, `%LOCALAPPDATA%\aoi\session.json`, ou « mise à jour disponible : tapez /aoi:regen »), plus une alerte si le contrôle des imports est inactif. Chaque passage est noté dans `%LOCALAPPDATA%\aoi\demarrage.log`. Il ne met rien à jour lui-même et ne lance pas de `claude` imbriqué (il bloquerait le démarrage) : `/regen` reste nécessaire.
- **Add-ins publiés à part** : une entrée de `addin.json` peut donner une `archive` (version, url, sha256, taille) au lieu d'une `source` du plugin. `/regen` et `installer-poste.ps1` (`maj.py --addins`) ne la téléchargent que si sa version manque dans `%LOCALAPPDATA%\aoi\addins`, et la refusent si l'empreinte diffère. C'est le cas des add-ins Revit et Rhino.
- **Parties lourdes publiées à part** (`archives/construire.py <nom> <version>`, puis `gh release create`) : add-ins Revit et Rhino (fiche `archive` de `addin.json`) et serveur MCP Revit (`revit-server-aoi.json`, `"versionne": true`). Une partie « versionnée » s'installe dans `%LOCALAPPDATA%\aoi\<nom>-<version>`, à côté de la version qu'utilise peut-être la session en cours ; le plugin (`.mcp.json`) désigne la version de sa fiche ; les fichiers `conserver` (ex. `revit-data.db`) sont repris de la version précédente. Les librairies du serveur Rhino restent dans le plugin : hors du dossier de `run.py`, le contrôle des imports les refuserait.

- **Règles de la console** : Claude Code n'écrit `~/.claude/remote-settings.json` qu'au démarrage d'un processus `claude`. `maj.py` lance donc d'abord `claude plugin marketplace list` (lecture seule), qui le réécrit. La session en cours garde ses anciennes règles jusqu'au redémarrage, mais `/regen` voit déjà la nouvelle étiquette.

- **Qui prépare le poste après la mise à jour** : `maj.py --appliquer` de la version installée change seulement le catalogue et le plugin, puis lance `maj.py --finir` de la **nouvelle** version, avec le Python de cette version (`controle/runtime`). C'est cette dernière qui recopie les add-ins et le contrôle des imports, télécharge le Python et le Node AOI et nettoie le cache, avec ses propres chemins. Une version antérieure à 2026.10.15.2 n'a pas ce passage de main : elle fait ces étapes elle-même, avec ses anciens chemins. Le crochet de démarrage rattrape alors le contrôle des imports (`activer_controle.py --si-besoin`). Une étape dont le script manque s'affiche « ÉCHEC : … introuvable », jamais en silence.
- **Règle : ne pas déplacer ce qu'utilise un ancien `/regen`.** Ces chemins doivent rester valables dans toute nouvelle version : `skills/regen/scripts/maj.py`, `controle/runtime/python.exe` et l'option `--finir`, que la version précédente lance. Un fichier que seul `finir()` utilise (add-ins, `controle/scripts/activer_controle.py`, `archives_aoi.py`) peut changer de place dans une version **N+1**, à condition qu'une étiquette N contenant `--finir` ait été imposée aux postes avant. Sinon, ajouter au crochet de démarrage un rattrapage, comme `controle_si_besoin()`.
- **Publier un nouveau serveur** : l'ajouter dans `plugins/aoi/mcp/<serveur>/` et dans `.mcp.json`, **augmenter la version** de `plugin.json` (sinon `claude plugin update` ne voit rien), créer l'étiquette, puis la reporter dans les deux entrées des managed settings. Les postes la récupèrent ensuite avec `/regen`.
- **Changer d'étiquette retire puis réinscrit le catalogue** : Claude Code désinstalle alors le plugin et le réinstalle en entier (environ 57 Mo depuis que les add-ins et le serveur Revit sont publiés à part ; 185 Mo avant). Le journal des imports (`%LOCALAPPDATA%\aoi`) n'est pas touché.
- `installer-poste.ps1` reste nécessaire pour un poste neuf (Git, Claude Code, jeton) et pour un poste qui n'a pas encore de plugin contenant `/regen`.
- **Add-in d'un serveur** : le décrire dans `mcp/<serveur>/addin.json`, avec un objet par application ou version. Exemple :
  ```json
  { "add-ins": [ {
      "nom": "Revit 2025",
      "si_existe": "%APPDATA%/Autodesk/Revit",
      "source": "addin/2025",
      "destination": "%APPDATA%/Autodesk/Revit/Addins/2025",
      "processus": "Revit.exe",
      "sauvegarder": ["revit_mcp_plugin/Commands/commandRegistry.json"] } ] }
  ```
  `/regen` copie le contenu de `source` dans `destination` si l'application a déjà été lancée sur ce compte (`si_existe`) et si elle est fermée (`processus`). Un serveur sans `addin.json` n'a pas d'add-in.
- **Limite** : `/regen` copie seulement des fichiers dans le profil de l'utilisateur. Un add-in qui demande une inscription dans le registre, une installation (`.msi`) ou des droits d'administrateur reste à la charge de l'IT.
