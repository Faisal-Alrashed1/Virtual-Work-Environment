# Venv — Virtual Work Environment

A simulated company for recent graduates: a **Manager** agent assigns real-world
tasks, a **Mentor** agent reviews submitted code, and an **HR** agent tracks
growth over time. Stage 1 (this bootcamp, Sep 1 – Oct 1 2026) is scoped to one
track (junior developer) and these three agents.

**Current status — Stage 1 is feature-complete and running end-to-end.**
Auth, CV intake, the full weekly-cycle flow (a Manager-planned project → one
big task per week → 5 subtasks handed out one at a time → Mentor review of
each → end-of-week Manager progress + HR behavioral evaluation), the
Jira-style workspace, a live home dashboard, a direct-chat meeting room with
each agent, and the growth view are all built and wired to real data — no
mocks. See `docs/PROJECT_STATUS.md` for the exact feature-by-feature state
and `docs/STAGE1_PRODUCT_FLOW.md` for the weekly-cycle spec it implements.

## Repo structure

```
.
├── docs/        PROJECT_STATUS.md (living handoff doc) + STAGE1_PRODUCT_FLOW.md (the spec)
├── backend/     FastAPI + PostgreSQL — auth, task/CV/review APIs, weekly-cycle orchestration
│   └── app/agents/   Manager / Mentor / HR + the weekly-cycle state machine (AI/Agents track)
├── frontend/    Next.js + React Flow — landing, dashboard board, workspace, meeting room, growth view
└── .vscode/     Shared editor settings so the whole team gets the same setup
```

## Team roles → where your code goes

| Role | Folder | Owns |
|---|---|---|
| Backend & Data | `backend/app/` (minus `agents/`) | DB schema, auth, task/CV/review APIs |
| AI / Agent engineering | `backend/app/agents/` | Manager, Mentor, HR prompts, tool-calling, orchestrator |
| Frontend | `frontend/` | Node board, task board, thread UI, performance page |
| Product, integration & QA | across both | task bank content, Mentor's review rubric, end-to-end testing |

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
pip install -r requirements.txt

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
python smoke_test.py               # auth → task → thread (20 checks)
python smoke_test_agents.py        # Manager / Mentor / HR basics (19 checks)
python smoke_test_weekly_cycle.py  # Project/Week schema + iterative review (17)
python smoke_test_orchestration.py # the full weekly cycle, end to end (56)
python smoke_test_meeting.py       # direct agent chat / meeting room (15)
python smoke_test_llm_errors.py    # graceful LLM-failure handling (8)
```

If the LLM key is missing, wrong, or out of credit, the agent endpoints
return a clean, actionable error (503/429/502 with a helpful message the UI
displays) rather than a 500 stack trace — so a missing key never looks like
a crash.

On Windows, delete the leftover sqlite files between runs with
`Remove-Item *.db`. **Agent features that actually call the LLM** (assigning
a task, replying, reviewing, the meeting room) need a real
`ANTHROPIC_API_KEY` in `.env` — the API console is billed separately from a
Claude Pro subscription, so add a few dollars of credit at
console.anthropic.com first.

See `backend/README.md` for schema details and `backend/app/agents/README.md`
for how the agents and the weekly-cycle state machine fit together.

**3. Run the frontend:**

```bash
cd frontend
npm install
cp .env.example .env.local     # optional — defaults to localhost:8000 anyway
npm run dev
```

Needs Node.js 18.18+ (`node -v` to check). Open http://localhost:3000 — the
landing page links to `/login` (sign in / register), then you land on
`/board` (the home dashboard: your current focus, stats, week progress, and
the interactive agents graph). From there:

- **`/workspace`** — the Jira-style workspace where you do the work: task
  list, task detail with submit/review actions, and a per-task agents
  discussion panel.
- **`/meeting`** — a direct chat room with each agent (Manager / Mentor / HR),
  not tied to any task.
- **`/growth`** — HR's view of your skills, strengths, and score trend.

**The frontend talks to the real backend above** — auth, tasks, reviews, the
employee file, dashboard stats, and agent chat are all live, not mock data.
See `frontend/README.md` and `frontend/DESIGN.md` for the structure and
design system before adding new UI.

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
Merge to `main` once a piece is working end-to-end, not mid-broken.
