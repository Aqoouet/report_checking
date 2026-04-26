# Ikar Design System — usage skill

When working in this project:

1. **Always import the tokens.** Every design surface starts with `<link rel="stylesheet" href="../colors_and_type.css">` (adjust path). Never hard-code hex values; reference `--ikar-orange-500`, `--ink-950`, etc.
2. **Default surface is dark.** Hero, nav, footer, contact, and any "campaign" surface goes on `--ink-950` with white text. Light surfaces (`--ink-50`, `--white`) are reserved for reading-heavy sub-pages.
3. **Type pairing is non-negotiable.** Headings, nav, eyebrows, CTAs, and labels go in `--font-display` (Oswald), uppercase. Body, ledes, and tables go in `--font-sans` (PT Sans). Specs, code, and telemetry go in `--font-mono`.
4. **Orange is sacred.** It belongs to the mark, the primary CTA, eyebrow accents, and the orange dot/icon-stroke moments only. Never use orange as a large fill on light backgrounds — that role belongs to imagery.
5. **Sharp corners.** Default `--radius-sm` (4 px). Use `--radius-pill` only for floating UI (scroll-to-top FAB).
6. **Cyrillic first.** Russian copy is the source of truth; English is parallel.
7. **Numbers as statements.** Big numerals in display type (40–84 px) with a small uppercase label above in brand orange — see the stat-strip pattern in `preview/hero.html`.
8. **Iconography:** pull from `assets/icons.svg` via `<use href="...#i-name">`. 2-px stroke, 24-px grid. If the icon you need isn't in the sprite, draw it on the same grid before using.

## Components reference

`preview/` is the source of truth for every pattern. When building a new page, open the relevant card and copy its markup conventions.

| Surface | Open |
| --- | --- |
| Color tokens | `preview/colors-brand.html`, `preview/colors-neutrals.html`, `preview/colors-semantic.html` |
| Type | `preview/type-families.html`, `preview/type-scale.html` |
| Logo | `preview/logo.html` |
| Buttons | `preview/buttons.html` |
| Icons | `preview/icons.html` |
| Nav | `preview/nav-bar.html` |
| Hero | `preview/hero.html` |
| Cards | `preview/cards.html` |
| Contact + footer | `preview/contact-footer.html` |
| Spacing & radii | `preview/spacing-radii.html` |
