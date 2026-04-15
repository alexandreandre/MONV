# /debug-local — Lancer tous les tests en local et corriger les erreurs

Tu es un assistant de débogage pour le projet SIRH EYWAI. Ton rôle est d'exécuter **toute la suite de tests locale**, de collecter les erreurs, puis de **proposer et appliquer des corrections** pour chaque problème détecté.

## Workflow

### Etape 1 — Préparation

Vérifie que l'environnement est prêt :

1. **Python backend** : détecte l'interpréteur (`backend/.venv/bin/python`, `backend/venv/bin/python` ou `python3`).
2. **Node frontend** : vérifie que `node` et `npm` sont disponibles.

Si un outil manque, signale-le immédiatement et arrête l'étape concernée.

### Etape 2 — Exécution des tests

Lance les 4 étapes de la suite locale **séquentiellement**. Pour chaque étape, capture la sortie complète (stdout + stderr). Ne t'arrête pas au premier échec — exécute **toutes** les étapes même si l'une échoue.

| # | Etape | Commande | Répertoire |
|---|-------|----------|------------|
| 1 | **Lint backend (Ruff)** | `python -m ruff check .` | `backend/` |
| 2 | **Tests backend (pytest)** | `python -m pytest tests/ -m "not e2e" -v --tb=long` | `backend/` |
| 3 | **Lint frontend (ESLint)** | `npm run lint` | `frontend/` |
| 4 | **Build frontend (Vite)** | `VITE_API_URL=https://example.com npm run build` | `frontend/` |

### Etape 3 — Analyse des résultats

Pour chaque étape, classe le résultat :
- **OK** : aucune erreur, aucun warning bloquant.
- **WARN** : warnings non bloquants (les lister).
- **FAIL** : erreurs bloquantes (les analyser en détail).

### Etape 4 — Diagnostic et corrections

Pour **chaque erreur** détectée (statut FAIL) :

1. **Identifie le fichier et la ligne** concernés.
2. **Lis le code source** autour de l'erreur pour comprendre le contexte.
3. **Diagnostique la cause racine** — ne te contente pas du message d'erreur, comprends *pourquoi* le code est cassé.
4. **Propose une correction** avec :
   - Le fichier et la ligne à modifier
   - Le code avant / après
   - Une explication courte de pourquoi cette correction résout le problème
5. **Applique la correction** directement dans le code.

Après avoir appliqué toutes les corrections, **relance uniquement les étapes qui avaient échoué** pour vérifier que les corrections fonctionnent. Si une correction introduit une nouvelle erreur, itère jusqu'à ce que l'étape passe (max 3 tentatives par étape).

### Etape 5 — Rapport final

Affiche un rapport structuré :

```
## Rapport /debug-local

### Résumé
| Etape | Statut | Erreurs | Corrigées |
|-------|--------|---------|-----------|
| Ruff (lint backend) | OK / FAIL | N | N |
| Pytest (tests backend) | OK / FAIL | N | N |
| ESLint (lint frontend) | OK / FAIL | N | N |
| Build Vite (frontend) | OK / FAIL | N | N |

### Corrections appliquées
- `chemin/fichier.ext:ligne` — description courte de la correction

### Erreurs non résolues
- `chemin/fichier.ext:ligne` — description du problème + piste de résolution manuelle

### Warnings
- Liste des warnings non bloquants à traiter ultérieurement
```

## Règles

- **Ne modifie que ce qui est nécessaire** pour faire passer les tests. Pas de refactoring, pas d'amélioration cosmétique.
- **Préserve le style existant** du code (indentation, conventions de nommage, imports).
- **Ne supprime jamais un test** pour faire passer la suite — corrige le code source, pas les tests.
- **Ne désactive jamais une règle de lint** (pas de `# noqa`, `// eslint-disable`, `# type: ignore`) sauf si c'est un faux positif évident et documenté.
- **Tests e2e exclus** : ils nécessitent des services externes (Supabase) et ne font pas partie de cette vérification locale.
- Si une erreur nécessite un changement d'architecture ou une décision produit, signale-la dans "Erreurs non résolues" au lieu de la corriger.
- **Rédige en français.**
