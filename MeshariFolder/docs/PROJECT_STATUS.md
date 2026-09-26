# Project Status — Venv

_Last updated: Sep 2026 — Stage 2 plus a full hardening pass, a
task-chat/Team Room/settings pass, all of Stage 3 (companies), and now
a full ten-agent roster._

> **One-paragraph summary.** Stage 1 (Manager/Mentor/HR, the weekly cycle, one
> track) and all of Stage 2 (CV-file intake with agent Q&A, six IT tracks, a
> selectable optional-agent roster, an own-project path — now with real uploaded
> materials, a guided orientation walkthrough, the Meeting Room open to any agent
> on your team, multi-modal submissions with vision review, and the agent
> roundtable) are built and merged. A full hardening pass followed: Alembic
> migrations, resumable onboarding, a visible "needs changes" state, Arabic agent
> replies, a Mentor rubric v2, a 15-seed task bank, a background roundtable, and
> protection against malformed model output on every agent tool call. Then a
> task-chat/collaboration pass: the Mentor is now the default day-to-day agent in
> a task thread (`docs/TASK_CHAT.md`); every agent conversation surface declines
> off-topic requests (`agents/guardrails.py`); a Team Room gives a shared thread
> with the whole team (`docs/TEAM_ROOM.md`); a `/settings` page
> (`docs/SETTINGS_PAGE.md`). Then all of Stage 3: company accounts
> (free-text job titles, per-rep logins with roles), a real RAG knowledge base
> (embeddings + cosine-similarity retrieval, no vector DB), a company's own real
> projects (distinct from a graduate's own project), an invite-with-enforced-
> consent flow, and a company roster with per-week reports built from the
> weekly cycle's existing reviews — see `docs/STAGE3_COMPANY_RAG.md` for the
> full write-up, including the confirmed answers to all four scoping questions
> that were open before it started. Then **a full ten-agent roster**
> (`docs/TEN_AGENTS.md`) — three new specialists (QA Engineer, UX Reviewer,
> Technical Writer) reachable everywhere the existing ones were, and Career
> Coach's long-standing gap closed with a real dedicated action (a career
> check-in that writes actual resume bullets, not just another chat reply).
> **Most recently: a deep, cross-agent read/write audit**
> (`docs/AGENT_READ_WRITE.md`) — a code audit (clean: no stubs/placeholders
> anywhere in `app/agents/`) plus a new test file held to a specifically
> higher bar than "did this return 200": does each agent's LLM call
> genuinely receive the real context it's supposed to, and does what it
> writes back genuinely round-trip correctly. Closed three real gaps —
> HR's attendance/lateness figures checked against a hand-computed exact
> answer for the first time, the roundtable's "a real conversation, not
> parallel monologues" claim verified directly, Mentor's vision path
> confirmed with an actual image. Most recently: **a real reported bug fixed**
> (`docs/CV_VALIDATION.md`) — uploading any readable file as a "CV" (an
> invoice, an essay, anything) used to be silently accepted; a wrong upload
> is now genuinely rejected at all three CV-intake points, judged by a real
> model rather than a fragile heuristic. **38 smoke suites, 970 checks, all
> passing** — genuinely **confirmed on a
> real PostgreSQL 16 instance** through the Stage 3 pass, not just SQLite: doing so
> surfaced and fixed two real deploy-breaking migration bugs that SQLite's lack of enum
> enforcement had hidden (see `docs/STAGE3_COMPANY_RAG.md`'s "The PostgreSQL
> story") — the ten-agent pass's own migration (0010) applies the same reasoning
> carefully but is **not yet re-verified against real Postgres**, per the
> steer to treat local/SQLite as the bar for this round (see `docs/TEN_AGENTS.md`'s
> "The PostgreSQL story, round two"). Frontend eslint clean, `next build` passes (20 routes).
> **Nobody has clicked through the app in a browser yet** — see "What's
> genuinely unverified" below before treating this as demo-ready.

## What's built

**Backend** (FastAPI + SQLAlchemy, SQLite dev / PostgreSQL prod, LangGraph for
onboarding and the weekly-cycle cascade):

- Auth, CV intake (file or paste), the full weekly cycle (Manager plans a
  project → one big task/week → 5 subtasks released one at a time → Mentor
  reviews each iteratively → end-of-week Manager progress + HR behavioral
  review, both consulting the Mentor directly → next week).
- Multi-modal submissions (GitHub link, text, up to 5 files/images — images go
  to the Mentor as real vision content).
- The **agent roundtable**: after the Mentor's review, any optional agents on
  the graduate's roster (Security Reviewer / Data Reviewer / DevOps) discuss
  the submission in a fixed order, then the Manager synthesizes — **now in the
  background**, so the graduate only waits for the Mentor (`docs/BACKGROUND_ROUNDTABLE.md`).
- Multi-provider LLM support (Anthropic/OpenAI/DeepSeek/Qwen) with tier-aware
  routing and automatic failover (`docs/LLM_PROVIDER_FAILOVER.md`).
- **The Manager's task bank**: 15 project seeds (2-3 per track) with four-week
  arcs; a project is based on one and adapted, every week is planned against its
  arc step, and every seed says what evidence to submit — because the Mentor
  only ever sees a repo's file list and README head, never the code itself
  (`docs/TASK_BANK.md`).
- **The Mentor's rubric v2**: anchored 1-5 scores per category, one enforced
  verdict rule (only "meets requirements" below 3 can block a task), memory of
  its own previous feedback on a resubmission (`docs/MENTOR_RUBRIC.md`).
- **Every agent tool call is hardened against malformed model output** —
  repaired where possible (a JSON-string list, a numeric string), checked
  structurally, retried on the same provider, then failed over — never a 500.
  Two separate tool-calling paths both covered: the Manager/Mentor/HR/roundtable
  path (`docs/LLM_PROVIDER_FAILOVER.md`, "Malformed tool output") and the
  onboarding graph's own path (`docs/ONBOARDING_GRAPH_HARDENING.md`) — found by
  running real models, not by any mocked test.
- **Database migrations (Alembic)** replace `create_all`; an existing dev
  database is adopted safely, an out-of-date one gets a clear startup error
  instead of a mystery crash later (`docs/MIGRATIONS.md`).
- **Onboarding survives a closed tab, a restart, or a second API worker** — state
  is saved on the `User` row and the graph thread is rebuilt from it, at zero LLM
  cost (`docs/ONBOARDING_RESUME.md`).
- **A bounced task is visible, not silent** — `Task.needs_changes`/`revision_count`,
  derived from the reviews (`docs/NEEDS_CHANGES_VISIBLE.md`).
- **Agents answer in the language the UI is showing** — one request header, two
  hooks in the LLM layer, no per-agent changes needed (`docs/AGENT_LANGUAGE.md`).
- **A graduate's own project can include real materials** — pasted notes and/or
  uploaded files, which the Manager actually plans around (`docs/STAGE2_OWN_PROJECT.md`).
- Local file storage for attachments (`app/storage.py`) — dev-scope, one box,
  not yet cloud.
- `backend/e2e_real_llm.py` — a one-command check that drives the whole demo
  path with **real** LLM keys (everything above is mocked-model tested only),
  reports what a graduate actually waits for, what got repaired/retried, and can
  save a full report of what the models produced (`--save-report`).
- **Task chat now has an agent switcher, and the Manager is scoped to the big
  picture.** The Mentor (`agents/mentor.py`'s new `respond_in_thread`) is the
  default agent in a task thread — framed as a senior engineer working the
  task day to day — rather than the Manager fielding every message. The
  graduate can also address the Manager (now redirects hands-on task asks to
  the Mentor instead of answering them) or a technical roster agent (Security
  Reviewer/Data Reviewer/DevOps) directly. New `agents/task_chat.py` routes
  `POST /agents/task/{id}/reply` by `agent_type`; the old
  `POST /agents/manager/reply/{id}` is unchanged for any other caller
  (`docs/TASK_CHAT.md`).
- **Every agent conversation surface has a shared behavioral floor**
  (`agents/guardrails.py`): declines requests outside its role at Venv instead
  of acting as a generic assistant, on top of whichever persona/task
  instructions it already had (`docs/TASK_CHAT.md`).
- **Team Room**: one shared thread per graduate (`TeamMessage`,
  `alembic/versions/0006_team_messages.py`) with their whole team, distinct
  from the Meeting Room's one-thread-per-agent chats. Each message is routed
  to whichever single teammate fits (a small-tier tool call), but the whole
  thread — everyone's past turns — stays visible to whoever replies next.
  `GET/POST /meeting/team` (`docs/TEAM_ROOM.md`).
- **Settings**: `PATCH /users/me` — rename yourself and/or change your
  password in one call, with current-password verification and a minimum
  length on the new one (`docs/SETTINGS_PAGE.md`).
- **Stage 3: companies on Venv** (`docs/STAGE3_COMPANY_RAG.md`) — company
  accounts (`AccountType`/`CompanyRole`, free-text job titles, per-rep
  logins reusing the exact same auth as students, and role-gated
  permissions — sending an invitation needs ADMIN/HR, a company project
  needs ADMIN/TECH_LEAD), a real RAG knowledge base (`app/rag.py`:
  chunking + OpenAI embeddings + in-Python cosine-similarity retrieval,
  no vector database), a company's own real projects (`CompanyProject`,
  distinct from a graduate's own project), an invite-by-email flow
  requiring explicit student consent before acceptance
  (`app/routers/invitations.py`, `INVITATION_DATA_NOTICE`) with a real
  email actually sent over SMTP (`app/email.py`, gracefully optional), a
  company roster with per-week reports built entirely from the weekly
  cycle's existing Manager/HR reviews — no new report-generation
  pipeline — and a student's own live view of exactly what the company
  sees (`GET /invitations/{id}/visibility`, `app/company_roster.py`,
  proven byte-for-byte identical to the company's own view in
  `smoke_test_student_visibility.py`). Migrations 0007/0008, both
  genuinely verified against a real PostgreSQL 16 instance (see that
  doc's "The PostgreSQL story" for two real bugs this caught and fixed).
- **Ten agents** (`docs/TEN_AGENTS.md`) — three new specialists (QA
  Engineer, UX Reviewer, Technical Writer) wired into every surface the
  existing optional agents already had (Meeting Room, Team Room, and —
  for QA Engineer/UX Reviewer specifically — task chat and the
  post-submission roundtable); Technical Writer deliberately stays
  chat-only, like Career Coach. Career Coach itself gets a real
  dedicated action for the first time — `app/agents/career_coach.py`'s
  career check-in, reading the actual Employee File/CV and writing real
  resume bullets plus one concrete focus area as a proper Review
  (`ReviewKind.CAREER_CHECKIN`), not another chat reply that evaporates.
  Migration 0010's genuinely novel piece: the first migration that
  alters an *existing*, already-populated Postgres enum type
  (`ALTER TYPE ... ADD VALUE`) rather than creating a fresh one or
  reusing one unchanged — see that doc's "PostgreSQL story, round two"
  for why it's safe and for a second, quieter SQLite column-width bug
  the drift guard caught along the way.

**Frontend** (Next.js + React Flow, dark-by-default "blueprint" design system,
light theme, Arabic/RTL — `frontend/DESIGN.md`):

- `/onboarding/cv` — CV upload → adaptive agent Q&A (skippable) → track
  suggestion with override → optional-agent roster → own-project choice (with
  materials upload) or "let the Manager plan it". **Resumes** from wherever a
  graduate left off (closed tab, restart). `POST /onboarding/reset` starts over.
- `/orientation` — shown once after onboarding: the graduate's project, full
  team, a guided walkthrough.
- `/board` — the agents graph, renders any extra agents dynamically.
- `/workspace` — task rail (with a "needs changes" badge) + the full roundtable
  thread, refreshing live while the specialists' discussion is still being
  written. The task-chat panel now shows a "working with" switcher (Mentor by
  default) and a "new task from {agent}" banner on a fresh task
  (`docs/TASK_CHAT.md`).
- `/profile/cv` — replace the CV after onboarding without touching track/team/tasks.
- `/meeting` — open to any agent on the graduate's actual roster, plus a "Team
  room" tab for a shared thread with the whole team at once (`docs/TEAM_ROOM.md`).
- `/settings` — profile (name), password change, a CV section linking to
  `/profile/cv`, and the language/theme toggles in one place
  (`docs/SETTINGS_PAGE.md`).
- `/growth`, `/tasks/[id]/review` — unchanged in shape.
- **Stage 3** (`docs/STAGE3_COMPANY_RAG.md`): `/company/register` (found
  a company or join via code + role), `/company` (org card with a
  copyable join code, job titles), `/company/job-titles/[id]` (material
  upload, real projects, invite a candidate, a "test the knowledge base"
  RAG search box with real scores), `/company/students` (roster) and
  `/company/students/[invitationId]` (week-by-week detail + reviews),
  `/invitations` (the student's consent screen — accept is disabled
  until an explicit checkbox is ticked; an accepted invitation gets a
  "See what they see" link) and `/invitations/[id]/visibility` (that
  same week-by-week data, from the student's side). `/login` now
  branches post-login on account type; `/board` gained an "Invitations"
  nav link with a pending-count badge.
- **Ten agents** (`docs/TEN_AGENTS.md`): no new pages — the point was that
  optional agents' names/descriptions have always come from the backend
  catalog, not `lib/i18n`, so three new agents needed zero new frontend
  translation strings. `/growth` gained an "Ask Career Coach for a
  check-in" button (shown only once Career Coach is on the roster) and
  a real display of the resume highlights/suggested focus it returns.
  Also fixed a real, pre-existing type-safety gap this surfaced:
  `lib/reviews.ts`'s `Review.agentType` was typed as only ever being one
  of the three default agents — true until Career Coach started writing
  reviews too; widened to the full agent-type union.
- Verified: eslint clean, full `next build` succeeds (20 routes).

## What's genuinely unverified

Be honest with yourself about this list before calling anything demo-ready:

- **Nobody has used the app in a browser since the hardening pass began** —
  and that now includes the task-chat/Team Room/settings pass and all of
  Stage 3, all built entirely against automated tests. Every check above
  is an automated test or a scripted real-model run — real clicking,
  real screens, real Arabic RTL layout, has not happened.
- **The task bank and Mentor rubric are drafts awaiting team sign-off**, not
  team-approved content (`docs/TASK_BANK.md`, `docs/MENTOR_RUBRIC.md` both have a
  "Decisions for the team" section).
- **Real-model coverage is partial.** Confirmed with real keys so far: onboarding
  through HR rollup on DeepSeek and Claude, Arabic replies on DeepSeek, the
  malformed-output bug that started the hardening pass. Not yet confirmed with
  real keys: the task bank's seed adaptation across tracks, the rubric's
  approve-path (every real run so far bounced on an unrelated default repo),
  Qwen (its configured model name is dead — see Setup notes), OpenAI as a
  fallback provider.
- **The roundtable's real-model timing** (background vs. the old inline ~25s) has
  not been measured with real keys, only proven correct in automated tests.
- **This latest pass (task chat, guardrails, Team Room, settings, and all of
  Stage 3) is mocked-LLM tested only, same as everything else above** — the
  Manager's redirect behavior, every agent's off-topic decline, the Team
  Room's routing quality, and RAG retrieval ranking (real cosine-similarity
  math, but against a mocked embedding fake, not real OpenAI embeddings)
  have not been checked against real models, only against mocks that
  return exactly what each test expects.
- **The Postgres verification that ran this session was against a
  throwaway instance in the sandbox itself, not the project's actual
  deployment target** — genuinely fixed real bugs (see
  `docs/STAGE3_COMPANY_RAG.md`'s "The PostgreSQL story"), but that
  sandbox instance is gone between sessions; re-run
  `smoke_test_migrations.py`'s Postgres section against whatever's
  actually used for deployment before fully trusting it there too.
- **Nobody has clicked through any of Stage 3 in an actual browser** —
  same "automated tests only" caveat as everything else, but worth
  calling out specifically since Stage 3 adds a second full account type
  (company) with its own login branch, nav, and pages that have never
  been visually checked.

## Setup notes for whoever runs this next

- **Qwen is misconfigured**: `qwen/qwen-turbo` returns 404 from the configured
  endpoint. Fix the model name/base URL, or drop it from
  `LLM_PROVIDER_PRIORITY_SMALL` for now.
- **`GITHUB_TOKEN`** (optional, no scopes needed) raises the Mentor's GitHub
  read limit from 60/hour/IP to 5,000/hour — each review costs 3 requests, so
  this matters fast once you're testing repeatedly.
- **First startup after `git pull` runs migrations automatically.** An
  out-of-date SQLite dev DB (schema older than what's in `alembic/versions/`)
  will refuse to start with a message naming the missing column — delete
  `dev.db` and it rebuilds clean.

## Doc index

**Stage 1 & 2 core** (chronological, one doc per slice):
`STAGE1_PRODUCT_FLOW.md` · `STAGE2_ONBOARDING_FLOW.md` ·
`STAGE2_WEEKLY_CYCLE_FLOW.md` · `STAGE2_OWN_PROJECT.md` ·
`STAGE2_ONBOARDING_FRONTEND.md` · `STAGE2_TEAM_AND_ORIENTATION.md`
(orientation's *UI* is superseded by a later frontend pass — see its own note —
but the backend it documents is still accurate) · `STAGE2_MEETING_AND_SUBMISSIONS.md` ·
`STAGE2_AGENT_TASK_WORK.md` (superseded by the roundtable, kept as the simpler
fallback, `co_reviewers.py`) · `STAGE2_ROUNDTABLE.md`.

**Hardening** (this session, roughly in build order): `MIGRATIONS.md` ·
`ONBOARDING_RESUME.md` · `NEEDS_CHANGES_VISIBLE.md` · `AGENT_LANGUAGE.md` ·
`MENTOR_RUBRIC.md` · `LLM_PROVIDER_FAILOVER.md` (incl. "Malformed tool output")
· `TASK_BANK.md` · `BACKGROUND_ROUNDTABLE.md` · `ONBOARDING_GRAPH_HARDENING.md`.

**Task chat / Team Room / settings** (this session, most recent):
`TASK_CHAT.md` (Mentor as the default in-task agent, the Manager scoped to
the big picture, the shared `agents/guardrails.py` role-boundary) ·
`TEAM_ROOM.md` (one shared thread with the whole team, routed replies) ·
`SETTINGS_PAGE.md` (`PATCH /users/me`, the new `/settings` page).

**Stage 3 — companies**: `STAGE3_COMPANY_RAG.md` — company
accounts, the RAG knowledge base, a company's own real projects, the
invite-with-consent flow, the roster/report view, and the real-Postgres
bug-hunt that verified all of it.

**Ten agents**: `TEN_AGENTS.md` — three new specialists
(QA Engineer, UX Reviewer, Technical Writer), Career Coach's new career-
checkin action, and the second round of Postgres-enum migration lessons
(altering an existing, already-populated enum type for the first time).

**Agent read/write audit**: `AGENT_READ_WRITE.md` — a
code audit and a new deep test file verifying every agent's LLM calls
genuinely receive real context and genuinely write back correctly, not
just "returns 200." Closes three real gaps (HR's attendance figures,
the roundtable's real-conversation claim, Mentor's vision path) and
notes one piece of housekeeping (`co_reviewers.py` is dead code, not an
active fallback) found but out of scope to act on this pass.

**CV content validation** (most recent): `CV_VALIDATION.md` — a real
reported bug fixed: uploading any readable file as a "CV" used to be
silently accepted (nothing checked the content, only that some text
came out of the file). Now judged by a real model at all three CV-intake
points, with the fix and testing story for what it took to update seven
pre-existing tests that had CV upload mocked for a single LLM call.

**Frontend-only work with no dedicated doc** (orientation rework, Arabic i18n,
light mode — built in a separate pass, documented only in their own PR/commit
messages): still true, still worth a proper writeup at some point, not urgent.

## Not built yet

- **Roundtable specialists don't get vision** — only the Mentor's review sees
  image attachments as real content; specialists see filenames only.
- **No cloud file storage** — `app/storage.py` is local-disk, one box.
- **The doc-writing gap** above (orientation/Arabic/light-mode).

## Stage 3 (companies) — done

Stage 3 ("companies build their own Venv") is built and merged — full
write-up at `docs/STAGE3_COMPANY_RAG.md`. All four scoping questions
that were open before it started are answered there: job titles are
free text, company accounts are separate per-rep logins with roles, a
company's own uploaded projects are distinct from a student's
own-project feature, and a student must see and explicitly consent to
what a company will see before accepting an invitation.

**What's still open, per that doc's "Not built" section:** no
per-role permission gating yet (any company role can do anything a
company account can do today), no email/invite-delivery system (joining
a company or seeing an invitation is self-serve/email-match, not a real
sent email), a student can't yet see their own view of what a company
has seen about them, and — as with everything else in this doc — nobody
has clicked through any of it in a browser yet.

**Groundwork that made this straightforward:** every core table already
carried a nullable `organization_id` from the original schema design,
long before Stage 3 started — Project, Week, Task, Review all had it
sitting unused. Own-project materials
(`docs/STAGE2_OWN_PROJECT.md`) turned out to be the exact same shape a
company's own real project needed (pasted notes + uploaded files,
extracted and capped) — that helper was pulled out into
`app/materials.py` so both features share it rather than duplicate it.

## Repo map

```
.
├── docker-compose.yml   one-command local Postgres
├── backend/
│   ├── e2e_real_llm.py   real-key end-to-end check (docs above; --help for flags)
│   └── app/
│       ├── agents/        Manager/Mentor/HR/Meeting/roundtable/task_bank/rubric/
│       │                  task_chat/guardrails/career_coach/tool_output —
│       │                  see app/agents/README.md
│       │   └── graph/     LangGraph: onboarding_graph, weekly_cycle_graph,
│       │                  collaboration, models, catalog, cv_parsing
│       ├── routers/       onboarding, projects, tasks, meeting, agents, users,
│       │                  auth, company, invitations
│       ├── migrations.py  startup migration runner (adopt / refuse / upgrade)
│       ├── language.py    per-request agent language (X-Venv-Language)
│       ├── materials.py   shared upload→text helper (own-project + company projects)
│       ├── rag.py         chunking + embeddings + cosine-similarity retrieval
│       └── storage.py     local-disk attachment storage
│   └── alembic/versions/  0001 baseline … 0010 ten agents
├── frontend/
│   └── src/
│       ├── app/            landing, login, board, orientation, onboarding/cv,
│       │                   workspace, meeting, growth, tasks/[id]/review,
│       │                   profile/cv, settings, invitations, company/
│       │                   (register, job-titles/[id], students/[invitationId])
│       ├── components/     board/, dashboard/, workspace/
│       └── lib/            api.ts (wire format), one file per domain, i18n/
└── .vscode/               shared editor config
```

## Working approach — follow this in every chat, every session

1. New piece of work → new branch off `main`: `feature/...`, `fix/...`,
   `chore/...`, `docs/...`.
2. Commit in small, logical chunks with imperative messages ("add X", not
   "added X"). Code gets brief comments explaining *why*, not just what.
3. Test before committing — the full smoke suite, not just the file you
   touched, on SQLite **and** PostgreSQL where the change touches the database.
4. Push the branch, merge into `main`.
5. `main` stays deployable at all times.

## Conventions established so far (keep these consistent going forward)

- Every core table carries a nullable `organization_id`, even where nothing
  uses it yet.
- `EmployeeFile` is the one shared context object — new agent logic reads/writes
  its existing fields rather than inventing a parallel structure.
- `TaskMessage.sender_type` is derived, not set directly: pass `agent_type` in
  the request to record it as an agent message, omit it for a user message.
- Secrets live in `.env` (gitignored), never committed; `.env.example` is the
  template.
- Frontend: hairline borders + a faint grid instead of rounded cards and
  shadows, one accent color, monospace reserved for actual technical content —
  see `frontend/DESIGN.md`.
- Model routing: cheap/mechanical steps (onboarding suggestions, roundtable
  specialist comments) use the small model; primary judgment calls (Mentor's
  review, the Manager's synthesis/progress writeups) use the main model.
- Any new agent capability that isn't a hard requirement for every graduate goes
  through the `AgentCatalog`/`UserAgent` roster pattern, not a new always-on
  code path.
- Any model call that forces a tool (JSON-schema-shaped arguments) should go
  through `agents/tool_output.py`'s repair/check, with a `validate` hook for
  anything schema-shape alone can't catch — the pattern both existing
  tool-calling paths (`llm_client.call_with_tool`, the onboarding graph's
  `_forced_tool_call`) now share. A new one should too.
- Test files that exercise a real endpoint under a deliberately-broken mock
  should pin `resolve_provider_chain` explicitly (don't rely on other providers
  being unconfigured in `.env` — a real developer's `.env` usually has every
  key set). A background task's effect should be polled for
  (`roundtable_running`), never assumed complete the instant a request returns.
- **A migration that adds or reuses a Postgres enum type must use
  `sqlalchemy.dialects.postgresql.ENUM`, never generic `sa.Enum`** — the
  generic type does not reliably honor `create_type=False` inside
  `op.create_table` (confirmed against real Postgres 16; see
  `docs/STAGE3_COMPANY_RAG.md`'s "The PostgreSQL story"). `postgresql.ENUM`
  degrades cleanly to an ordinary column on SQLite, so this is safe to use
  unconditionally, no dialect branching needed at the column-definition
  level. Also: a new NOT NULL column's `server_default` on an existing
  Enum-typed column must match the enum's stored label exactly — this
  codebase's Enum columns store the Python member's **name**
  (`'STUDENT'`), not its `.value` (`'student'`); SQLite won't catch a
  mismatch there, Postgres will refuse it outright.
- **Adding a value to an existing enum type** (as opposed to creating a
  fresh one) needs `ALTER TYPE ... ADD VALUE IF NOT EXISTS` — safe on
  Postgres 12+ inside a normal transaction as long as nothing in the
  same migration *uses* the new value (see `docs/TEN_AGENTS.md`'s
  "PostgreSQL story, round two"). Check SQLite too: `sa.Enum` sizes its
  SQLite `VARCHAR` to the longest member *name* at the column's
  original creation time, so a new, longer member name can silently
  leave that column too narrow — a real drift the model-drift guard
  catches (confirmed the hard way), even though SQLite never enforces
  the length at the data level. Widen the column explicitly if the new
  member is longer than every existing one.

## Reference: full API surface

Backend base URL in dev: `http://localhost:8000`. Interactive schema for every
endpoint at `/docs`.

- **Auth**: `POST /auth/register`, `POST /auth/login` (form-encoded).
- **Users**: `GET /users/me` (`has_cv`, `track`), `PATCH /users/me` (rename
  and/or change password — the settings page), `GET /users/me/agents`,
  `GET /users/me/dashboard`, `/users/me/employee-file`, `/users/me/reviews`,
  `POST /users/me/cv` (paste), `POST /users/me/cv/file` (replace after
  onboarding — 409 while mid-wizard).
- **Onboarding**: `POST /onboarding/cv` (upload, starts the graph),
  `POST /onboarding/qa`, `POST /onboarding/track`, `POST /onboarding/agents`,
  `GET /onboarding/state`, `GET /onboarding/resume` (resume the wizard from
  wherever it was left, no LLM cost), `POST /onboarding/reset`,
  `GET /onboarding/catalog` (no auth required).
- **Projects**: `GET /projects/me` (`seed_id`, `has_materials`),
  `POST /projects/own` (multipart: `title`, `description`, optional
  `materials_text` + up to 3 `files`).
- **Tasks**: `GET /tasks` (incl. `needs_changes`, `revision_count`,
  `roundtable_running`), `POST /tasks` (admin/manual only), `GET /tasks/{id}`,
  `PATCH /tasks/{id}/status`, `POST /tasks/{id}/submit` (multipart — the path
  the frontend uses), `GET /tasks/{id}/attachments/{attachment_id}`,
  `POST /tasks/{id}/messages`, `GET /tasks/{id}/review`.
- **Agents**: `POST /agents/manager/assign-task` (bootstraps/advances the
  weekly cycle), `POST /agents/manager/reply/{task_id}` (unchanged, still
  Manager-only), `POST /agents/task/{task_id}/reply` (body
  `{"agent_type": ...}`, defaults to `mentor` — the endpoint the app itself
  uses now; 403s an agent not available for task chat, `docs/TASK_CHAT.md`),
  `POST /agents/mentor/review/{task_id}` (schedules the roundtable in the
  background), `POST /agents/hr/rollup`, `POST /agents/career-coach/checkin`
  (docs/TEN_AGENTS.md — Career Coach's one dedicated action; 403 unless
  Career Coach is on the graduate's roster, 400 with no Employee File yet).
- **Meeting**: `GET/POST /meeting/{agent}` — any `AgentType`; 403s an optional
  agent the graduate hasn't added. `GET/POST /meeting/team` — the Team Room's
  shared thread, routed to whichever teammate fits (`docs/TEAM_ROOM.md`).
- **Company** (`docs/STAGE3_COMPANY_RAG.md`): `POST /company/register`
  (found a new company or join one via `join_code` + `role`),
  `GET /company/me`, `POST/GET /company/job-titles`,
  `GET /company/job-titles/{id}`,
  `POST/GET /company/job-titles/{id}/materials` (RAG knowledge base
  upload/list), `POST /company/job-titles/{id}/query` (real retrieval,
  real scores), `POST/GET /company/job-titles/{id}/projects` (a
  company's own real projects, distinct from a graduate's own project),
  `POST /company/job-titles/{id}/invitations`, `GET /company/invitations`,
  `GET /company/students` (roster), `GET /company/students/{invitation_id}`
  (week-by-week detail + reviews — the "end-of-week report").
- **Invitations** (student-facing, `docs/STAGE3_COMPANY_RAG.md`):
  `GET /invitations/mine` (matched by email — no account needs to exist
  when the invite is sent), `POST /invitations/{id}/accept` (body
  `{"consent": true}`, required — 400 without it),
  `POST /invitations/{id}/decline`.
- Every request should carry `X-Venv-Language: en|ar` (the frontend does this
  automatically) so agent replies match the UI language.
- All of the above is wired into `frontend/src/lib/api.ts` and the per-domain
  `lib/*.ts` files — nothing calls `fetch` directly elsewhere.

## Running the smoke suite

Mocked LLM calls throughout — no API key needed. From `backend/`:

```bash
python smoke_test.py                          # auth → task → thread (20)
python smoke_test_agents.py                    # Manager/Mentor/HR basics (19)
python smoke_test_weekly_cycle.py              # Project/Week schema + iterative review (17)
python smoke_test_orchestration.py             # full weekly cycle, end to end (57)
python smoke_test_meeting.py                   # direct agent chat, Stage 1 scope (15)
python smoke_test_llm_errors.py                # graceful LLM-failure handling (10)
python smoke_test_llm_provider_routing.py      # tier-aware provider selection (14)
python smoke_test_stage2_onboarding.py         # onboarding graph, isolated (28)
python smoke_test_stage2_onboarding_router.py  # onboarding endpoints, incl. reset (36)
python smoke_test_stage2_collaboration.py      # Manager/HR consulting the Mentor (9)
python smoke_test_stage2_own_project.py        # POST /projects/own (12)
python smoke_test_stage2_meeting.py            # Meeting Room roster gating (9)
python smoke_test_stage2_submissions.py        # multi-modal submission + vision (41)
python smoke_test_stage2_co_reviews.py         # co_reviewers.py unit tests (11)
python smoke_test_stage2_roundtable.py         # the roundtable, end to end (20)
python smoke_test_migrations.py                # Alembic + model-drift guard (19; +10 with Postgres — both dialects genuinely verified, docs/STAGE3_COMPANY_RAG.md)
python smoke_test_stage2_onboarding_resume.py  # restart-proof onboarding + CV replacement (54)
python smoke_test_needs_changes.py             # visible 'needs changes' state (29)
python smoke_test_agent_language.py            # agents answer in Arabic + browser CORS preflight (34)
python smoke_test_mentor_rubric.py             # Mentor rubric v2 + enforcement (49)
python smoke_test_llm_tool_output.py           # repair / retry / fail over on bad model output (48)
python smoke_test_task_bank.py                 # the Manager's task bank: integrity + wiring (62)
python smoke_test_github_client.py             # what the Mentor sees of a repo; token + rate limit (29)
python smoke_test_background_roundtable.py     # roundtable runs after the review; real HTTP timing (43)
python smoke_test_own_project_materials.py     # own-project notes/files reach the Manager's plan (29)
python smoke_test_onboarding_graph_hardening.py # onboarding tool calls: repair/check/retry (16)
python smoke_test_task_chat.py                 # task-thread agent switcher: Mentor default, Manager/roster agents, HR refused (14)
python smoke_test_team_room.py                 # Team Room: routing, fallback, isolation between users (17)
python smoke_test_settings.py                  # PATCH /users/me: rename, password change, validation (15)
python smoke_test_company_rag.py               # company accounts, job titles, RAG upload + real retrieval ranking (35)
python smoke_test_company_invitations.py       # company projects, invite/consent flow, double-response prevention (36)
python smoke_test_company_students.py          # company roster + per-week reports, real assign-task integration (22)
python smoke_test_company_roles.py             # company role permissions: invitations ADMIN/HR, projects ADMIN/TECH_LEAD (13)
python smoke_test_invitation_emails.py         # real invitation emails: graceful degradation + a genuine local SMTP server (15)
python smoke_test_student_visibility.py        # student's own view matches the company's, byte-for-byte, after a real task cycle (11)
python smoke_test_ten_agents.py                # catalog, Meeting/task-chat/roundtable eligibility, full career-checkin lifecycle (20)
python smoke_test_agent_read_write.py          # deep read/write audit: real context in, exact HR figures, real roundtable conversation (24)
python smoke_test_cv_validation.py             # real bug fix: a non-CV upload genuinely refused at all 3 intake points (16)
```

If the LLM key is missing, wrong, or out of credit, agent endpoints return a
clean, actionable error (503/429/502) rather than a 500 — a missing key never
looks like a crash.

**Before a demo, also run the real-model check** — the suites above mock every
model call, so only this one catches a slow provider, malformed tool output, a
provider without image support, or a failover that doesn't fail over:

```bash
python e2e_real_llm.py                                # providers as set in .env
python e2e_real_llm.py --provider qwen                # one provider for every call
python e2e_real_llm.py --language ar                   # do the agents really answer in Arabic?
python e2e_real_llm.py --full-week --force-approve     # run the end-of-week cascade even if the Mentor keeps bouncing
python e2e_real_llm.py --save-report run.json          # keep what the models produced, to review or share
```

It reports what a graduate actually waits for (over real HTTP), how often a
model's output had to be repaired or retried, and prints the project/tasks/
reviews the models produced so you can judge quality yourself. First real run
(DeepSeek and Claude) found the malformed-output bug that started this whole
hardening pass — it has already earned its keep once.
