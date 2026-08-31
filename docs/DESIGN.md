# DESIGN — LucidFence Design System

This document defines the design identity of LucidFence: the visual language, typography, color palette, contrast requirements, and what does NOT belong in the UI.

## Identity

LucidFence is a serious security and compliance tool. The design reflects:
- **Clarity over decoration** — Every element has a purpose; nothing is ornamental
- **Trust through restraint** — No gradients, no shadows, no "wow" effects
- **Readability at scale** — Operators read dashboards all day; typography must not fatigue

The personality is: calm, precise, authoritative. Think: Bloomberg terminal crossed with Apple's accessibility-first design.

## Typography

### Primary font stack

```
-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif
```

With this hierarchy:

| Level | Size | Weight | Line height | Use |
|-------|------|--------|-------------|-----|
| H1 | 28px | 600 | 1.3 | Page title |
| H2 | 22px | 600 | 1.35 | Section heading |
| H3 | 18px | 600 | 1.4 | Subsection |
| Body | 15px | 400 | 1.6 | Default text |
| Small | 13px | 400 | 1.5 | Labels, captions, metadata |
| Mono | 13px | 400 | 1.5 | Code, IDs, technical values |

### Typography rules

- **No font-family mixing** in body content — one family per context
- **Italic for emphasis only** — never for structural purposes
- **All-caps for labels and status pills only** —  uppercase for 3-5 character labels
- **Monospace for:** device IDs, policy names in code view, timestamps, raw config

### What we don't use

- Serif fonts (too decorative for a security tool)
- Variable fonts (no proven readability gain)
- Icon fonts (use SVG icons instead)

## Color palette

### Semantic colors (not decorative)

| Role | Token | Hex | Usage |
|------|-------|-----|-------|
| Background primary | `--bg-primary` | `#0a0a0b` | Main background |
| Background secondary | `--bg-secondary` | `#18181b` | Cards, elevated surfaces |
| Background tertiary | `--bg-tertiary` | `#27272a` | Hover states, active items |
| Border | `--border` | `#3f3f46` | Dividers, outlines |
| Border strong | `--border-strong` | `#52525b` | Focus rings, emphasis |

| Role | Token | Hex | Usage |
|------|-------|-----|-------|
| Text primary | `--text-primary` | `#fafafa` | Main body text |
| Text secondary | `--text-secondary` | `#a1a1aa` | Labels, secondary info |
| Text muted | `--text-muted` | `#71717a` | Disabled, placeholder |
| Text link | `--text-link` | `#60a5fa` | Links, interactive text |

| Role | Token | Hex | Usage |
|------|-------|-----|-------|
| Success | `--success` | `#22c55e` | Compliant, healthy, complete |
| Warning | `--warning` | `#f59e0b` | At-risk, attention needed |
| Danger | `--danger` | `#ef4444` | Non-compliant, critical, error |
| Info | `--info` | `#3b82f6` | Neutral information, not action |

### Color rules

- **Semantic meaning, not decoration** — green means "good", red means "bad", never just "looks nice"
- **Sufficient contrast** — all text meets WCAG AA (4.5:1 for body, 3:1 for large)
- **Never use color alone** — pair color with icon/label for status (colorblind-safe)

## What does NOT enter the UI

### Absolutely not

- **Photography** — No stock photos, no device images, no hero shots
- **Illustrations** — No cartoonish graphics, no mascot characters
- **Gradients** — Flat colors only; gradients are decoration
- **Animations beyond functional transitions** — No entrance animations, no parallax, no bounce
- **Rounded corners beyond 8px** — Squareness signals precision; 8px max for cards/buttons
- **Drop shadows** — Elevation is conveyed by background color change, not shadow

### Exceptions

- **Functional transitions** (150ms max): hover state changes, expand/collapse, modal open/close
- **Status pulse** (2s loop, 1px border glow): only for critical alerts requiring immediate attention

## Component principles

### Buttons

- **Primary** (filled, `--bg-secondary` background, `--text-primary`): the main action on a screen
- **Secondary** (border only, `--border`): less important actions, alternative paths
- **Danger** (red border + text `--danger`): destructive actions (wipe, delete, revoke)
- **Disabled** (`--text-muted`, `cursor: not-allowed`): not available in current context

### Cards

- Background: `--bg-secondary`
- Border: `--border`
- Padding: 16px
- Border radius: 8px max
- No shadow

### Tables

- Row background: `--bg-primary` (default), `--bg-secondary` (hover)
- Header: `--bg-tertiary`, text `--text-secondary`, uppercase, 13px
- Borders between rows: `--border`
- Zebra striping: **NOT used** (distracting at scale)

### Forms

- Input background: `--bg-tertiary`
- Input border: `--border`, focus: `--border-strong`, text: `--text-primary`
- Label: `--text-secondary`, 13px, above input
- Error state: `--danger` border + text
- Helper text: `--text-muted`, 12px, below input

### Status pills

- Uppercase, 11px, bold, border-radius: 4px
- Background: subtle (10% opacity of semantic color)
- Text: semantic color (full opacity)
- Examples: "COMPLIANT", "AT RISK", "NON-COMPLIANT", "UNKNOWN"

### Navigation

- Top nav: horizontal, text links, `--text-secondary` default, `--text-primary` + underline on active
- Sidebar: vertical, same style, with section headers in uppercase
- Breadcrumbs: `--text-muted` with `>` separator, last item `--text-primary`

## Accessibility

- **Minimum contrast ratio:** 4.5:1 for body text, 3:1 for large text (WCAG AA)
- **Focus indicators:** `--border-strong` outline, 2px, offset 2px
- **Keyboard navigation:** All interactive elements reachable via Tab, Enter/Space activates
- **Screen reader:** Semantic HTML, aria-labels where needed, no meaningful content in images
- **Motion:** Respect `prefers-reduced-motion`; disable all non-functional transitions

## Responsive behavior

- **Desktop-first** — LucidFence is primarily used on desktop/laptop by operators
- **Minimum width:** 1024px designed; functional down to 768px
- **Below 768px:** Sidebar collapses to top nav; tables scroll horizontally; cards stack vertically
- **Mobile:** Functional but not optimized; the tool is not designed for phone use

## Branding

### Logo usage

The LucidFence logo is a simple geometric mark: a hexagon (representing containment/boundary) with a location pin integrated. Use only the approved SVG at `/static/logo.svg`.

### Logo rules

- **Never modify the logo** — no recoloring, no reshaping, no combining with other marks
- **Clear space:** logo height worth of space on all sides
- **Minimum size:** 24px height in UI contexts, 160px in full-page contexts

### Name usage

- "LucidFence" (capital L, capital F, no space variation)
- "LucidFence" is the product name; "LucidFence Project" refers to the open-source effort
- Don't abbreviate to "LF" in user-facing content

## File structure

```
static/
├── app.js              # Main application logic
├── i18n.js             # Internationalization
├── logo.svg            # Logo mark
├── dashboard.html      # Local dashboard SPA
├── cloud.html          # Cloud showcase (public demo data)
└── styles/
    └── main.css        # Design system tokens + component styles
```

The design tokens above are defined in `static/styles/main.css` as CSS custom properties. Any visual change goes through this file and is verified by `verify.py` (doc links check) and the browser smoke tests.

---

*Last updated: 2026-01-15. Maintained by the Growth and product loops.*
