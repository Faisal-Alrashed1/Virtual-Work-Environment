# Venv — Virtual Work Environment

A simulated company for recent graduates: a **Manager** agent assigns real-world
tasks, a **Mentor** agent reviews submitted code, and an **HR** agent tracks
growth over time — plus, since Stage 2, a selectable roster of optional
specialist agents (Security Reviewer, Data Reviewer, Career Coach, DevOps)
that actually **discuss submissions with each other** before the Manager
synthesizes what matters most.

**Current status — Stage 2 is complete and merged to `main`.** Stage 1's
weekly-cycle flow (a Manager-planned project → one big task per week → 5
subtasks handed out one at a time → Mentor review of each → end-of-week
Manager progress + HR behavioral evaluation) plus Stage 2's additions: CV
file intake with agent-generated follow-up questions, track selection
across six IT majors, an own-project path, a first-time orientation
screen, a Meeting Room open to any agent on your team, multi-modal task
submissions (link/text/images/files, with real vision review), and the
**agent roundtable** — optional agents building on each other's comments
in sequence, not just posting in parallel. See `docs/PROJECT_STATUS.md`
for the exact feature-by-feature state (start there — it links every
Stage 2 doc in build order) and `docs/STAGE1_PRODUCT_FLOW.md` for the
weekly-cycle spec that started it all.

**Next up (see `docs/PROJECT_STATUS.md`'s handoff section):** reworking
the onboarding/orientation greeting for new users, Arabic language
support, and a light-mode theme — then Stage 3.

## Repo structure

```
.
├── docs/        PROJECT_STATUS.md (start here) + one STAGE2_*.md doc per Stage 2 slice
├── backend/     FastAPI + PostgreSQL — auth, task/CV/review APIs, weekly-cycle
│                orchestration, LangGraph agents (onboarding + the roundtable)
│   └── app/agents/   Manager/Mentor/HR/Meeting + Stage 2's roundtable & co-reviewers
│       └── graph/      LangGraph: onboarding, weekly-cycle cascade, model routing
├── frontend/    Next.js + React Flow — landing, onboarding wizard, orientation,
│                dashboard board, workspace, meeting room, growth view
└── .vscode/     Shared editor settings so the whole team gets the same setup
```

## Team roles → where your code goes

| Role | Folder | Owns |
|---|---|---|
| Backend & Data | `backend/app/` (minus `agents/`) | DB schema, auth, task/CV/review/onboarding APIs |
| AI / Agent engineering | `backend/app/agents/` | Manager, Mentor, HR, Meeting, roundtable, LangGraph agents |
| Frontend | `frontend/` | Onboarding wizard, board, workspace, meeting room, growth |
| Product, integration & QA | across both | task bank content, Mentor's rubric, i18n/theme decisions, end-to-end testing |

## Getting started

**1. Start the database.** Install [Docker
Desktop](https://www.docker.com/products/docker-desktop/) once, then from the
repo root:

```bash
docker compose up -d
```

This runs a real Postgres in the background, already matching the credentials
in `backend/.env.example` — no extra config needed. Leave it running while you
work; `docker compose down` stops it.

**2. Run the backend:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt  # includes LangGraph/LangChain — see requirements.txt

cp .env.example .env             # already points at the Docker Postgres above
uvicorn app.main:app --reload
```

No Docker yet, or just testing something quick? Set `DATABASE_URL=sqlite:///./dev.db`
in `.env` instead — the app runs fine on either, but **Postgres is what the
team should actually develop against**, since that's what we'll deploy on.

Open http://localhost:8000/docs for the interactive API. Sanity-check the
whole system any time with the smoke test suite (mocked LLM calls — no API
key needed to run them):

```bash
python smoke_test.py                          # auth → task → thread (20)
python smoke_test_agents.py                    # Manager/Mentor/HR basics (19)
python smoke_test_weekly_cycle.py              # Project/Week schema + iterative review (17)
python smoke_test_orchestration.py             # full weekly cycle, end to end (57)
python smoke_test_meeting.py                   # direct agent chat, Stage 1 scope (15)
python smoke_test_llm_errors.py                # graceful LLM-failure handling (8)
python smoke_test_stage2_onboarding.py         # onboarding graph, isolated (28)
python smoke_test_stage2_onboarding_router.py  # onboarding endpoints incl. reset (34)
python smoke_test_stage2_collaboration.py      # Manager/HR consulting the Mentor (9)
python smoke_test_stage2_own_project.py        # bring-your-own-project path (12)
python smoke_test_stage2_meeting.py            # Meeting Room roster gating (9)
python smoke_test_stage2_submissions.py        # multi-modal submission + vision (41)
python smoke_test_stage2_co_reviews.py         # parallel co-reviewers, unit-level (11)
python smoke_test_stage2_roundtable.py         # the agent roundtable, end to end (20)
```

If the LLM key is missing, wrong, or out of credit, the agent endpoints
return a clean, actionable error (503/429/502 with a helpful message the UI
displays) rather than a 500 stack trace — so a missing key never looks like
a crash.

On Windows, delete the leftover sqlite files between runs with
`Remove-Item *.db`. **Agent features that actually call the LLM** (onboarding,
assigning a task, replying, reviewing, the roundtable, the meeting room) need
a real `ANTHROPIC_API_KEY` in `.env` — the API console is billed separately
from a Claude Pro subscription, so add a few dollars of credit at
console.anthropic.com first. `LLM_MODEL` and `SMALL_LLM_MODEL` in `.env`
control which model each tier uses (see `docs/STAGE2_ONBOARDING_FLOW.md` for
why there are two tiers) — both have sensible defaults, no need to set them
for local dev.

Task attachments (images/files from submissions) land on local disk under
`backend/uploads/` (gitignored) — see `app/storage.py`.

See `backend/README.md` for schema details and `backend/app/agents/README.md`
for how the agents, the LangGraph flows, and the roundtable fit together.

**3. Run the frontend:**

```bash
cd frontend
npm install
cp .env.example .env.local     # optional — defaults to localhost:8000 anyway
npm run dev
```

Needs Node.js 18.18+ (`node -v` to check). Open http://localhost:3000 — the
landing page links to `/login` (sign in / register). **Register a new
account to see Stage 2's onboarding wizard** (existing accounts skip
straight to `/board`, same as before Stage 2). From registration:

- **`/onboarding/cv`** — CV file upload, agent-generated follow-up
  questions, track selection, and your optional-agent roster.
- **`/orientation`** — your project, your team, and how the app works,
  shown once right after onboarding.
- **`/board`** — the home dashboard: current focus, stats, week progress,
  and the interactive agents graph (now shows any optional agents you
  added, not just the default three).
- **`/workspace`** — the Jira-style workspace: task list, task detail with
  a submit form (link, notes, and file/image attachments), and the agents
  thread — where the Mentor's review and, if you added any specialists,
  the full roundtable discussion plays out.
- **`/meeting`** — a direct chat room with any agent on your team.
- **`/growth`** — HR's view of your skills, strengths, and score trend.

**The frontend talks to the real backend above** — everything is live, not
mock data. See `frontend/README.md` and `frontend/DESIGN.md` for the
structure and design system before adding new UI (the design-system doc is
dark-theme-only right now — see `docs/PROJECT_STATUS.md`'s handoff section
for the light-mode work queued up next).

## Git workflow

Keep `main` deployable. For any real chunk of work:

```bash
git checkout main && git pull
git checkout -b feature/short-description   # or fix/..., chore/...
# ... do the work, commit as you go ...
git push -u origin feature/short-description
# open a PR into main, get it reviewed, then merge
```

Commit often and in small, meaningful chunks — one logical change per commit,
written in the imperative ("add task status endpoint", not "added" or "stuff").
Merge to `main` once a piece is working end-to-end, not mid-broken. Run the
full smoke suite before merging, not just the file you touched.
