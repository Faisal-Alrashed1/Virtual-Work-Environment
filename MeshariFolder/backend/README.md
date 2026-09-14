# Venv Backend (Stage 1)

FastAPI + PostgreSQL backend for Venv — auth, task board, agent logic
(Manager/Mentor/HR), and the shared Employee File they all read and write.

## Quickstart

From the **repo root** first, start Postgres via Docker (see root README):
```bash
docker compose up -d
```

Then, from this `backend/` folder:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env already points at the Docker Postgres above — no edits needed.
# Quick local check without Docker? Set DATABASE_URL=sqlite:///./dev.db instead.

uvicorn app.main:app --reload
```

Then open http://localhost:8000/docs for interactive Swagger UI.

Verify everything works end-to-end:
```bash
python smoke_test.py
```

## What's here

| File | Purpose |
|---|---|
| `app/models.py` | SQLAlchemy schema: Organization, User, EmployeeFile, Project, Week, Task, TaskMessage, Review, ChatMessage |
| `app/schemas.py` | Pydantic request/response shapes |
| `app/auth.py` | Password hashing + JWT issue/verify + `get_current_user` dependency |
| `app/scheduling.py` | Saudi (Sun–Thu) workweek date math for week/subtask deadlines |
| `app/dashboard.py` | Aggregates the home-dashboard stats (`GET /users/me/dashboard`) |
| `app/agents/` | Manager, Mentor, HR + the weekly-cycle state machine (see its own README) |
| `app/routers/auth.py` | `POST /auth/register`, `POST /auth/login` |
| `app/routers/users.py` | `GET /users/me`, `POST /users/me/cv`, `GET /users/me/employee-file`, `GET /users/me/reviews`, `GET /users/me/dashboard` |
| `app/routers/tasks.py` | Task board CRUD, threaded messages, `GET /tasks/{id}/review` |
| `app/routers/projects.py` | `GET /projects/me` — active project + all its weeks |
| `app/routers/agents.py` | Endpoints that trigger the three agents |
| `app/routers/meeting.py` | `GET`/`POST /meeting/{agent}` — direct task-free agent chat |
| `smoke_test.py` | End-to-end check of auth/task/thread/CV flow against sqlite (20 checks) |
| `smoke_test_agents.py` | The three agents' basics (LLM mocked, real GitHub fetch) (19) |
| `smoke_test_weekly_cycle.py` | Project/Week schema + iterative Mentor review (17) |
| `smoke_test_orchestration.py` | The full weekly cycle end-to-end through the API (56) |
| `smoke_test_meeting.py` | Direct agent chat / meeting room (15) |
| `smoke_test_llm_errors.py` | Graceful LLM-failure handling — clean errors, not 500s (8) |

## Schema notes for the rest of the team

- **`organization_id` is nullable on every core table** (Users, Tasks, EmployeeFile,
  Reviews) even though Stage 1 has no organizations. This was a deliberate call from
  the proposal so Stage 3 (companies build their own Venvs) is additive — you add
  rows to `organizations` and start setting the FK — instead of a migration that
  touches every table.
- **`EmployeeFile` is the shared context object.** Every user gets one automatically
  at registration (see `routers/auth.py`). This is what should back the Manager's
  task-difficulty calibration, the Mentor's findings, and HR's rollup reviews — write
  to `skills_json` / `strengths_json` / `growth_areas_json` / `summary_text` rather
  than inventing a parallel structure.
- **`Task.created_by_agent`** defaults to `manager`. `POST /tasks` is still a
  plain authenticated endpoint (useful for testing); the Manager agent itself
  builds `Task` rows directly rather than calling its own HTTP endpoint — see
  `app/agents/manager.py`'s docstring for why that's an equivalent, not a
  shortcut.
- **`TaskMessage.sender_type`** is derived automatically: pass `agent_type` in
  the request body and it's recorded as an agent message; omit it and it's
  recorded as the user. The Manager agent calls this same path to post
  replies into a task's thread.
- **CV parsing is intentionally shallow.** `POST /users/me/cv` just stores
  `cv_raw_text` and returns `has_cv: true`. Turning that into structured
  `EmployeeFile.skills_json` doesn't happen at intake — the Manager agent
  reads the raw text directly as prompt context instead.

## Still open

See **`docs/STAGE1_PRODUCT_FLOW.md`** at the repo root — that's the current
priority, and it'll add new tables (a Project/Week-shaped entity, task
deadlines, end-of-week evaluation records) on top of what's here. Smaller
standalone items:

- Example task bank content — not modeled as a separate table yet; the
  Manager currently improvises tasks live from CV/skills context alone.
- Mentor's rubric (`SUBMIT_REVIEW_TOOL` in `app/agents/tools.py`) is a first
  pass, not team-agreed.
- CV file upload (PDF/docx) — currently paste-only, no parsing anywhere.
- Migrations: tables are still created via `Base.metadata.create_all` on
  startup. Worth switching to Alembic once the Stage 1 flow's new tables
  land, not before — no point migrating the schema twice.

## Auth flow for the frontend team

1. `POST /auth/register` → `{email, password, full_name}` → returns the created user.
2. `POST /auth/login` → form-encoded `username`/`password` (OAuth2 password flow) →
   returns `{access_token, token_type}`.
3. Send `Authorization: Bearer <access_token>` on every subsequent request.
