# Audit de sécurité complet du SIRH

Tu es un expert en cybersécurité applicative. Réalise un **audit de sécurité complet** de l'application SIRH (SaaS RH multi-tenant).

## Périmètre de l'audit

Analyse **tout** le code source et la configuration en couvrant les 3 axes ci-dessous.

---

### AXE 1 — Sécurité côté client (front-end & navigateur)

Vérifie et rapporte l'état de :

- **Stockage des tokens** : JWT dans `localStorage` vs cookies `httpOnly`/`Secure`/`SameSite`
- **Protection XSS** : échappement des entrées utilisateur, dangerouslySetInnerHTML, sanitization
- **Protection CSRF** : tokens CSRF, headers `SameSite`, double-submit cookie
- **Validation des entrées** : schémas Zod, React Hook Form, sanitization avant envoi
- **Exposition de données sensibles** : tokens, IDs, rôles stockés en clair dans `localStorage`
- **Gestion des erreurs** : messages d'erreur exposant des détails internes au client
- **Content Security Policy (CSP)** : headers CSP dans la config nginx/frontend
- **Dépendances frontend** : packages npm avec vulnérabilités connues (`npm audit`)
- **Source maps en production** : vérifier si les source maps sont exposées
- **Redirections ouvertes** : paramètres d'URL non validés utilisés pour des redirections

---

### AXE 2 — Sécurité côté serveur / éditeur (back-end, API, infra)

Vérifie et rapporte l'état de :

- **Authentification** : validation JWT, expiration, révocation, flux login/logout/reset
- **Autorisation & RBAC** : vérification des rôles sur chaque endpoint, IDOR, escalade de privilèges
- **Isolation multi-tenant** : RLS Supabase, `set_session_company`, header `X-Active-Company`
- **Injection SQL** : requêtes paramétrées, module Copilot text-to-SQL (validation `only_select_allowed`), RPC `execute_sql`
- **Rate limiting** : protection brute-force sur login, reset password, endpoints sensibles
- **CORS** : origines autorisées, wildcards, `allow_credentials` avec `allow_origins=["*"]`
- **Headers de sécurité** : HSTS, X-Frame-Options, X-Content-Type-Options, Permissions-Policy
- **Gestion des secrets** : `.env` commité, `sa-key.json`, clés en dur, rotation des secrets
- **Logging sensible** : `print()` avec emails, tokens, mots de passe dans les logs
- **Erreurs exposées** : `str(e)` renvoyé au client, stack traces, détails internes
- **Upload de fichiers** : types autorisés, taille max, path traversal, stockage sécurisé
- **Génération PDF** : injection de template (Jinja2/WeasyPrint), SSRF
- **Scraping** : SSRF, exécution de code via URLs arbitraires
- **Docker** : utilisateur non-root, images minimales, secrets dans les layers
- **CI/CD** : secrets GitHub Actions, permissions des workflows, artifacts exposés
- **Dépendances backend** : packages Python avec CVE connues
- **Validation des entrées** : Pydantic sur tous les endpoints, types stricts

---

### AXE 3 — Sécurité des données & conformité (clients & RGPD)

Vérifie et rapporte l'état de :

- **Données personnelles** : inventaire des données RH stockées (salaires, IBAN, numéros sécu, adresses)
- **Chiffrement au repos** : chiffrement des colonnes sensibles en base
- **Chiffrement en transit** : HTTPS forcé, TLS 1.2+, certificats
- **Accès aux données** : qui peut voir quoi (matrice rôle × donnée)
- **Journalisation / audit trail** : traçabilité des accès et modifications aux données sensibles
- **Droit d'accès / suppression** : mécanismes RGPD (export, suppression, anonymisation)
- **Rétention des données** : politique de conservation, suppression automatique
- **Sauvegardes** : chiffrement des backups, accès restreint
- **Sous-traitants** : Supabase, OpenAI (envoi de données RH au LLM), Google Cloud, Brevo

---

## Format de sortie attendu

### 1. Résumé exécutif

Un paragraphe de synthèse avec le niveau de maturité global (Critique / Insuffisant / Acceptable / Bon / Excellent).

### 2. Tableau des problèmes identifiés

Pour **chaque** problème trouvé, une ligne dans ce tableau :

| # | Problème | Axe | Criticité | Fichier(s) concerné(s) | Solution recommandée | Difficulté |
|---|----------|-----|-----------|------------------------|---------------------|------------|
| 1 | ... | Client / Serveur / Données | Critique / Haute / Moyenne / Basse / Info | `path/to/file:line` | Description de la solution | Facile / Moyenne / Difficile |

Trie le tableau par **criticité décroissante** (Critique en premier).

### 3. Points positifs

Liste les mesures de sécurité déjà en place et bien implémentées.

### 4. Plan d'action prioritaire

Liste les **5 actions les plus urgentes** avec un ordre de priorité clair.

---

## Instructions d'exécution

1. **Lis réellement les fichiers** — ne suppose pas, vérifie le code source.
2. **Couvre les 3 axes** — ne te limite pas au backend.
3. **Sois exhaustif** — mieux vaut un faux positif qu'un vrai négatif manqué.
4. **Donne des chemins de fichiers précis** avec numéros de ligne.
5. **Évalue la difficulté** de chaque solution (Facile = <1h, Moyenne = 1-4h, Difficile = >4h ou changement d'architecture).
6. **Rédige en français.**
