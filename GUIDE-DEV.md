# Guide développeur — démarrage rapide

Petit aide-mémoire pour travailler sur le projet sans se perdre.

---

## 1. Commencer une nouvelle implémentation et se mettre à jour avec la branche main (PAS A CHAQUE DEBUT DE SESSION)  : `/begin`

Dans le chat Cursor, écris **`/begin`** (ou demande explicitement de démarrer une session sur ta branche `dev-*`).

Ça prépare Git : bonne branche personnelle, dernières mises à jour de `main` intégrées, sans basculer sur `main`.

**Attention :** si tu as du travail local **non commité / fragile** ou que tu ne veux pas risquer de perdre, **ne lance pas `/begin`**. Passe directement à l’étape 2 (serveurs) ou règle d’abord tes changements (commit, stash, etc.) selon ton cas.

---

## 2. Lancer le frontend et le backend

Ouvre **deux terminaux** à la racine du dépôt.

**Terminal 1 — frontend**

```bash
cd frontend
npm run dev
```

**Terminal 2 — backend**

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

*(Si ton environnement Python est ailleurs, adapte la ligne `source …` comme d’habitude sur ta machine.)*

---

## 3. Fin de session (A FAIRE A CHAQUE FIN DE SESSION) : pousser ton travail avec `/push`

Quand tu as terminé une session et que tu veux **committer et pousser** sur **ta branche `dev-*`** (jamais `main` directement), écris **`/push`** dans le chat.

L’agent vérifie la branche, prépare des commits propres et pousse vers `origin` sur la même branche.

---

## Skills utiles

Dans Cursor, tu peux **mentionner la commande** ou **attacher le fichier** du skill pour guider l’agent.


| Commande / intention   | À quoi ça sert                                                                                                                                                                                                                                                                                                              |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`/debug`**           | Quelque chose **ne marche pas** : erreur dans le terminal, écran blanc, 500, stack trace, échec `npm` / `pytest`, message dans la console navigateur. Colle le **log** ou décris **ce que tu faisais** et **ce qui s’affiche**. L’agent diagnostique et corrige jusqu’à ce qu’un test minimal (build, relance, etc.) passe. |
| **`/frontend-design`** | Tu veux **améliorer l’UI/UX** d’un écran ou composant : plus propre, cohérent avec le reste du produit, **sans** look « template IA ». Décris en mots ce que tu veux (lisibilité, états hover/erreur/chargement, mobile, accessibilité).                                                                                    |
| **`/test`**            | Couverture **pytest** backend, CI, page Super Admin « Tests » : attacher le skill `test` (`.cursor/skills/test/SKILL.md`) ou taper `/test`.                                                                                                                                                                                  |
| **`/check-feature`**   | Vérifier qu’une fonctionnalité décrite est bien en place (front, back, tests) : skill `check-feature`.                                                                                                                                                                                                                       |
| **`/etat`**            | Bilan Git local vs `origin` / `main` : skill `etat`.                                                                                                                                                                                                                                                                       |
| **Fusion `dev-*` → `main`** | Procédure détaillée : skill `merge-dev-to-main` (fichier `SKILL.md` dans le même dossier).                                                                                                                                                                                                                             |

Les fichiers correspondants sont sous **`.cursor/skills/<nom>/SKILL.md`** (à attacher dans le chat si besoin).


---

## Raccourcis Mac (Cursor)

Sur **Mac**, les touches **Cmd** (⌘), **Maj** (⇧), **Option** (⌥) et **Ctrl** correspondent aux libellés anglais *Command*, *Shift*, *Option*, *Control*.


| Raccourci             | Effet utile                                                                                                 |
| --------------------- | ----------------------------------------------------------------------------------------------------------- |
| **⌘⇧B** (*Cmd+Maj+B*) | Ouvre une **fenêtre navigateur** intégrée dans Cursor (aperçu Simple Browser / équivalent selon ta config). |
| **⌘B**                | Afficher ou masquer la **barre latérale** (explorateur de fichiers).                                        |


*(Tu peux créer tes propres raccourcis dans Cursor → Réglages → Raccourcis clavier.)*

---

En résumé : **`/begin`** → **2 terminaux** (`npm run dev` + `uvicorn`) → travail → **`/push`** ; en cas de souci ou de polish UI, **`/debug`** ou **`/frontend-design`**.

