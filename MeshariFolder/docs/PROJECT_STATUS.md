# Project Status — Venv

> **Stage 1 — final state (submission).** Everything below the spec note is
> historical build log; this block is the current summary.
>
> **Backend** (FastAPI + SQLAlchemy, Postgres or sqlite): auth, CV intake,
> the full weekly-cycle flow (Manager plans a project → one big task/week →
> 5 subtasks released one at a time → Mentor reviews each, iteratively →
> end-of-week Manager progress + HR behavioral evaluation → next week),
> plus a home-dashboard aggregation endpoint and a task-free meeting-room
> chat with each agent. Models: Organization, User, EmployeeFile, Project,
> Week, Task, TaskMessage, Review, ChatMessage. Verified by **5 smoke suites,
> 127 checks total**, all passing (`smoke_test.py` 20, `_agents` 19,
> `_weekly_cycle` 17, `_orchestration` 56, `_meeting` 15).
>
> **Frontend** (Next.js + React Flow): landing page, `/board` home dashboard
> (focus, stats, week progress, interactive agents graph), `/workspace`
> (Jira-style task rail + detail + per-task agents discussion), `/meeting`
> (direct agent chat), `/growth` (HR view), `/onboarding/cv`, `/logout`. All
> wired to the real backend — no mock data. Clean production build + lint.
>
> **Known open items** (documented, intentionally out of Stage 1 scope):
> curated task bank vs. LLM-improvised subtasks, finalized Mentor rubric,
> CV file upload (currently paste), Alembic migrations, and whether
> `needs_changes` needs its own board column. See "Not built yet" below.

_Last updated: Sep 2026 — the weekly-cycle flow from
`docs/STAGE1_PRODUCT_FLOW.md` is now fully built, schema AND orchestration:
`Project`, `Week`, `Task` deadline/lateness fields, `Review.kind`/`week_id`,
iterative Mentor review, and `backend/app/agents/weekly_cycle.py`'s state
machine that actually bootstraps a Project/Week, releases subtasks one at a
time, and runs the end-of-week cascade (Manager's progress review, then
HR's behavioral review) before rolling into the next week. All of it hangs
off the existing `POST /agents/manager/assign-task` — no new endpoint
needed for the core loop. Read `docs/STAGE1_PRODUCT_FLOW.md` for the full
picture; every open question there is now resolved, confirmed with Meshari
directly (not just a working default)._

## Where things stand right now

**Backend: built, tested, running — schema + orchestration + agent logic all in.**
- Schema live: `Organization`, `User`, `EmployeeFile`, `Task`, `TaskMessage`,
  `Review`, `Project`, `Week` (`organization_id` nullable everywhere, so
  Stage 3 multi-tenancy is additive later)
- `Task` gained `week_id`, `deadline`, `submitted_at`, `completed_at`, and a
  computed `is_late` property. `Review` gained `kind` (`task_review` /
  `week_progress` / `behavioral` / `skills_rollup`) and `week_id`.
  `TaskOut`/`ReviewOut` surface all of it, and `Project`/`Week` are now
  created and advanced for real — see the orchestration bullet below and
  `GET /projects/me`.
- JWT auth, task board CRUD with status transitions, per-task threaded messages,
  CV intake endpoint
- `EmployeeFile` auto-created per user at registration — the shared context
  object all three agents read/write
- Verified with `smoke_test.py` (20 checks), `smoke_test_agents.py` (19
  checks), `smoke_test_weekly_cycle.py` (17 checks, the Project/Week/Task
  schema + the needs_changes bounce-back, exercised directly via the ORM),
  and `smoke_test_orchestration.py` (56 checks, the real thing
  end to end through the API — bootstrap, idempotency, all 5 subtasks,
  the full end-of-week cascade, landing correctly on week 2). All four
  pass together against sqlite; `smoke_test.py` was originally verified
  against real Postgres too.
- Local dev database: `docker compose up -d` from repo root
- Confirmed running locally via `uvicorn app.main:app --reload` →
  `http://localhost:8000/docs`

**Agent logic (`backend/app/agents/`) — weekly-cycle orchestration new this round.**
- LLM: Anthropic Claude (`ANTHROPIC_API_KEY` + `LLM_MODEL` in `.env`,
  default `claude-sonnet-5`). Orchestration is a plain custom router
  (`orchestrator.py`) plus a small state machine (`weekly_cycle.py`), not a
  framework (CrewAI was considered — not worth the dependency at this scale).
- **Manager** — introduces the graduate's main `Project` once
  (`create_project`), plans each `Week` as a big task + exactly 5 subtasks
  with deadlines decided upfront against the Saudi Sun-Thu workweek
  (`plan_week`, `app/scheduling.py`), hands out one subtask at a time
  (`release_next_subtask` — no LLM call, the plan's already decided),
  replies in the task thread (`respond_in_thread`), and writes the
  end-of-week progress review (`submit_week_progress`).
- **Mentor** — reads a submitted task's real public `github_link` (via a
  new unauthenticated `github_client.py`), writes a structured `Review`
  (verdict + 4-category rubric + inline comments, matching the frontend's
  proposed shape in `reviews.ts`), and moves the task to `reviewed` only on
  `approved` — `needs_changes` sends it back to `in_progress` for
  resubmission (iterative review).
- **HR** — `run_rollup` rolls up Mentor review history into `EmployeeFile`
  (skills, strengths, growth areas, summary) plus a standalone
  `skills_rollup` `Review`. `run_behavioral_review` (new) writes the
  end-of-week behavioral evaluation — attendance/absence/lateness are
  computed in code from existing timestamps ("meaningful progress": a
  status change, submission, or resubmission counts as a day present,
  confirmed with Meshari), and the LLM only writes the narrative + a
  consistency rating on top of those numbers.
- **`weekly_cycle.get_next_task`** — the state machine tying it together.
  Bootstraps a Project + Week 1 on the graduate's very first
  `assign-task` call; returns the same in-flight subtask if one's still
  open (idempotent, no duplicates); releases the next one once the
  current is approved; and once all 5 are approved, runs the cascade
  (Manager's `submit_week_progress` then HR's `run_behavioral_review`,
  that order), closes the Week, and rolls straight into the next one —
  all in the same call, so the graduate always gets a task back.
- Endpoints: `POST /agents/manager/assign-task` (now does all of the
  above, not just a flat task), `POST /agents/manager/reply/{task_id}`,
  `POST /agents/mentor/review/{task_id}`, `POST /agents/hr/rollup`; reads
  via `GET /projects/me` (new — the Project + all its Weeks), `GET
  /tasks/{id}/review`, `GET /users/me/employee-file`, `GET /users/me/reviews`.
- Tested with `smoke_test_agents.py` (basic per-agent sanity) and, more
  importantly, `smoke_test_orchestration.py` (the full cycle end to end —
  see above). All four smoke tests pass together, no regressions.
- Full detail and what's still open (task bank content, rubric
  finalization, CV parsing, `needs_changes` board visibility, frontend
  wiring) in `backend/app/agents/README.md`.

**Frontend: all four screens plus CV intake, wired to the real backend — no mock data left.**
- Next.js (App Router, TypeScript, Tailwind v4), a real design system
  documented in `frontend/DESIGN.md` — a dark "blueprint" look (hairline
  borders, faint grid, one accent color) instead of a generic SaaS theme.
  Fonts self-hosted via `@fontsource`, no external font CDN call.
- **Auth is real**: `/login` (toggles sign-in/register), `lib/auth-context.tsx`
  (`AuthProvider`, `useAuth`, `useRequireAuth` — redirects signed-out
  visitors to `/login`, `refreshUser()` to re-sync after something changes
  server-side mid-session). JWT in `localStorage`. Every other page is
  auth-gated.
- **`lib/api.ts`** is the one place that knows the backend's wire format
  (snake_case, matching `schemas.py` exactly) — every page/lib function
  goes through it, nothing calls `fetch` directly elsewhere.
- **`/onboarding/cv`** — paste-a-CV step, shown once right after
  registration (Manager handles a missing CV gracefully, so skipping is a
  real option, not a dead end). Copy adapts to an "update" framing if
  `user.hasCv` is already true, reachable anytime from the board's
  Employee File panel. `UserOut` gained a `has_cv` boolean (derived from
  `cv_raw_text`, not the raw text itself) specifically so returning users
  aren't re-prompted every login.
- `/board` — React Flow canvas: a You node connects to Manager, Mentor, and
  HR, all three feeding into a shared Employee File node (dashed, animated
  edges — the shared-memory differentiator made visible, not just claimed).
  Clicking a node opens a slide-over detail panel. Header shows the
  signed-in user's email + a logout button. Employee File panel now shows
  CV status with an Add/Update link.
- `/tasks` — kanban board (To do / In progress / Submitted / Reviewed),
  fetching real tasks. "Ask manager for a task" button calls
  `POST /agents/manager/assign-task`. Submitting a task auto-triggers the
  Mentor's review (`POST /agents/mentor/review/{id}`) — no separate "run
  review" button. Posting a thread message auto-triggers the Manager's
  reply (`POST /agents/manager/reply/{id}`) — it's a live conversation now,
  not a one-way comment box. `TaskDetailPanel` shows which agent is
  currently working (`busy: "review" | "reply" | null`).
- `/tasks/[id]/review` — Mentor's review, a client component fetching
  the real task + `GET /tasks/{id}/review`. **The rubric categories are
  still a first pass, not a finalized contract** — see
  `backend/app/agents/README.md`'s "Still open" section.
- `/growth` — HR's view: real `GET /users/me/employee-file` +
  `GET /users/me/reviews`, a "Ask HR for a review" button
  (`POST /agents/hr/rollup`), and an empty state before any reviews exist
  (`employeeFile.summary` is `null` until HR's first rollup — see
  `hr.py`'s storage note for why skills/strengths/growth-areas are `{}`
  until then, `{"items": [...]}` after).
- One new design token: `danger` (`#d9765f`), documented in `DESIGN.md`,
  used only for error text — the app can now actually fail (bad login,
  server down, an agent call erroring) and needed a way to show that.
- Hit and fixed a newer ESLint rule (`react-hooks/set-state-in-effect`)
  false-positive on the standard "fetch on mount" pattern across three
  files — targeted, commented `eslint-disable-next-line`s rather than
  restructuring working code; see the comments at each site for why.
- Verified end-to-end against the real running backend at every stage
  (not just `npm run build`/`lint`): register → login → `/users/me` →
  task create/detail/status/messages → employee-file/reviews reads → CV
  submit flipping `has_cv`. Every response matched the TypeScript wire
  types field-for-field, including CORS preflight from `localhost:3000`.

**Repo:** https://github.com/MeshMoh506/VirtualWorkEnviroment_AI — `main`
had 13 merged PRs as of the frontend-wiring update (repo scaffold + VS
Code config, backend + Docker Postgres, project status doc, frontend
scaffold + design system, home board, task board, the React Flow height
fix + docs update, Mentor's review view, a docs refresh, HR's growth
view, agent logic, frontend wiring). This round adds the CV upload flow
on a new branch, not yet merged — see below.

Since then, `main` also picked up the weekly-cycle spec doc and the
weekly-cycle schema (16 merged PRs as of this update). This round's
orchestration work (`weekly_cycle.py`, `scheduling.py`, the Manager/HR
additions, `GET /projects/me`) is on `feature/weekly-cycle-orchestration`,
not yet merged.

**Not built yet:**
- **Frontend isn't wired to the weekly-cycle flow yet.** `GET /projects/me`
  exists and returns the Project + all its Weeks, but nothing in
  `frontend/` calls it — the home board's node UI still shows the old flat
  model. The core task-board loop (`POST /agents/manager/assign-task` etc.)
  still works unchanged from the frontend's point of view — it just does
  more behind the scenes now — but there's no UI yet for "which week am I
  on" / "what's this week's big task" / the end-of-week reviews.
- Concrete task bank content, finalized Mentor rubric (current one is a
  first pass, not team-agreed) — still open, see
  `backend/app/agents/README.md`'s "Still open" section. Confirmed this
  round: for now, subtasks stay LLM-improvised (not sourced from a bank) —
  company-uploaded tasks and Phase 3's user-uploaded-project flow are
  separate, later, out-of-scope paths.
- **Whether `needs_changes` needs its own visible board state** — right
  now it just sends the task back to `in_progress`, indistinguishable from
  a task that was never reviewed. Product call, not made yet.
- CV file upload (PDF/docx) — currently paste-only; no file parsing
  exists anywhere in the stack
- Alembic migrations — schema currently created via `create_all` on
  startup; the schema has changed shape twice now (weekly-cycle schema,
  then nothing new needed for orchestration itself) without a migration
  tool, worth doing before it changes again
- **Attendance computation is only tested at the "everything happens in
  the same second" level** — `smoke_test_orchestration.py` proves the
  formula is right, but hasn't (and can't, as a smoke test) exercise a
  week that actually spans multiple real days.

## Repo map

```
.
├── docker-compose.yml   one-command local Postgres
├── backend/             FastAPI — done, tested, running
│   └── app/agents/       Manager/Mentor/HR + weekly_cycle.py's state
│                         machine — implemented, see its README
│                         (app/scheduling.py, alongside, is the Saudi
│                         workweek date math it depends on)
├── frontend/             Next.js + React Flow — all 4 screens (home
│                         board, task board, review, growth) plus CV
│                         intake, wired to the flat task-board API (not
│                         yet to the weekly-cycle Project/Week endpoints)
└── .vscode/              shared editor config
```

## Working approach — follow this in every chat, every session

1. New piece of work → new branch off `main`: `feature/...`, `fix/...`,
   `chore/...`, `docs/...`.
2. Commit in small, logical chunks with imperative messages ("add X", not
   "added X"). Code gets brief comments explaining *why*, not just what.
3. Test before committing — don't commit something known-broken.
4. Push the branch, open a PR on GitHub, merge into `main`.
5. `main` stays deployable at all times.

## Conventions established so far (keep these consistent going forward)

- Every core table carries a nullable `organization_id`, even where Stage 1
  doesn't use it.
- `EmployeeFile` is the one shared context object — new agent logic should
  read/write its existing fields (`skills_json`, `strengths_json`,
  `growth_areas_json`, `summary_text`) rather than inventing a parallel
  structure.
- `TaskMessage.sender_type` is derived, not set directly: pass `agent_type`
  in the request to record it as an agent message, omit it for a user
  message.
- Secrets live in `.env` (gitignored), never committed; `.env.example` is
  the template.
- Frontend: hairline borders + a faint grid instead of rounded cards and
  shadows, one accent color, monospace reserved for actual technical
  content (IDs, timestamps, links) rather than every label — see
  `frontend/DESIGN.md` before adding new UI.

## Handoff notes for whatever's next (starting in a new chat)

**The weekly-cycle flow is fully built now** — schema and orchestration
both. `docs/STAGE1_PRODUCT_FLOW.md` has the full picture; every open
question in it is resolved, confirmed with Meshari (not a working
default). The natural next piece is **wiring the frontend to it**: the
home board doesn't show Project/Week context at all yet (`GET
/projects/me` is ready and waiting), and there's no UI distinguishing
"this week's big task" from the flat task list, or surfacing the
end-of-week `week_progress`/`behavioral` reviews anywhere. The core
task-board loop itself needs no frontend changes — it already calls
`POST /agents/manager/assign-task` and gets a real subtask back, same
shape as before.

If that's blocked or deprioritized, the smaller standalone items are
still open:

- **Task bank + rubric**: the Manager currently improvises subtasks from
  scratch each time (confirmed as the intended behavior for now — see
  `STAGE1_PRODUCT_FLOW.md`), and the Mentor's 4-category rubric
  (`correctness`, `code_quality`, `testing`, `documentation` — see
  `backend/app/agents/tools.py`'s `SUBMIT_REVIEW_TOOL`) is a first pass,
  not team-agreed. This is mostly a content/product decision, not code —
  good for a session with the whole team weighing in, not just backend.
- **`needs_changes` board visibility** — currently silent (task just goes
  back to `in_progress`). Decide whether it needs its own visible state.
- **CV file upload**: right now `/onboarding/cv` is paste-only text. Real
  file upload (PDF/docx) would need client-side text extraction (no
  parsing exists on the backend — `POST /users/me/cv` just stores
  whatever text it's given) before this is worth doing.
- `frontend/DESIGN.md` has the full design rationale — read it before
  adding new colors, fonts, or components.

## Reference: full API surface

- Backend base URL in dev: `http://localhost:8000`. Interactive schema
  for every endpoint at `/docs`.
- Auth: `POST /auth/register` → `{email, password, full_name}`. `POST
  /auth/login` → **form-encoded** `username`/`password` (OAuth2 password
  flow) → `{access_token, token_type}`. `GET /users/me` (includes
  `has_cv`).
- CV: `POST /users/me/cv` → `{cv_raw_text}` → returns `UserOut`.
- Tasks: `GET /tasks`, `POST /tasks` (manual/admin — the app itself never
  calls this; real tasks come from the Manager agent), `GET /tasks/{id}`,
  `PATCH /tasks/{id}/status`, `POST /tasks/{id}/messages`,
  `GET /tasks/{id}/review`.
- Agents: `POST /agents/manager/assign-task` (bootstraps/advances the
  weekly cycle — see `docs/STAGE1_PRODUCT_FLOW.md`), `POST
  /agents/manager/reply/{task_id}`, `POST /agents/mentor/review/{task_id}`,
  `POST /agents/hr/rollup`.
- Projects: `GET /projects/me` (new — the graduate's active `Project` with
  all its `Week`s nested).
- `GET /users/me/employee-file`, `GET /users/me/reviews`.
- All of this except `GET /projects/me` is already wired into
  `frontend/src/lib/api.ts`, `auth-context.tsx`, `tasks.ts`, `reviews.ts`,
  and `employee-file.ts` — `/projects/me` is new this round and not yet
  called from anywhere in the frontend.
