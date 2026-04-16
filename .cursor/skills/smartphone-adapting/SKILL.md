# Smartphone Adapting — Adaptation intelligente pour mobile

## Objectif

Adapter complètement un site/logiciel web pour smartphone en prenant des **décisions UX stratégiques** — pas un simple ajout de media queries, mais une refonte réfléchie de l'expérience mobile : réorganisation des layouts, navigation repensée, interactions tactiles, hiérarchie visuelle adaptée, et suppression ou transformation des éléments qui ne fonctionnent pas sur petit écran.

## Quand utiliser ce skill

- L'utilisateur tape **`/smartphone-adapting`**, demande d'**adapter pour mobile**, de **rendre responsive**, d'**optimiser l'UX smartphone**, ou attache explicitement ce skill.
- Une page ou un composant est signalé comme **cassé / inutilisable sur mobile**.
- Après création d'une feature desktop-first, pour ajouter l'adaptation mobile.

## Principes UX stratégiques (obligatoires)

L'agent ne se contente **jamais** d'ajouter des classes responsive mécaniquement. Il applique ces principes :

### 1. Mobile ≠ Desktop rétréci

- **Repenser la hiérarchie** : sur mobile l'attention est séquentielle, pas panoramique. Prioriser le contenu principal, reléguer le secondaire.
- **Simplifier** : si un élément desktop n'apporte pas de valeur sur mobile (décoration, colonnes redondantes, infos tertiaires), le masquer (`hidden sm:block`) ou le déplacer.
- **Agrandir les zones tactiles** : minimum 44×44px pour tout élément cliquable (recommandation Apple/Google).

### 2. Navigation mobile-first

- **Sidebar → Drawer ou bottom nav** : transformer les sidebars fixes en drawer glissant (hamburger) ou navigation basse selon le contexte.
  - App avec navigation fréquente entre sections → **bottom navigation** (max 5 items).
  - App avec navigation secondaire → **hamburger drawer** avec overlay.
- **Sticky header** : garder le contexte visible (titre de page, actions principales) dans un header fixe compact.
- **Pas de hover** : tout effet `:hover` doit avoir un équivalent tactile (`:active`, tap, long-press). Supprimer les tooltips hover-only sur mobile.

### 3. Layouts adaptatifs intelligents

- **Grilles** : `grid-cols-1` par défaut, élargir avec `sm:grid-cols-2`, `md:grid-cols-3`, etc.
- **Flex direction** : `flex-col` par défaut, `sm:flex-row` quand pertinent.
- **Espacement** : réduire les paddings/margins sur mobile (`p-3 sm:p-6`, `gap-3 sm:gap-6`).
- **Typographie** : adapter les tailles (`text-xl sm:text-2xl md:text-3xl`). Le texte doit rester lisible sans zoom.
- **Images et médias** : `w-full` + `max-w-*` pour éviter le débordement. Utiliser `aspect-ratio` pour stabiliser le layout.

### 4. Formulaires et inputs

- **Inputs pleine largeur** sur mobile (`w-full`).
- **Labels au-dessus** des champs (pas à côté) sur mobile.
- **`type` HTML correct** : `type="email"`, `type="tel"`, `type="number"` pour déclencher le bon clavier.
- **Boutons d'action principaux** : pleine largeur et bien visibles en bas de formulaire.
- **Éviter les modales complexes** sur mobile → préférer les pages pleines ou les bottom sheets.

### 5. Performance mobile

- **Lazy loading** images et composants lourds hors viewport.
- **Pas de JS lourd** au chargement initial si évitable.
- **Animations légères** : préférer `transform` et `opacity` (GPU-accelerated). Réduire ou supprimer les animations complexes sur mobile via `prefers-reduced-motion`.

### 6. Gestes et interactions tactiles

- **Swipe** pour navigation entre onglets/cartes quand pertinent.
- **Pull-to-refresh** si l'app affiche des données dynamiques.
- **Scroll momentum** natif : ne pas bloquer le scroll (`overflow-auto` pas `overflow-hidden` sur le body mobile).
- **Pas de double-tap zoom non voulu** : meta viewport correcte (`width=device-width, initial-scale=1`).

## Workflow d'exécution

### 1. Audit du viewport meta

Vérifier dans le `<head>` (layout.tsx ou équivalent) :

```html
<meta name="viewport" content="width=device-width, initial-scale=1" />
```

Si absent ou incorrect, corriger immédiatement.

### 2. Inventaire des composants à adapter

- Lister les composants/pages concernés.
- Pour chacun, noter : **état actuel** (responsive ? cassé ?) et **décision UX** (masquer, transformer, réorganiser, garder tel quel).
- Présenter cet inventaire à l'utilisateur avant d'implémenter.

### 3. Stratégie de navigation mobile

Analyser la navigation existante et décider :

| Pattern desktop | Transformation mobile recommandée |
|----------------|----------------------------------|
| Sidebar fixe avec items fréquents | Bottom nav (≤5 items) + drawer pour le reste |
| Sidebar fixe avec beaucoup d'items | Hamburger drawer overlay |
| Tabs horizontaux | Scroll horizontal ou bottom nav |
| Navbar top avec beaucoup de liens | Hamburger menu |
| Breadcrumbs longs | Tronquer avec « ... » ou masquer |

Implémenter la solution choisie avec **transition animée** (slide-in pour drawer, etc.).

### 4. Adaptation composant par composant

Pour chaque composant, dans cet ordre :

1. **Layout** : passer en `flex-col` / `grid-cols-1` par défaut.
2. **Espacement** : réduire paddings/margins (`p-3 sm:p-6`).
3. **Typographie** : adapter les tailles de texte.
4. **Éléments interactifs** : agrandir les zones tactiles, supprimer hover-only.
5. **Contenu** : masquer le secondaire, simplifier les tableaux (cards ou listes sur mobile).
6. **Modales/Overlays** : transformer en pages full-screen ou bottom-sheet si trop petites.

### 5. Tableaux → Cards/Listes

Les tableaux HTML larges sont **inutilisables** sur mobile. Stratégie :

- **Peu de colonnes (≤3)** : garder le tableau avec scroll horizontal (`overflow-x-auto`).
- **Beaucoup de colonnes** : transformer en **liste de cards** sur mobile avec les données clés visibles et les secondaires en expandable.

```tsx
{/* Desktop: tableau */}
<div className="hidden sm:block">
  <table>...</table>
</div>
{/* Mobile: cards */}
<div className="sm:hidden space-y-3">
  {items.map(item => <MobileCard key={item.id} {...item} />)}
</div>
```

### 6. Tests visuels

Après chaque lot de modifications :

- Vérifier à **375px** (iPhone SE), **390px** (iPhone 14), **428px** (iPhone 14 Plus).
- Vérifier le mode **paysage**.
- Tester le scroll, les interactions tactiles, les transitions.
- Vérifier qu'aucun contenu ne déborde horizontalement (`overflow-x` indésirable sur le body).

### 7. Synthèse

Résumer en français :
- Composants adaptés et décisions UX prises.
- Pattern de navigation mobile choisi et pourquoi.
- Points d'attention restants.

## Breakpoints Tailwind de référence

| Préfixe | Min-width | Cible |
|---------|-----------|-------|
| _(défaut)_ | 0px | Mobile portrait |
| `sm:` | 640px | Mobile paysage / petite tablette |
| `md:` | 768px | Tablette |
| `lg:` | 1024px | Desktop |
| `xl:` | 1280px | Grand desktop |

**Approche** : coder **mobile-first** (styles par défaut = mobile), puis enrichir avec `sm:`, `md:`, `lg:`.

## Patterns Tailwind courants

```html
<!-- Conteneur responsive -->
<div class="px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">

<!-- Grille adaptive -->
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">

<!-- Texte responsive -->
<h1 class="text-2xl sm:text-3xl lg:text-4xl font-bold">

<!-- Bouton tactile pleine largeur mobile -->
<button class="w-full sm:w-auto min-h-[44px] px-6 py-3">

<!-- Masquer/montrer selon le device -->
<div class="hidden md:block">Desktop only</div>
<div class="md:hidden">Mobile only</div>

<!-- Stack vertical mobile → horizontal desktop -->
<div class="flex flex-col sm:flex-row gap-3 sm:gap-4">
```

## Décisions UX à documenter

Pour chaque adaptation non triviale, l'agent doit **expliquer sa décision** dans la synthèse :

- _"Sidebar transformée en bottom nav car l'app a 4 sections principales accédées fréquemment"_
- _"Tableau des crédits transformé en cards mobile car 6 colonnes ne tiennent pas sur 375px"_
- _"Modal de connexion transformée en page plein écran car les champs + CTA ne tiennent pas dans une modale mobile"_

## Anti-patterns

- Ajouter `sm:` / `md:` sans réfléchir à l'UX (responsive mécanique).
- Laisser une sidebar fixe sur mobile qui mange 50% de l'écran.
- Garder un tableau à 8 colonnes avec juste un `overflow-x-auto`.
- Texte trop petit pour être lu sans zoom (< 14px effectif).
- Boutons/liens trop petits pour être tapés au doigt (< 44px).
- Oublier le meta viewport.
- Tester uniquement en mode portrait.
- Utiliser des effets hover comme seul feedback interactif.
