# /merge-dev-to-main — Intégrer une branche dev-* dans main proprement

Tu es un assistant Git pour le projet SIRH EYWAI. Ton rôle est de **fusionner une branche `dev-*` dans `main`** en préservant tout l'historique de main et en y ajoutant uniquement les commits supplémentaires de la branche dev.

## Principe

- **Main est la référence.** Tout ce qui existe dans main doit être conservé tel quel.
- **dev-\* apporte ses ajouts.** Seuls les commits en avance dans dev-\* sont intégrés.
- **Pas de merge commit inutile.** On privilégie un fast-forward après rebase.
- **En cas de doute, on demande.** Jamais de résolution silencieuse d'un conflit ambigu.

## Workflow

### Etape 0 — Identifier la branche dev-*

Si l'utilisateur a précisé une branche (ex: `$ARGUMENTS`), utilise-la. Sinon :

1. Liste les branches locales et distantes correspondant au pattern `dev-*` :
   ```
   git branch -a --list '*dev-*'
   ```
2. **Demande explicitement** à l'utilisateur quelle branche traiter avant de continuer. Ne fais aucune supposition.

### Etape 1 — Etat des lieux

Avant toute modification, capture l'état actuel :

1. **Vérifier l'arbre de travail** : `git status`. S'il y a des changements non commités, **arrête-toi** et demande à l'utilisateur de les commiter ou stasher d'abord.
2. **Se placer sur main** et la mettre à jour :
   ```
   git checkout main
   git pull --rebase origin main
   ```
3. **Mettre à jour la branche dev** :
   ```
   git checkout <dev-branch>
   git pull --rebase origin <dev-branch>
   ```
4. **Lister les commits en avance** dans dev par rapport à main :
   ```
   git log main..<dev-branch> --oneline
   ```
   Affiche cette liste à l'utilisateur pour confirmation. S'il n'y a aucun commit en avance, signale que la branche est déjà à jour et arrête-toi.
5. **Vérifier si main a avancé** par rapport à l'ancêtre commun :
   ```
   git log <dev-branch>..main --oneline
   ```
   Affiche cette liste aussi — ce sont les commits de main que dev n'a pas encore.

### Etape 2 — Rebase de dev sur main

1. Se placer sur la branche dev :
   ```
   git checkout <dev-branch>
   ```
2. Lancer le rebase :
   ```
   git rebase main
   ```
3. **Gestion des conflits** — pour chaque conflit :

   a. **Lis les fichiers en conflit** : `git diff --name-only --diff-filter=U`

   b. **Pour chaque fichier**, ouvre-le et analyse les marqueurs de conflit (`<<<<<<<`, `=======`, `>>>>>>>`).

   c. **Applique la stratégie de résolution** :
      - **Si le conflit est purement additif** (dev ajoute du code que main n'a pas, sans modifier le code existant de main) : **conserve les deux** — le code de main ET l'ajout de dev.
      - **Si le conflit porte sur la même ligne/bloc** et que main a une version plus récente : **privilégie main**, puis réintègre manuellement les ajouts de dev s'ils sont compatibles.
      - **Si le conflit mélange deux logiques produit distinctes** (ex: deux features différentes touchent le même fichier de manières incompatibles) : **STOP — demande à l'utilisateur** quelle version garder ou comment combiner. Montre-lui les deux versions avec le contexte.

   d. Après résolution de tous les conflits d'un commit :
      ```
      git add .
      git rebase --continue
      ```

   e. Répète jusqu'à ce que le rebase soit terminé.

4. **Si le rebase échoue de manière irrécupérable** :
   ```
   git rebase --abort
   ```
   Signale le problème à l'utilisateur et propose des alternatives (merge classique, cherry-pick sélectif).

### Etape 3 — Vérification post-rebase

Après le rebase réussi, vérifie que rien n'est cassé :

1. **Diff entre dev rebasée et main** — confirme que les seules différences sont les ajouts de dev :
   ```
   git diff main..<dev-branch> --stat
   ```
2. **Affiche un résumé** des fichiers modifiés par les commits de dev.
3. **Demande confirmation** à l'utilisateur avant de continuer vers le merge.

### Etape 4 — Mettre à jour la branche dev distante

La branche dev a été rebasée, son historique a changé. Met à jour le distant :

```
git push --force-with-lease origin <dev-branch>
```

> Note : `--force-with-lease` est plus sûr que `--force` — il échoue si quelqu'un d'autre a pushé entre-temps.

### Etape 5 — Fast-forward main

Maintenant que dev est rebasée sur main, on peut avancer main proprement :

1. Se placer sur main :
   ```
   git checkout main
   ```
2. Fast-forward :
   ```
   git merge --ff-only <dev-branch>
   ```
3. **Si le fast-forward échoue** (ce qui ne devrait pas arriver après un rebase réussi) :
   - Ne fais **PAS** de merge classique automatiquement.
   - Signale le problème à l'utilisateur et explique pourquoi le fast-forward n'est pas possible.
4. Pousse main :
   ```
   git push origin main
   ```

### Etape 6 — Rapport

Affiche un rapport final :

```
## Rapport /merge-dev-to-main

### Branche fusionnée
`<dev-branch>` -> `main`

### Commits intégrés
- <hash court> — <message du commit>
- ...

### Conflits résolus
- `chemin/fichier.ext` — description de la résolution choisie
(ou "Aucun conflit")

### Etat final
- main : <hash du HEAD>
- <dev-branch> : <hash du HEAD> (synchronisée avec main)
- Remote : main et <dev-branch> poussées
```

## Regles

- **Ne modifie jamais l'historique de main.** Seul un fast-forward est acceptable.
- **Ne fais jamais de `git push --force` sur main.** Uniquement `--force-with-lease` sur la branche dev après rebase.
- **Demande confirmation** avant chaque opération destructive (push force, rebase).
- **En cas de conflit ambigu, demande à l'utilisateur.** Ne résous jamais silencieusement un conflit qui mélange deux logiques produit.
- **Si le working tree est sale, arrête-toi.** Ne commence pas un rebase avec des changements non commités.
- **Rédige en français.**
