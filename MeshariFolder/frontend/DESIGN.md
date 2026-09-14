# Venv design system

Short version: the home board is a floor plan of a shared workplace, so
the whole visual system borrows from technical drawings — hairline
borders, a faint grid, small tick-mark tags — instead of the usual
rounded-card, soft-shadow SaaS look. This is the one idea everything
else follows from.

## Color

Dark only, on purpose — this is a workspace someone spends time in, not
a marketing page, and one consistent surface is simpler to build against
across the team.

| Token | Hex | Use |
|---|---|---|
| `bg-base` | `#10161d` | page background |
| `bg-surface` | `#182029` | cards, panels, the board itself |
| `bg-surface-raised` | `#1f2933` | modals, dropdowns — anything sitting above a panel |
| `border` | `#2b3946` | default hairline border |
| `border-strong` | `#3b4c5c` | hover / focus border |
| `text-primary` | `#edeff2` | body and headings |
| `text-secondary` | `#8a97a6` | supporting text |
| `text-muted` | `#5c6773` | placeholders, timestamps |
| `accent` | `#e8a33d` | the one signal color — primary buttons, active states, notifications |
| `danger` | `#d9765f` | error text only (failed requests, form validation) — never a background |

Three extra colors identify the agents, used only as small tags (a dot,
a border-left, a badge) — never as a full background:

- Manager — `#e8a33d` (same as accent — the manager is the one driving action)
- Mentor — `#4fb286`
- HR — `#a78bfa`

Don't add more colors without a reason. If a new screen seems to need a
new color, check whether an existing token already does the job first.

## Type

Two fonts, both self-hosted via `@fontsource` (no Google Fonts network
call at runtime — one less external dependency, works offline):

- **Space Grotesk** — everything you read: headings, body text, buttons,
  labels. Geometric and a little technical, which fits.
- **JetBrains Mono** — reserved for genuinely technical content only:
  task IDs, timestamps, GitHub links, review scores. Not used for
  regular labels just to look "techy" — that reads as decoration.

## Layout

- The home board and any full-bleed surface uses `.bg-blueprint-grid`
  (a faint 32px grid) — it's texture from the floor-plan idea, not
  decoration, so keep it subtle.
- Flat surfaces, hairline borders, small border-radius (4-6px). No drop
  shadows, no gradients as decoration.
- Reading screens (task detail, reviews, profile) are left-aligned with
  a comfortable line length. The home board canvas is its own thing —
  content lives on nodes, not in columns.

## Motion

One deliberate moment, not scattered hover effects everywhere: when the
home board first loads, the agent nodes and their connections to the
Employee File draw themselves in briefly, like a plan being sketched.
Everywhere else, motion only answers something the user just did
(opening a panel, submitting a task) — it doesn't run on its own.

## Why not the obvious defaults

Worth writing down so nobody "fixes" this back to the default later:

- Not cream background + serif + terracotta — that's the generic
  AI-generated look right now, and terracotta specifically reads as
  "made by Claude," which we don't want here.
- Not the SaaS card kit (identical rounded cards, same soft shadow on
  everything) — hairline borders and the grid do that job instead, and
  it fits the "floor plan" idea better than a stack of cards would.
- Monospace is data-only, not a decoration on every label — that's a
  common generated-page tell we're deliberately avoiding.
