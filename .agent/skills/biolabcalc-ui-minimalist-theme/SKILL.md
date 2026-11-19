---
name: biolabcalc-ui-minimalist-theme
description: Enforce the BioLabCalc minimalist CSS design system, color-customization tokens, WCAG AAA contrast, hairline geometry, and print-ready layouts across ELN, interactive viewers, and exported reports. Use when styling, auditing, or refactoring frontend interfaces, CSS custom properties, or printable HTML/PDF views.
---

# biolabcalc-ui-minimalist-theme

Govern and enforce the BioLabCalc minimalist visual design language across the Electronic Lab Notebook (ELN), interactive scientific visualizers (`interactive_gel.py`, `interactive_plasmid.py`), protocol generators, and lab report HTML/PDF exports.

## Core Design Principles

1. **Zero Clutter & Hairline Geometry**:
   - Avoid heavy drop shadows, neon gradients, or thick decorative borders.
   - Use clean 1px hairline dividers with token `var(--hairline)` or `var(--border)`.
   - Generous whitespace, compact typography (system sans-serif fonts), and clear hierarchy.

2. **Semantic CSS Tokens**:
   Consume standard CSS variables from `theme_tokens.css`:
   - `--bg`: Main application background canvas.
   - `--surface` / `--card-bg`: Elevated card/panel containers.
   - `--ink` / `--text-primary`: Primary body and heading text.
   - `--ink-muted` / `--text-muted`: Secondary metadata, labels, and captions.
   - `--hairline` / `--border`: Structural 1px separation lines.
   - `--accent`: Brand interactive accent (buttons, active tabs, focus rings).

3. **Built-in Presets & Custom Color**:
   - `minimal-light`: High-clarity light bench paper aesthetic.
   - `minimal-slate`: Low-glare dark laboratory bench theme.
   - `bench-paper`: Warm cream-tinted physical laboratory notebook look.
   - `colorblind-safe`: Okabe-Ito barrier-free palette with accessible data visualization hues.
   - Support arbitrary custom accent colors via `ThemeConfig.accent_hex` with automated fallback to WCAG-compliant contrast.

4. **WCAG AAA Accessibility**:
   - Primary text must maintain $\ge 7:1$ contrast against the underlying background.
   - Secondary/muted text must maintain $\ge 4.5:1$ contrast.
   - Interactive elements must possess clear `:focus-visible` outlines.

5. **Print & Archival Readiness (`@media print`)**:
   - Force pure white background (`#ffffff`) and dark text (`#000000`) when printing.
   - Hide interactive chrome: navigation bars, modals, action buttons, live tickers, theme selectors via `.no-print`.
   - Prevent page breaks inside table rows, cards, or charts (`break-inside: avoid`).
   - Every printable report and notebook view must include an accessible `window.print()` trigger.
