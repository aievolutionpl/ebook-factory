# Ebook Factory — Codex Workspace Design Contract

## Brief

- **Audience:** a single private operator running a production pipeline, not a public marketing audience.
- **Product:** an AI-assisted ebook factory that creates, runs, inspects, and downloads bounded artifact packages.
- **Personality:** Claude Code / Codex technical workspace: precise, compact, legible, and operational. Swiss / International structure is dominant; restrained terminal brutalism appears through dark panels, hairline rules, monospace-like command affordances, and direct labels.
- **Non-goals:** no publishing, payments, fake analytics, decorative stats, confetti, mascots, emoji, gradients, webfonts, or external UI dependencies.
- **Primary action:** contextual project action (`start`, `pause`, `resume`, `download`) plus global `+ New`, both always reachable in the relevant viewport.
- **AI disclosure:** compact and visible. It states the panel/output is AI-assisted and requires human review.

## Design Tokens

CSS values must resolve through tokens in `:root`; component rules should not introduce ad hoc color values. Tokens below are authoritative.

### Color

| Token | Value | Use |
|---|---|---|
| `--color-bg` | `#0b0e13` | App background |
| `--color-surface` | `#12161d` | Cards, controls, rows |
| `--color-surface-raised` | `#1a2029` | Dialogs, composer, raised controls |
| `--color-surface-subtle` | `#10141b` | Inspector / low-emphasis panels |
| `--color-border` | `#262d38` | Hairline rules |
| `--color-border-strong` | `#3a4453` | Strong control borders |
| `--color-text` | `#eef1f5` | Primary text |
| `--color-text-muted` | `#a6b0bf` | Secondary copy and labels |
| `--color-text-faint` | `#7b8797` | Disabled/tertiary text |
| `--color-accent` | `#4f7cff` | Primary actions, focus, selected state |
| `--color-accent-hover` | `#6a8fff` | Primary hover |
| `--color-accent-text` | `#04070d` | Text on accent |
| `--color-success` | `#3ecf8e` | Completed |
| `--color-warning` | `#f2b84b` | Paused/attention |
| `--color-danger` | `#ff6b6b` | Failed/destructive |
| `--color-danger-surface` | `rgba(255, 107, 107, 0.12)` | Error background |
| `--color-info` | `#7fb4ff` | Running |
| `--color-backdrop` | `rgba(0, 0, 0, 0.64)` | Modal backdrop |
| `--color-accent-surface` | `rgba(79, 124, 255, 0.16)` | Selected project row |
| `--color-success-surface` | `rgba(62, 207, 142, 0.14)` | Positive low-emphasis fills |
| `--color-warning-surface` | `rgba(242, 184, 75, 0.14)` | Unsaved-change badge |

### Scale

- Spacing: `--space-1: 4px`, `--space-2: 8px`, `--space-3: 12px`, `--space-4: 16px`, `--space-5: 24px`, `--space-6: 32px`, `--space-7: 48px`, `--space-8: 64px`.
- Radius: `--radius-sm: 6px`, `--radius-md: 8px`, `--radius-lg: 12px`.
- Motion: `--duration-fast: 120ms`, `--duration-base: 200ms`, `--ease-standard: cubic-bezier(0.2, 0, 0, 1)`.
- Type: system sans only. `--text-xs: 12px`, `--text-sm: 13px`, `--text-base: 15px`, `--text-lg: 18px`, `--text-xl: 24px`, `--text-2xl: 32px`.
- Workspace widths: `--rail-width: 280px`, `--inspector-width: 300px`, `--composer-height: 64px`.

## Layout

- **Desktop >=1150px:** three columns: left project rail, center active workspace, right inspector. Bottom command composer is fixed and maps only to existing project actions.
- **Tablet >=768px and <1150px:** single dominant workspace with the project rail as an explicit drawer and inspector below the workspace flow.
- **Mobile around 390px:** single workspace flow. Project rail behaves as the project drawer area, inspector becomes a bottom sheet, contextual action is sticky, and horizontal overflow is forbidden.
- **Center workspace:** header with mode/title/status/contextual action, progress cluster, and tabs for Workflow, Files, Text quality, Activity, Settings.
- **Right inspector:** outputs, sources, recent activity, and download link when completed.
- **Provider context:** project header and inspector both show the selected provider and local availability.

## Components

- **Project rail:** search, status filters, `+ New`, loading skeleton, empty and error copy.
- **New project dialog:** accessible four-screen flow built from a 3-step wizard plus review: Goal & format, Audience/brand, Sources/settings, Review before submit. Existing field IDs and upload behavior are preserved.
- **Writing setup:** the audience/brand step carries the writing style (`practical` / `narrative` / `expert`) and the humanizer level (`off` / `light` / `standard` / `strong`). Both are editable later in Settings and are echoed in the project header, so the reader of the workspace always knows how the book was written.
- **Text quality panel:** an AI-trace score (0-100, lower is more human) with a written grade, before/after comparison when the humanize stage ran, readability figures, the detected signals with an actionable hint each, and a per-chapter breakdown. The score is never communicated by colour alone: the dial carries the number, the grade in words and an `aria-label`.
- **Provider selector:** part of Sources/settings. `demo` remains the default; Codex CLI and Claude Code are opt-in local tools with setup guidance and availability status.
- **Command palette:** Ctrl/Cmd+K opens; ArrowUp/ArrowDown moves active command; Enter executes; Esc closes; focus returns to the trigger.
- **Command composer:** visible desktop/tablet command strip. Commands are limited to existing `start`, `pause`, `resume`, `cancel`, and `download`.
- **Feedback:** toast region for action results, explicit error banners, skeleton loading, and empty states. Toasts collapse repeats into a counter, carry a dismiss control, and errors stay on screen longer than confirmations.
- **Connection pill:** header status with dot plus label (`Połączono`, `Serwer nie odpowiada`, `Brak połączenia`); the last sync time lives in its tooltip. Label-only on mobile is not allowed to disappear into colour — the dot is decorative.
- **Stage strip and timing line:** one segment per stage under the progress bar, plus `Etap n z m`, current stage duration and a remaining-time estimate derived from this project's own completed stage durations.
- **Busy state:** any control that fires a request takes `.is-busy`, keeps its footprint, and is disabled for the duration, so no action can be submitted twice.
- **Shortcuts dialog:** `?` or the header button opens the full key map; every shortcut listed there is implemented.
- **Command palette availability:** commands the current project status cannot accept are ranked last, marked `aria-disabled`, and state the reason instead of failing at the API.
- **File rows:** format badge from the real extension, per-group size totals, copy-path action, and preview for text, images and PDF.
- **Settings dirty state:** unsaved edits raise a badge, enable `Przywróć`, and are confirmed before switching project or leaving the page.

## Accessibility

- Landmarks remain `header`, `nav[aria-label]`, `main`, `aside[aria-label]`, `footer`.
- Every form control with an ID has a bound label.
- All touch targets are at least 44px.
- Status is never color-only: every chip includes a readable label and semantic color.
- `:focus-visible` is mandatory and uses the accent token.
- `prefers-reduced-motion: reduce` disables transitions and animations.
- No horizontal overflow at mobile, tablet, or desktop breakpoints.
- Background refreshes must not steal focus: list and timeline re-renders restore focus to the same project or stage.
- On mobile the workspace header keeps its controls on one row and gives the title the full width below them.

## Runtime behaviour

- Polling is a recursive timeout, never an interval: one request is in flight at a time. It runs fast while a project is running, backs off otherwise, and stops entirely while the tab is hidden.
- Durations and relative timestamps tick locally between refreshes; only project state comes from the API.
- The browser tab title carries the progress percentage while a project runs.
- Filters, sorting, theme and preview wrapping persist per browser; nothing about a project is stored client-side.
