# Ebook Factory — Design Contract

## Brief

- **Audience:** a single private operator (Chris / JARVIS-style assistant), not a public customer. The panel is a cockpit, not a marketing surface.
- **Product:** an AI production tool that runs a multi-stage pipeline and produces real, downloadable sales artifacts.
- **Personality:** precise, editorial, calm. No hype copy, no mascot, no celebratory confetti. Status is communicated in words and color, never ambiguity.
- **Density:** medium-high. The operator wants to see pipeline state (11 stages × N projects) at a glance without excessive whitespace, but never so dense that tap targets shrink below 44px.
- **Primary action:** "Nowy ebook" — always reachable, always the visually heaviest interactive element on screen.
- **Emotional target:** control and confidence. The UI should feel like a mission-control panel: current state is always legible, every control's effect is predictable, failures are explicit and never silently swallowed.
- **Dominant style:** Swiss / International Typographic Style — strict grid, one display sans family, generous but disciplined whitespace, color used only for status meaning, not decoration. Restrained editorial support: small caps labels, hairline rules, numeric stage indices — evokes a print production ledger, not a SaaS dashboard.

## Design tokens

All values below are the only allowed colors/spacing/radii/shadows/durations in `styles.css`. No ad hoc magic numbers.

### Color (WCAG AA verified against its stated use)

| Token | Value | Use | Contrast |
|---|---|---|---|
| `--color-bg` | `#0b0e13` | App background | — |
| `--color-surface` | `#12161d` | Card / panel surface | — |
| `--color-surface-raised` | `#1a2029` | Modal / raised surface | — |
| `--color-border` | `#262d38` | Hairline rules, card borders | — |
| `--color-border-strong` | `#3a4453` | Focus-adjacent structural borders | — |
| `--color-text` | `#eef1f5` | Primary text on `--color-bg`/`--color-surface` | 15.1:1 |
| `--color-text-muted` | `#a6b0bf` | Secondary text, meta labels | 6.1:1 |
| `--color-text-faint` | `#7b8797` | Disabled / tertiary text | 5.3:1 |
| `--color-accent` | `#4f7cff` | Primary action, links, focus ring | 4.6:1 on `--color-bg` |
| `--color-accent-text` | `#04070d` | Text on `--color-accent` fill | 8.9:1 |
| `--color-success` | `#3ecf8e` | Stage/project completed | 7.4:1 |
| `--color-warning` | `#f2b84b` | Paused / attention | 9.7:1 |
| `--color-danger` | `#ff6b6b` | Failed / destructive | 5.6:1 |
| `--color-info` | `#7fb4ff` | Running / in progress | 7.9:1 |

### Spacing scale (4px base)

`--space-1: 4px`, `--space-2: 8px`, `--space-3: 12px`, `--space-4: 16px`, `--space-5: 24px`, `--space-6: 32px`, `--space-7: 48px`, `--space-8: 64px`.

### Radius

`--radius-sm: 6px` (chips, inputs), `--radius-md: 10px` (cards), `--radius-lg: 16px` (modal/dialog).

### Shadow

`--shadow-card: 0 1px 2px rgba(0,0,0,0.4)`, `--shadow-modal: 0 16px 48px rgba(0,0,0,0.55)`.

### Motion

`--duration-fast: 120ms`, `--duration-base: 200ms`, easing `--ease-standard: cubic-bezier(0.2, 0, 0, 1)`. All motion is disabled under `prefers-reduced-motion: reduce`.

### Type

Single family: system sans stack (`-apple-system, "Segoe UI", Inter, sans-serif`) for both UI and editorial labels — no webfont network fetch. Scale: `--text-xs: 12px`, `--text-sm: 13px`, `--text-base: 15px`, `--text-lg: 18px`, `--text-xl: 24px`, `--text-2xl: 32px`. Small-caps, letter-spaced labels (`text-transform: uppercase; letter-spacing: 0.06em`) mark structural/editorial elements (stage numbers, section eyebrows) per the Swiss-ledger reference.

## Layout

- **Mobile (390px) / tablet (768px):** single column. Bottom navigation bar with two destinations (Projekty, Nowy ebook) plus a scrollable project list; tapping a project pushes the detail view full-screen with a back control.
- **Desktop (1150px, 1440px):** persistent left sidebar (project list + "Nowy ebook") and a detail panel filling the remaining width. No bottom nav.
- Grid breakpoints at 768px and 1150px; content max-width caps at 1440px, centered beyond that.

## Accessibility

- Landmarks: `header`, `nav[aria-label]`, `main`, `footer`.
- Every form control has a bound `<label>`; icon-only buttons carry `aria-label`.
- Visible `:focus-visible` ring using `--color-accent`, 2px offset, on every interactive element — never suppressed.
- Status is never color-only: every status chip pairs color with a text word (`Ukończono`, `W trakcie`, `Wstrzymano`, `Błąd`).
- `prefers-reduced-motion: reduce` disables all transitions/animations.
- A persistent AI-disclosure bar states the panel and its output are AI-assisted demo tooling — always visible, not dismissible.

## Explicitly out of scope for this screen

Publishing, payments, multi-user accounts — the panel only creates, runs, inspects and downloads.
