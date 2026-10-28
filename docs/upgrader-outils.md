# Mise à jour des postes : `upgrader-outils.cmd`

Depuis le plugin 2026.10.28.4, la mise à jour d'un poste se lance hors de Claude Code, par `upgrader-outils.cmd`. Cette commande remplace la skill `/regen`. Une session ouverte garde ses serveurs MCP et verrouille les fichiers à remplacer.

`upgrader-outils.cmd`, `installer-claude.cmd`, `installer-poste.cmd`, leurs scripts PowerShell et leurs tests ne sont pas dans ce dépôt. L'IT les tient dans un dépôt interne, non publié, et les copie sur le partage de l'atelier.

## Ce que ce dépôt fournit

- **Le moteur** : `plugins/aoi/skills/regen/scripts/maj.py`. `upgrader-outils.cmd` lance `maj.py --appliquer` du plugin installé, avec son Python embarqué (`controle/runtime/python.exe`). `maj.py` réinscrit le catalogue à l'étiquette imposée, met le plugin à jour, puis lance `maj.py --finir` de la nouvelle version. `finir()` copie les add-ins et le contrôle des imports, installe le Python et le Node AOI, nettoie le cache et renvoie 1 si une étape a échoué.
- **Les messages** : `maj.py`, `archives_aoi.py`, `lancer.py` et le crochet de démarrage disent « fermez Claude Code, puis lancez upgrader-outils.cmd ». Un message qui signale un problème contient `ÉCHEC` : le lanceur l'affiche en rouge.
- **Les fiches d'add-in** : la clé `processus` de `mcp/<serveur>/addin.json` sert deux fois. `maj.py` ne copie pas l'add-in si l'application est ouverte, et le lanceur demande de la fermer avant la mise à jour.

## Règle : ne pas déplacer ce qu'utilise une version précédente

Ces chemins restent valables dans toute nouvelle version : `skills/regen/scripts/maj.py`, `controle/runtime/python.exe` et l'option `--finir`. Le lanceur et les versions précédentes du plugin les utilisent. Un fichier que seul `finir()` utilise peut changer de place dans une version N+1, à condition qu'une étiquette N contenant `--finir` ait été imposée aux postes avant.

## Pour l'IT

- **Au démarrage de chaque session** (crochet `SessionStart`, `hooks/hooks.json`) : `maj.py --demarrage` affiche une ligne à l'utilisateur, sans rien transmettre à Claude. Si la console impose une autre étiquette, la ligne demande de lancer `upgrader-outils.cmd`.
- **Règles de la console** : `maj.py` lance d'abord `claude plugin marketplace list` (lecture seule), qui réécrit `~/.claude/remote-settings.json`. Une étiquette changée dans la console est vue sans autre geste.
- **Hors de Claude Code**, `activer_controle.py --verifier` vérifie la copie du contrôle des imports, pas le `PYTHONPATH` de la console : cette variable n'existe que dans les commandes lancées par Claude Code.
- **Publier une version** : augmenter la version de `plugin.json`, créer l'étiquette, puis la reporter dans les deux entrées des managed settings.
- **Limite** : la mise à jour copie seulement des fichiers dans le profil de l'utilisateur. Une inscription dans le registre, un `.msi` ou des droits d'administrateur restent à la charge de l'IT.
- **En cas d'échec** (« RÈGLES NON REÇUES », inscription refusée, plugin introuvable) : aucune autre source. Lancer `installer-poste.cmd`, ou contacter l'IT.

## Tests de ce dépôt

`tests/test_messages_aoi.py` vérifie qu'aucun message du plugin ne renvoie encore à `/aoi:regen`, que `maj.py` garde son chemin et que `activer_controle.py --verifier` ne signale pas à tort un contrôle inactif hors de Claude Code.
