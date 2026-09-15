# Venv frontend

Next.js (App Router, TypeScript, Tailwind v4) + React Flow for the
node-based home board. Wired to the real backend — no mock data.

## Running it

```bash
npm install
cp .env.example .env.local     # optional, defaults to localhost:8000
npm run dev
```

Open http://localhost:3000. The backend runs separately — see
`backend/README.md` and `docker-compose.yml` at the repo root. Register
a new account to see the Stage 2 onboarding wizard (existing accounts
skip straight to `/board`).

## Screens

- `/login` — sign in / register (toggle).
- `/onboarding/cv` — the Stage 2 onboarding wizard, shown once after
  registration: CV file upload → agent-generated follow-up questions
  (skippable) → track suggestion with an override → optional-agent
  roster (suggested + editable) → own-project choice. "Go through it
  again" on the completed-state screen resets and redoes it.
- `/orientation` — shown once right after onboarding: your project
  (bootstrapped automatically if you let the Manager plan it), your full
  team, and a short how-it-works walkthrough. One button into `/board`.
- `/` — landing page: scroll-snapping sections (hero, the agents, the
  weekly loop, CTA).
- `/board` — home dashboard, two columns: left is your current focus,
  stat row, week-progress strip, and live agent cards (default three
  plus any optional agents you added); right is the interactive agents
  graph (You → your whole team → shared Employee File), scaling
  automatically to however many agents you have. Clicking a node opens a
  detail drawer.
- `/workspace` — the Jira-style workspace: task list rail (grouped by
  status) · task detail (a submit form: GitHub link, notes, and
  file/image attachments) · the agents-meeting thread, which renders the
  Mentor's review and — if you added any specialists — the full
  roundtable discussion (each agent's turn, then the Manager's
  synthesis), each correctly attributed and colored. "Ask manager"
  triggers the Manager; submitting triggers the Mentor's review (and the
  roundtable behind it); a thread message auto-triggers the Manager's
  reply. `/tasks` redirects here.
- `/meeting` — direct chat with any agent on your actual team, not just
  the fixed three — the picker rail reflects your real roster.
- `/tasks/[id]/review` — Mentor's structured review for one task, plus
  the submission's text/attachments alongside the GitHub link.
- `/growth` — HR's view: Employee File + review timeline, "Ask HR for a
  review" button.
- `/logout` — sign-off confirmation screen.

## Talking to the backend

Base URL in dev: `http://localhost:8000` (`NEXT_PUBLIC_API_BASE_URL` in
`.env.local` to override). **`lib/api.ts` is the one place that knows the
backend's wire format** (snake_case, matching `backend/app/schemas.py`
exactly) — every page/lib function goes through it, nothing calls
`fetch` directly elsewhere. Auth is JWT bearer, stored in `localStorage`
via `lib/auth-context.tsx` (`AuthProvider`, `useAuth`, `useRequireAuth`).
Attachment downloads (`lib/attachments.ts`) fetch as an authenticated
blob rather than a plain `<img>`/`<a>`, since those can't attach the
bearer token the download endpoint needs. See `backend/README.md` for
exact request/response shapes, or `/docs` on the running backend for
live interactive schemas.

## Design system

See `DESIGN.md` before adding new colors, fonts, or components — the
short version is: hairline borders and a faint grid instead of rounded
cards and shadows, one accent color, monospace reserved for actual data
(IDs, timestamps) rather than every label. **Dark-theme only right
now** — light mode is queued up next, see `docs/PROJECT_STATUS.md`'s
handoff section; expect this doc to need a real token-strategy pass, not
a quick toggle, before that lands.

## Structure

```
src/app/              App Router pages (see Screens above)
src/app/globals.css   design tokens (colors, fonts) — see DESIGN.md
src/components/       board/ (nodes, detail panel), dashboard/ (flow-section,
                       agent-cards), workspace/ (task-workspace, agents-meeting,
                       attachment-list), rubric-bar
src/lib/               api.ts (backend client, one file, every wire type),
                       auth-context.tsx, tasks.ts / reviews.ts / projects.ts /
                       team.ts / meeting.ts (domain types + fetch functions),
                       agents.ts / agent-display.ts / tracks.ts (display
                       metadata), attachments.ts, format.ts
```

## What's next

Not a frontend-only list — see `docs/PROJECT_STATUS.md`'s "Handoff"
section for the full picture, but the frontend-relevant pieces: reworking
the onboarding/orientation experience further, Arabic language support
(no i18n infrastructure exists here yet — this is a real architecture
decision, not a drop-in library), and a light-mode theme built on top of
the existing CSS-variable token system in `DESIGN.md`.
