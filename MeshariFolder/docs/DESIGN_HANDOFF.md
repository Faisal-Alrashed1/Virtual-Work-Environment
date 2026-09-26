# Design handoff — for a design collaborator working outside this codebase

Written for someone (or another AI) helping redesign Venv's pages
without direct access to the repo. Gives just enough to make changes
that fit — the actual design rules, the full page map, and the shared
building blocks already in place — without dumping the whole codebase.

## Read this first: the design system already has a point of view

Venv is **not** a generic SaaS product — it's a simulated engineering
company. The UI should feel like a tool professionals use, not a
marketing site. Concretely:

- **Palette**: near-white/near-black neutrals with ONE accent color —
  **amber** (`#e8a33d`), used sparingly for primary buttons, active
  states, and notifications — plus three fixed agent identity colors
  (Manager = amber, same as the accent; Mentor = green `#4fb286`; HR =
  purple `#a78bfa`) used only as small dots/left-borders, never as
  full-surface fills. No gradients, no glassmorphism, no drop shadows
  anywhere.
- **Typography**: **Space Grotesk** for everything you read — headings
  AND body text, not a separate pairing — IBM Plex Sans Arabic for
  Arabic locale, JetBrains Mono reserved for genuinely technical
  content only (IDs, timestamps, status tags, counts). Monospace is
  data-only, never used as a decorative flourish.
- **Structure**: hairline 1px borders, small border-radius (4-6px,
  never pill-shaped buttons), a faint 32px background grid texture
  (`.bg-blueprint-grid`) used sparingly for hero/section moments,
  generous whitespace over dense card grids.
- **Explicitly rejected, on purpose — do not reintroduce these**: a
  cream background with serif display type and a terracotta accent
  (that combination specifically reads as "generic AI-generated
  design" and was deliberately avoided); identical rounded SaaS cards
  with a soft shadow on everything; any full-bleed dark/saturated
  slide-style background.
- **Bilingual, RTL-aware**: every layout must work mirrored for Arabic.
  Use logical CSS properties (`ms-`/`me-`/`ps-`/`pe-`/`start-`/`end-`,
  not `ml-`/`mr-`/`left-`/`right-`/`border-l`/`border-r`/`text-left`/
  `text-right`) so a redesign doesn't silently break in RTL. One
  gotcha worth knowing: a framer-motion `x` transform (e.g. a slide-in
  drawer) is a *physical* translateX regardless of `dir` — logical
  positioning alone won't flip which direction it travels from, so
  that needs an explicit `dir`-based sign flip (see the existing
  pattern in `components/board/detail-panel.tsx`).

## Files to give a design collaborator

For general context (give these once, at the start):

1. **`frontend/DESIGN.md`** — the full design system explanation this
   summary is condensed from. The authoritative source.
2. **`frontend/src/app/globals.css`** — the actual CSS custom
   properties: every color token (light and dark mode), font stacks,
   spacing/radius scale. The real values, not descriptions of them.
3. **This file** (`docs/DESIGN_HANDOFF.md`) — the page map below, so a
   redesign of one page can stay consistent with what every other page
   already does.
4. **`frontend/src/components/theme-toggle.tsx`** and
   **`frontend/src/components/locale-toggle.tsx`** — small, finished
   reference components showing the established small-icon-button
   pattern (`h-8 w-8`, hairline border, no shadow) used everywhere.
5. **`frontend/src/components/nav/account-menu.tsx`** and
   **`frontend/src/components/nav/icon-link.tsx`** — the shared header
   controls every page's header already uses; a redesign should reuse
   these, not invent new ones.

For a **specific page** redesign, also give:

6. That page's own file (e.g. `frontend/src/app/board/page.tsx`) and
   whatever it imports from `frontend/src/components/` — grep the
   page's `import` lines for the exact list.

## The full page map (20 routes)

**Student side:**
- `/` — public landing page (marketing, not logged in)
- `/login` — sign in / register (student and company both start here,
  or `/company/register` directly)
- `/board` — the student's home/dashboard after login: focus task,
  week strip, team, activity feed
- `/workspace` — the actual task workspace: task detail, submission,
  chat with agents about the current task
- `/meeting` — 1:1 Meeting Room with any agent on the roster, plus the
  shared Team Room
- `/tasks` — flat task list (legacy Stage 1 view, still used)
- `/tasks/[id]/review` — a single task's full Mentor review detail
- `/growth` — Employee File, skills/strengths/growth areas, score
  trend chart, Career Coach check-in
- `/orientation` — a guided first-time walkthrough of how Venv works
- `/onboarding/cv` — CV upload step of the onboarding wizard
- `/profile/cv` — view/re-upload CV after onboarding is done
- `/settings` — profile, password, language/theme
- `/invitations` — a student's received company invitations, with the
  required consent notice before accepting
- `/invitations/[id]/visibility` — after accepting, the exact same
  view the company sees about that student (transparency)
- `/logout` — clears session, redirects to `/`

**Company side:**
- `/company/register` — found a new company or join an existing one
  via code
- `/company` — company dashboard: org info, job titles, join code
- `/company/job-titles/[id]` — one job title: knowledge-base uploads,
  a RAG test-search box, real projects, sending invitations
- `/company/students` — roster of everyone who accepted an invitation
- `/company/students/[invitationId]` — one student's week-by-week
  detail and reviews, from the company's side

## General-purpose prompt for redesigning any one page

Copy this, fill in the page name, and use it as-is for any page:

> I'm redesigning the **[PAGE NAME, e.g. `/growth` — the Growth page]**
> of Venv, an AI-simulated workplace platform for recent graduates
> (with a separate side for companies). I've given you the design
> system doc, the actual CSS tokens, the page map, and the shared
> header components already in use everywhere else.
>
> Please redesign this page's layout and visual hierarchy while:
> - staying strictly inside the existing design system (the palette,
>   type scale, border/radius rules, and the explicit "don't
>   reintroduce" list in the design system doc) — don't introduce new
>   colors, fonts, shadows, or a different visual language than the
>   rest of the app already uses
> - reusing the shared header components (`AccountMenu`, `IconLink`,
>   `ThemeToggle`, `LocaleToggle`) rather than inventing new ones
> - keeping every string as a translation lookup (`t("...")`), not a
>   hardcoded English string — this app is bilingual, English/Arabic,
>   with RTL layout
> - using only logical CSS properties for direction-sensitive spacing
>   (`ms-`/`me-`/`start-`/`end-`, never `ml-`/`mr-`/`left-`/`right-`)
> - keeping all existing functionality on the page intact — this is a
>   visual/layout redesign, not a feature change
>
> Give me the complete, ready-to-drop-in file (or files) — not a
> partial diff or a description of what to change. If you need
> anything about this specific page's current implementation that I
> haven't given you, tell me exactly what file or snippet you need
> and I'll provide it.

## What NOT to give a design collaborator

Skip backend code, migrations, and test files entirely — none of it is
relevant to a visual redesign and it only adds noise. If a redesign
genuinely needs to know what data a page displays (not how it looks),
describe the data in plain English rather than pasting backend schema.
