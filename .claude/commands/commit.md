# /commit — Valider la branche, commits découpés, push sur `origin`

Tu es un assistant Git pour le dépôt EYWAI. L’utilisateur veut **tout stager**, produire **un ou plusieurs commits** avec des messages **structurés et spécifiques** (pas un seul fourre-tout si le diff le justifie), puis **pousser** sur la branche validée — **en accord explicite avec l’utilisateur** avant le push.

## Branches autorisées pour commit + push

- `dev-mathieu`, `dev-jose`, `dev-alex`
- Toute autre branche `dev-*` **documentée** dans le dépôt (ex. `guidebranche.md`) : **même règles**.

**Interdit** : `main`, `master`, ou toute branche qui n’est pas une `dev-*` autorisée/documentée — **ne pas** `add` / `commit` / `push` sans que l’utilisateur confirme **explicitement** une exception (branche de secours, hotfix nommée, etc.) et que ce soit cohérent avec la politique du projet.

Si l’utilisateur a passé une branche dans les arguments (ex. `dev-alex`), **vérifie** qu’elle est bien une `dev-*` autorisée ; sinon **demande** avant de `git checkout`.

---

## Étape 1 — Valider la branche (obligatoire)

1. `git rev-parse --show-toplevel` si besoin pour confirmer la racine du dépôt.
2. Branche cible :
   - Si l’utilisateur a indiqué un nom de branche `dev-*` valide : propose `git checkout <branche>` puis **attends confirmation** si ce n’est pas déjà la branche courante.
   - Sinon : utilise la branche courante : `git branch --show-current`.
3. Si la branche n’est **pas** une `dev-*` autorisée → **arrête-toi**, affiche la branche actuelle et ce qui est attendu (`dev-alex`, etc.), sauf confirmation d’exception explicite de l’utilisateur.
4. `git status -sb` : signale les fichiers non suivis, renommages, conflits. **Ne pas** continuer avec un merge/rebase en cours non résolu — demande à l’utilisateur de finir ou d’abandonner d’abord.

---

## Étape 2 — Revue du diff (avant staging définitif)

1. `git diff` et `git diff --stat` sur les changements non commités.
2. Si un fichier **ne doit pas** être versionné (secrets, `.env` avec clés, artefacts locaux hors `.gitignore`) → **alerte** l’utilisateur et **exclus** ces chemins du commit (ne pas les `add`).

---

## Étape 3 — Staging global puis découpage en commits

1. `git add -A` à la racine du dépôt (sauf exclusions convenues avec l’utilisateur).
2. `git diff --cached --stat` et `git diff --cached --name-only` pour lister ce qui est indexé.

**Découpage (plusieurs commits)** quand le diff mélange **des intentions distinctes**. Stratégie par défaut, dans cet ordre, **une intention = un commit** :

| Lot (exemple) | Préfixe « spécial » dans le **titre** du message (obligatoire si ce lot est commité seul) |
|---------------|-------------------------------------------------------------------------------------------|
| Fichiers sous `.cursor/` | `chore(config-cursor): …` |
| Fichiers sous `.claude/` | `chore(config-claude): …` |
| `backend/` | `feat|fix|refactor|test|chore(backend): …` selon le diff réel |
| `frontend/` | `feat|fix|style|refactor|chore(frontend): …` selon le diff réel |
| Autres racines (`docs/`, scripts, etc.) | `docs:|chore:|ci:` etc. avec scope explicite si utile |

Pour appliquer le découpage après un `git add -A` :

1. `git reset` (sans `--hard`) pour **désindexer** tout en **gardant** les modifications dans l’arbre de travail.
2. Pour chaque lot : `git add -- <chemins du lot>`, puis `git status` pour vérifier que seul ce lot est stagé.
3. `git commit` avec un message qui respecte **tous** les points suivants :

**Format obligatoire du message** (une ligne courte + corps détaillé si le diff le mérite) :

```text
<type>(<scope>): <résumé impératif, ≤ ~72 caractères>

[CONFIG-CURSOR] ou [CONFIG-CLAUDE] ou [APP] : une ligne de contexte si utile

- Détail vérifiable (fichier ou comportement)
- Risque ou suite éventuelle (tests, migration)
```

- Les préfixes **`[CONFIG-CURSOR]`** / **`[CONFIG-CLAUDE]`** dans le **corps** sont **obligatoires** dès qu’un commit touche uniquement `.cursor/` ou uniquement `.claude/` (en plus du `chore(config-*):` dans le titre).
- **Pas** de messages vagues du type « update » ou « fix » sans lien avec le diff.
- **Un seul commit** si tout le staged correspond à **une seule** intention produit.

---

## Étape 4 — Vérification avant push

1. `git log -5 --oneline` pour afficher les commits créés ou ajoutés.
2. S’il n’y a **aucun** nouveau commit (rien à committer après add) : vérifier s’il reste des commits locaux non poussés (`git log @{u}..HEAD 2>/dev/null` ou équivalent) ; si oui, passer à l’étape 5 après validation.

---

## Étape 5 — Push **avec** l’utilisateur

1. Rappelle la branche : `git branch --show-current`.
2. **Demande une confirmation explicite** : *« Confirmer le push vers `origin/<branche>` ? Réponds Oui ou Non. »*
3. Si **Non** → ne pas pousser ; résume l’état local (commits créés, branche).
4. Si **Oui** → uniquement :

```bash
git push -u origin "$(git branch --show-current)"
```

- **Jamais** `git push origin main` ni `master` dans ce workflow.
- Si le push est refusé (non fast-forward) : **ne pas** `force push` sans demande explicite ; explique l’erreur et propose des options sûres (`git pull --rebase` sur la branche `dev-*` après accord, etc.).

---

## Synthèse finale (en français)

- Branche validée.
- Liste des commits (hash court + titre).
- Confirmation du push ou raison du refus.

---

## Règles

- **Français** pour les échanges avec l’utilisateur ; les messages de commit peuvent suivre l’habitude du dépôt (`git log -3`) pour rester cohérents.
- **Toujours** valider la branche avant `add` / `commit` / `push`.
- **Toujours** confirmation **Oui/Non** avant `git push`.
