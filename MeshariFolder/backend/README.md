# Venv Backend (Stage 2)

FastAPI + PostgreSQL backend for Venv — auth, the weekly-cycle task
board, agent logic (Manager/Mentor/HR/Meeting + Stage 2's roundtable),
onboarding (a LangGraph agent), and the shared Employee File they all
read and write.

## Quickstart

From the **repo root** first, start Postgres via Docker (see root README):
```bash
docker compose up -d
```

Then, from this `backend/` folder:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # includes LangGraph/LangChain, pypdf, python-docx

cp .env.example .env
# .env already points at the Docker Postgres above — no edits needed.
# Quick local check without Docker? Set DATABASE_URL=sqlite:///./dev.db instead.

uvicorn app.main:app --reload
```

Then open http://localhost:8000/docs for interactive Swagger UI.

Verify everything works end-to-end (full list in `docs/PROJECT_STATUS.md`):
```bash
python smoke_test.py
```

## What's here

| File | Purpose |
|---|---|
| `app/models.py` | SQLAlchemy schema: Organization, User, Track, AgentCatalog/UserAgent, EmployeeFile, Project, Week, Task, TaskAttachment, TaskMessage, Review, ChatMessage |
| `app/schemas.py` | Pydantic request/response shapes |
| `app/auth.py` | Password hashing + JWT issue/verify + `get_current_user` dependency |
| `app/scheduling.py` | Saudi (Sun–Thu) workweek date math for week/subtask deadlines |
| `app/dashboard.py` | Aggregates the home-dashboard stats (`GET /users/me/dashboard`) |
| `app/storage.py` | Local-disk storage for task attachments (`backend/uploads/`, gitignored) |
| `app/agents/` | Manager, Mentor, HR, Meeting, the roundtable, and the LangGraph agents (see its own README) |
| `app/routers/auth.py` | `POST /auth/register`, `POST /auth/login` |
| `app/routers/users.py` | `GET /users/me`, `GET /users/me/agents`, `/employee-file`, `/reviews`, `/dashboard` |
| `app/routers/onboarding.py` | The full onboarding flow: CV upload, Q&A, track, agent roster, reset |
| `app/routers/tasks.py` | Task board CRUD, multi-modal submission, attachment download, threaded messages |
| `app/routers/projects.py` | `GET /projects/me`, `POST /projects/own` |
| `app/routers/agents.py` | Endpoints that trigger Manager/Mentor/HR — Mentor's endpoint also runs the roundtable |
| `app/routers/meeting.py` | `GET`/`POST /meeting/{agent}` — any agent on the graduate's actual team |
| `smoke_test*.py` (14 files) | Full list + check counts in `docs/PROJECT_STATUS.md`'s "Running the smoke suite" |

## Schema notes for the rest of the team

- **`organization_id` is nullable on every core table** (Users, Tasks,
  EmployeeFile, Reviews) even though nothing uses it yet. Deliberate from
  the original proposal, so a future multi-tenant stage is additive —
  add rows to `organizations` and start setting the FK — instead of a
  schema migration that touches every table.
- **`EmployeeFile` is the shared context object.** Every user gets one
  automatically at registration. Write to `skills_json` /
  `strengths_json` / `growth_areas_json` / `summary_text` rather than
  inventing a parallel structure.
- **`AgentCatalog`/`UserAgent`** (Stage 2) is the pattern for any new
  optional agent capability: a catalog row + a per-user selection table,
  not a new always-on code path. This is why Security Reviewer/Data
  Reviewer/Career Coach/DevOps were cheap to add — follow this pattern
  for anything similar later.
- **`Task.created_by_agent`** defaults to `manager`. `POST /tasks` is
  still a plain authenticated endpoint (useful for testing); the Manager
  agent itself builds `Task` rows directly.
- **`TaskMessage.sender_type`** is derived automatically: pass
  `agent_type` in the request body and it's recorded as an agent
  message; omit it and it's recorded as the user.
- **`Task.submission_text` / `TaskAttachment`** (Stage 2) — a submission
  is a GitHub link, free text, and/or up to 5 files/images, any
  combination, via `POST /tasks/{id}/submit`. Images reach the Mentor
  (and only the Mentor, not the roundtable specialists yet) as real
  vision content blocks.
- **CV parsing is real now** (Stage 2) — `POST /onboarding/cv` extracts
  text from PDF/.docx via `app/agents/graph/cv_parsing.py`, not just
  paste. The older `POST /users/me/cv` (plain text, no parsing) still
  exists unchanged for anything still calling it.

## Still open

See `docs/PROJECT_STATUS.md`'s "Not built yet" and "Handoff" sections —
kept there so there's one current list instead of this file and the root
doc drifting apart. Quick pointers specific to this folder:

- Alembic migrations — still `create_all` on startup. The onboarding
  dead-end bug (pre-Stage-2 rows never got the new `onboarding_stage`
  column backfilled) is a live example of why this is worth doing before
  the schema changes shape again.
- Task bank content, Mentor's rubric — both still first-pass/improvised,
  unchanged in nature since Stage 1.
- Onboarding's LangGraph checkpointer is in-memory — fine for one dev
  box, not for a real deployment.

## Auth flow for the frontend team

1. `POST /auth/register` → `{email, password, full_name}` → returns the created user.
2. `POST /auth/login` → form-encoded `username`/`password` (OAuth2 password flow) →
   returns `{access_token, token_type}`.
3. Send `Authorization: Bearer <access_token>` on every subsequent request.
