---
description: Importer dans le cerveau CortexDB local les mémoires Claude Code déjà écrites (tous les projets, ou un projet par son chemin)
argument-hint: tout | <chemin du projet>
---

Importe dans le cerveau CortexDB local les fichiers de mémoire Claude Code déjà écrits, selon la convention de l'atelier. Argument : `$ARGUMENTS`.

1. Si l'argument est vide, demande à l'utilisateur : « tout » (tous les projets) ou le chemin d'un projet. Ne devine pas.
2. Lance la liste, en lecture seule, avec l'outil Bash :
   `"$LOCALAPPDATA/aoi/python/python.exe" "${CLAUDE_PLUGIN_ROOT}/memo/convention.py" memoires "<argument>"`
   Si `${CLAUDE_PLUGIN_ROOT}` n'est pas remplacé, le script est `memo/convention.py` du plugin aoi : dossier donné par `--plugin-dir`, sinon `%USERPROFILE%\.claude\plugins\cache\aoi\aoi\<version la plus récente>\memo`. Ne cherche nulle part ailleurs.
   La sortie donne le login Windows (auteur), la base, le nombre de fichiers par état, puis une ligne JSON par fichier : `fichier`, `type`, `nature`, `identifiant`, `etat`, `corps`.
3. Si la sortie commence par `ARRÊT`, rapporte le message et arrête-toi.
4. Montre le plan, sans le corps des fichiers : nombre par état, puis un tableau (projet, fichier, identifiant proposé, état). États :
   - `nouveau` : à écrire ;
   - `a-mettre-a-jour` : déjà importé, le fichier a changé ; à réécrire sous le même identifiant ;
   - `deja-importe` : rien à faire ;
   - `doublon-probable` : le fait est déjà dans le cerveau sous l'identifiant indiqué ; pas d'import, sauf si l'utilisateur le demande pour ce fichier.
5. Demande une seule confirmation : « Importer <n> nouveaux et mettre à jour <m> ? ». Sans accord, n'écris rien.
6. Pour chaque fichier `nouveau` ou `a-mettre-a-jour`, appelle `mcp__plugin_aoi_cortexdb__memory_save` :
   - `memory_id` : l'identifiant proposé ; remplace `<theme>` (et `<nature>` pour le type `project`) selon la skill `/aoi:memo` ; garde l'identifiant tel quel pour `a-mettre-a-jour` ;
   - `content` : le `corps`, tel quel ;
   - `user_id` : le login Windows de la sortie ; `scope` : `user` ; `namespace` : `assistant` ;
   - `metadata` : `nature`, `theme`, `status` = `current`, `date` du jour (AAAA-MM-JJ) si la nature est datée, `produit_par` = `claude-code`, et `source` = le chemin complet du fichier, c'est-à-dire la valeur du champ `fichier` de sa ligne JSON (par exemple `C:\Users\<login>\.claude\projects\<projet>\memory\<nom>.md`), jamais le mot « fichier ». Ce chemin permet de reconnaître l'élément au prochain import et au miroir.
   Si le crochet de convention refuse, corrige selon son message et relance ; ne contourne jamais le crochet.
7. Compte rendu : écrits, mis à jour, déjà importés, doublons laissés, refus restants (avec le message). Ne copie pas le corps des fichiers dans le compte rendu.

N'importe jamais un fichier qui contient un mot de passe, un jeton ou une clé : signale-le et passe au suivant.
