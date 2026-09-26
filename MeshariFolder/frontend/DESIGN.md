# Venv design system

Short version: the home board is a floor plan of a shared workplace, so
the whole visual system borrows from technical drawings — hairline
borders, a faint grid, small tick-mark tags — instead of the usual
rounded-card, soft-shadow SaaS look. This is the one idea everything
else follows from.

## Color

Two themes, one token system — dark was the only option through Stage 2;
light mode (below) adds a second value for each token rather than a
parallel system, so every component that already reads color through a
CSS variable themes for free.

### Dark (default)

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
| `accent-ink` | `#e8a33d` | accent used as bare text/icon color (same as `accent` here — already ~8:1 against `bg-base`) |
| `danger` | `#d9765f` | error text only (failed requests, form validation) — never a background |

Three extra colors identify the agents, used only as small tags (a dot,
a border-left, a badge) — never as a full background:

- Manager — `#e8a33d` (same as accent — the manager is the one driving action)
- Mentor — `#4fb286`
- HR — `#a78bfa`

### Light

| Token | Hex | Use |
|---|---|---|
| `bg-base` | `#eef1f5` | page background |
| `bg-surface` | `#f8fafc` | cards, panels, the board itself |
| `bg-surface-raised` | `#ffffff` | modals, dropdowns |
| `border` | `#d7dee6` | default hairline border |
| `border-strong` | `#aebac6` | hover / focus border |
| `text-primary` | `#151b22` | body and headings |
| `text-secondary` | `#4c5964` | supporting text |
| `text-muted` | `#7c8791` | placeholders, timestamps |
| `accent` | `#e8a33d` | unchanged — see note below |
| `accent-ink` | `#9c5f0e` | deepened — see note below |
| `danger` | `#b8432a` | deepened for ~5.4:1 against white (the dark-mode value is ~2:1 on light and fails as text) |
| Manager | `#9c5f0e` | same value as `accent-ink` |
| Mentor | `#22815a` | deepened from `#4fb286` |
| HR | `#6b46c1` | deepened from `#a78bfa` |

**Why `accent` and `accent-ink` split.** `accent` backs the amber button
(`bg-accent` + `text-accent-text`) — a self-contained fill+label pair
that reads fine on any page background in either theme, so it never
changes. But three spots set accent color directly on bare text/an icon
(the landing headline, a numbered label, a workspace checkmark) — the
bright dark-mode amber only clears ~2:1 against a white/near-white
page, well under the ~4.5:1 body text needs. `accent-ink` is the
theme-aware value for exactly that case: identical to `accent` in dark
mode (already high-contrast there), deepened to `#9c5f0e` (~5.2:1) in
light mode. Same logic for the three agent identity colors, which get
used as dots/badges/borders directly against the page — the dark-mode
values would wash out on white, so light mode deepens each one (still
recognizably the same hue family) rather than reusing the dark values.

Not just an inverted dark theme, on purpose: a real blueprint print is
light drafting paper with blue linework, not a dark screen — so light
mode leans into that instead of just flipping the palette, with a cool
off-white base, a soft blue-gray grid, and ink-dark text. Same
elevation logic as dark mode either way — `bg-base` → `bg-surface` →
`bg-surface-raised` gets progressively more "present" moving toward
white instead of away from black.

Don't add more colors without a reason. If a new screen seems to need a
new color, check whether an existing token already does the job first.

### Switching themes

`lib/theme.tsx`'s `ThemeProvider`/`useTheme()` toggles `<html
data-theme="light">` (absence = dark) and persists the choice to
`localStorage` (`venv-theme`). `layout.tsx` also inlines a small
blocking script in `<head>` that applies the stored value (or the OS
`prefers-color-scheme`, on a first visit) before the first paint —
without it, the page would render dark for one frame and then jump to
light, or vice versa. `components/theme-toggle.tsx` is the sun/moon
control wired into every page header; it stays blank until mounted
specifically to avoid a hydration mismatch against that same
pre-paint script.

Every color property gets a default 0.25s cross-fade on theme change
(a zero-specificity `:where()` rule in `globals.css`, so any element's
own hover-transition utility still wins) — the one animated "theme"
moment, on top of the toggle icon's own rotate/fade swap.

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
(opening a panel, submitting a task, flipping the theme toggle) — it
doesn't run on its own.

## Internationalization (English / Arabic)

Two languages sharing one string layer, same relationship as the two
color themes above: `lib/i18n/en.ts` is the type-authoritative
dictionary, `ar.ts` is typed against it (`Dictionary`, from en.ts), so
a missing or mis-shaped key fails the build instead of silently
falling back to English or a raw key string at runtime. Every page and
component reads text through `useLocale()`'s `t()` (strings),
`tPlural()` (count-dependent text — see below), or `tRaw()`
(structural data like the landing page's cycle-step cards), plus
`useAgents()` / `useStatusLabels()` / `useTrackLabels()` for the
handful of dictionaries that used to be static English `Record`s in
`lib/agents.ts` / `lib/tasks.ts` / `lib/tracks.ts`.

`lib/i18n/locale.tsx`'s `LocaleProvider` mirrors `lib/theme.tsx`
exactly: `<html lang/dir>` set by an inline anti-flash script in
`layout.tsx` before first paint (stored choice, else the browser's
`navigator.language` on a first visit, English otherwise), the
provider picks up whatever's already applied on mount, and
`components/locale-toggle.tsx` is the EN/AR control wired into every
header next to `ThemeToggle`.

**Plural handling.** Count-dependent strings use a simple `{one,
other}` pair (`n === 1` vs everything else), not full ICU plural rules
or classical Arabic's dual/few/many noun-numeral agreement. The
Arabic strings use the numeral-plus-plural-noun pattern common in
real-world Arabic software UI (matches Google/Meta/X's own Arabic
products) rather than strict classical grammar across every count
range — a deliberate, documented trade-off, not an oversight.

**RTL layout.** `dir="rtl"` flips automatically for most of the app at
zero cost: every layout here already uses plain flexbox rows with
`justify-between`/`gap`, and CSS flexbox's `row` direction is
direction-aware by default, no `row-reverse` needed anywhere. The
exceptions — anything using a *physical* CSS property — were converted
to Tailwind's logical-property utilities app-wide: `ml-/mr-` →
`ms-/me-`, `pl-/pr-` → `ps-/pe-`, `left-/right-` → `start-/end-`,
`border-l/r` → `border-s/e`, `text-left/right` → `text-start/end`. One
non-CSS exception needed a manual fix: the board's detail-panel drawer
slides in via a framer-motion `x` transform, which is a *physical*
translateX regardless of `dir` — so its off-screen X offset is flipped
explicitly based on `dir` (see the comment in `detail-panel.tsx`),
rather than relying on the logical `end-0` positioning to handle it,
which only fixes where the drawer rests, not which direction it
travels from.

**Font.** Space Grotesk and JetBrains Mono don't cover Arabic glyphs
at all, so `[dir="rtl"]` swaps the body font to **IBM Plex Sans
Arabic** — picked over rounder, friendlier options (Cairo, Tajawal)
because it's part of a coordinated multi-script superfamily built for
technical/corporate contexts, the same "geometric, a little technical"
reasoning as Space Grotesk itself. Mono-styled Arabic captions still
request JetBrains Mono first and fall back per-glyph for the Arabic
characters it lacks — a normal, unbroken fallback, not worth a second
Arabic mono font for a handful of short labels.

**Bidi embedding.** Genuinely technical content — GitHub links, email
addresses, task/agent ids, the mono `agent_type:` labels — keeps
`dir="ltr"` explicitly even inside an RTL page, the same way it stays
in Latin script regardless of language: a URL or email address doesn't
localize, and forcing it into RTL flow would scramble how slashes and
dots read.

**Deliberately out of scope for this pass** (English-only regardless
of `lang`, and worth flagging before assuming they're bugs):
- **Agent-generated content** — *(no longer out of scope: agents now
  answer in the UI's language; see `docs/AGENT_LANGUAGE.md`. The frontend
  sends `X-Venv-Language` on every request, from `<html lang>`.)*
- **Stage 2's optional-agent catalog** — the extra agents' `name`/
  `description` (Security Reviewer, Data Reviewer, etc.) come from the
  backend catalog, not `lib/i18n`, for the same reason.
- **The Mentor's rubric category labels** — written by the model, so
  they now follow the language; the keys (`correctness`, `code_quality`,
  ...) stay English.
- **The interactive agents graph** (React Flow, `flow-section.tsx`) —
  node *labels* are fully translated, but the graph's geometry (node
  x/y positions) is left unmirrored, same convention most RTL products
  use for diagrams and charts (recharts' score-trend chart in
  `/growth` is the other instance) — flipping a diagram's layout
  doesn't inherently improve RTL usability and isn't worth re-deriving
  every coordinate for.
- A handful of short, snake_case labels (`how_it_works`, `get_started`,
  `your_team`, `employee_file`, `week_`, `agent_type`, ...) are
  identical in both dictionaries on purpose — they read as system
  tokens in the mono "blueprint" furniture, not prose, the same
  category as task IDs and timestamps.



Worth writing down so nobody "fixes" this back to the default later:

- Not cream background + serif + terracotta — that's the generic
  AI-generated look right now, and terracotta specifically reads as
  "made by Claude," which we don't want here.
- Not the SaaS card kit (identical rounded cards, same soft shadow on
  everything) — hairline borders and the grid do that job instead, and
  it fits the "floor plan" idea better than a stack of cards would.
- Monospace is data-only, not a decoration on every label — that's a
  common generated-page tell we're deliberately avoiding.
