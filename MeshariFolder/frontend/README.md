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
`backend/README.md` and `docker-compose.yml` at the repo root.

## Screens

- `/login` — sign in / register (toggle). `/onboarding/cv` — one-time
  CV paste step after registration, skippable, reachable again later
  from the board's Employee File panel.
- `/` — landing page: scroll-snapping sections (hero, the three agents,
  the weekly loop, CTA).
- `/board` — home dashboard, two columns: left is your current focus,
  stat row, week-progress strip, and live agent cards; right is the
  interactive agents graph (You -> Manager / Mentor / HR -> shared
  Employee File), clicking a node opens a detail drawer.
- `/workspace` — the Jira-style workspace: task list rail (grouped by
  status) · task detail (submit / review actions) · a per-task agents
  discussion panel. "Ask manager" triggers the Manager; submitting a
  GitHub link auto-triggers the Mentor's review; a thread message
  auto-triggers the Manager's reply. `/tasks` redirects here.
- `/meeting` — direct chat room with each agent (Manager / Mentor / HR),
  not tied to any task; one persisted conversation per agent.
- `/tasks/[id]/review` — Mentor's structured review for one task.
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
See `backend/README.md` for exact request/response shapes, or
`/docs` on the running backend for live interactive schemas.

## Design system

See `DESIGN.md` before adding new colors, fonts, or components — the
short version is: hairline borders and a faint grid instead of rounded
cards and shadows, one accent color, monospace reserved for actual data
(IDs, timestamps) rather than every label.

## Structure

```
src/app/              App Router pages (see Screens above)
src/app/globals.css   design tokens (colors, fonts) — see DESIGN.md
src/components/       board/ (nodes, panels, task card), rubric-bar
src/lib/               api.ts (backend client), auth-context.tsx,
                       tasks.ts / reviews.ts / employee-file.ts (domain
                       types + fetch functions), agents.ts, format.ts
```

## What's next

The backend is about to grow a weekly-cycle flow (big task → subtasks,
deadlines, end-of-week evaluation) — see `docs/STAGE1_PRODUCT_FLOW.md`
at the repo root. That'll mean new screens/states here too once the
backend side lands; nothing to do on the frontend yet.
