---
name: regen
description: Met à jour les outils de l'atelier (plugin aoi : serveurs MCP, add-ins Rhino et Revit) à la version validée par l'IT dans la console, sans relancer installer-poste.ps1. Utiliser quand l'utilisateur tape /regen, demande de récupérer les nouveaux serveurs MCP ou outils de l'atelier, ou quand /plugin signale que le catalogue aoi n'est pas autorisé.
---

# /regen : récupérer la version validée des outils de l'atelier

La commande se tape `/regen`. Si une autre commande porte déjà ce nom, utiliser `/aoi:regen`.

La version des outils est choisie par l'IT dans la console d'administration (étiquette du dépôt `itmaster-aoi/outils-ia` dans les managed settings). Cette skill aligne le poste sur cette étiquette. Elle ne choisit jamais une version elle-même et n'installe rien d'autre que le plugin `aoi`.

## Ce que tu fais quand on t'appelle

1. Lance l'état du poste, sans rien changer, avec le Python fourni par la skill report (le poste n'a pas forcément de Python) :
   ```
   "<dossier de cette skill>/../report/runtime/python.exe" "<dossier de cette skill>/scripts/maj.py"
   ```
2. Si l'état est « catalogue à jour » et que les add-ins sont à jour, dis-le en une ligne et arrête-toi.
3. Sinon, annonce la mise à jour (étiquette actuelle et étiquette imposée), puis lance :
   ```
   "<dossier de cette skill>/../report/runtime/python.exe" "<dossier de cette skill>/scripts/maj.py" --appliquer
   ```
   Le script réinscrit le catalogue à l'étiquette imposée, met le plugin à jour et recopie les add-ins Rhino et Revit qui ont changé, si Rhino et Revit sont fermés.
   Le script commence toujours par faire relire les règles de la console (ligne « Règles de la console ») : une étiquette changée dans la console est vue sans redémarrer la session.
4. Présente le résultat : version avant et après, **nouveaux serveurs**, serveurs retirés, **nouvelles skills**, add-ins recopiés ou en attente. Termine par la consigne de **quitter et relancer Claude Code** : les serveurs ne se chargent qu'au démarrage.
5. En cas d'échec (« RÈGLES NON REÇUES », inscription refusée, plugin introuvable) :
   - ne tente **aucune autre source** : pas d'autre dépôt, pas d'autre étiquette, pas de `git clone`, pas d'installation manuelle ;
   - propose de lancer `installer-poste.cmd`, ou de contacter l'IT si le problème persiste.

## Pour l'IT

- **Règles de la console** : Claude Code n'écrit `~/.claude/remote-settings.json` qu'au démarrage d'un processus `claude`. `maj.py` lance donc d'abord `claude plugin marketplace list` (lecture seule), qui le réécrit. La session en cours garde ses anciennes règles jusqu'au redémarrage, mais `/regen` voit déjà la nouvelle étiquette.

- **Publier un nouveau serveur** : l'ajouter dans `plugins/aoi/mcp/<serveur>/` et dans `.mcp.json`, l'inscrire dans `skills/report/mcp-whitelist.txt`, **augmenter la version** de `plugin.json` (sinon `claude plugin update` ne voit rien), créer l'étiquette, puis la reporter dans les deux entrées des managed settings. Les postes la récupèrent ensuite avec `/regen`.
- **Changer d'étiquette retire puis réinscrit le catalogue** : Claude Code désinstalle alors le plugin et le réinstalle en entier (environ 350 Mo). Le journal des imports (`%LOCALAPPDATA%\aoi`) n'est pas touché.
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
