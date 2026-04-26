# Ikar Design System

> Visual language for ГК «ИКАР» — engineering and aerospace holding.
> Sourced from **ikarcenter.ru** corporate identity.

---

## 01 · Brand context

ГК «ИКАР» is a leading engineering-and-manufacturing holding — the design and production center for aviation systems, components, and unmanned aerial systems (UAS), with a 20-year history of work for Russian and international clients. Founded in 2002 as a joint venture between Airbus and the Kaskol Investment Group, today it counts more than 1,000 specialists.

Visually this means: **industrial, technical, monumental.** Black surfaces. Heavy condensed Cyrillic display type. A single brand-orange accent that operates as the mark, the CTA, and the icon stroke. No decoration; flat, rectilinear, engineering-minded.

## 02 · Content fundamentals

- **Cyrillic-first.** Russian copy is canonical. English is provided as a parallel translation.
- **Tone is corporate-technical.** Short clauses, capitalised section titles, concrete numerals (years, projects, kilograms, hours of flight).
- **No marketing slop.** No emoji, no exclamation marks, no metaphors that aren't grounded in engineering.
- **Numbers are statements.** «20 лет», «1 000+», «200+» — set in display type at large scale; they replace adjectives.

## 03 · Visual foundations

| Token | Use |
| --- | --- |
| `--ikar-orange-500` | Brand mark, primary CTA, eyebrow accent, icon highlights |
| `--ink-950` / `--ink-900` | Hero, nav, footer, contact blocks |
| `--ink-50` / `--white` | Sub-pages, technical reading, forms |
| `--font-display` (Oswald) | All headings, nav, eyebrows, CTAs — uppercase |
| `--font-sans` (PT Sans) | Body copy, ledes, tables |
| `--font-mono` (JetBrains Mono) | Specs, telemetry, code, captions |
| `--radius-sm` (4 px) | Buttons, badges, cards |
| `--radius-pill` | Reserved for floating UI (scroll-to-top FAB) |

## 04 · Iconography

A 24-px grid, 2-px stroke, square caps, no rounded ends. Two layers:

- **Functional system icons** (chevron, menu, close, arrow, search) — neutral colour.
- **Domain marks** (aircraft, drone, document, gear) — same grid; used at section heads or in product cards.
- **Contact triplet** (pin / phone / mail) — always rendered in brand orange.

`assets/icons.svg` ships the full sprite. Reference symbols by `<use href="assets/icons.svg#i-name">`.

## 05 · File map

```
colors_and_type.css       — design tokens (CSS variables) + type styles
assets/
  logo.svg                — full lockup (planet + ring + ИКАР + descriptor)
  logo-mark.svg           — mark only, for favicons / small contexts
  icons.svg               — 24-px sprite
  hero.png                — original hero illustration (ARCHIVED — not used in current system)
preview/                  — one HTML card per design-system asset
ui_kits/
  web-app/                — internal report-checking tool (legacy violet — DEPRECATED, kept for reference)
```

## 06 · Caveats & next steps

- **Fonts:** Oswald + PT Sans are the closest free analogs to the site's heavy condensed grotesque + humanist sans. If the team has the actual licensed faces (likely PF DinDisplay Pro or similar), drop them into `fonts/` and update the `--font-display` and `--font-sans` variables.
- **Logo:** SVG is a faithful reconstruction of the planet+ring mark from the screenshots. A vector-perfect master from the team would replace `assets/logo.svg`.
- **The internal report-checking UI kit** (`ui_kits/web-app/`) was built against the previous violet styling. It is now **deprecated** but kept on disk so existing screenshots remain referenceable; rebuild it against the new tokens before continuing development.
- **Photography direction is not yet codified.** The corporate site relies heavily on dark, technical imagery (CAD screenshots, circuit boards, aircraft components). A photo-treatment guide is the most important next addition.
