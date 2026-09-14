# Agents

Manager, Mentor, and HR are implemented, driving the full
docs/STAGE1_PRODUCT_FLOW.md weekly-cycle flow — LLM: Anthropic Claude,
model configurable via `LLM_MODEL` in `.env` (default `claude-sonnet-5`).
Orchestration is a plain custom router (`orchestrator.py`) plus a small
state machine (`weekly_cycle.py`), not a framework like CrewAI — three
agents sharing one Employee File didn't need one.

- **Manager** (`manager.py`) — five jobs: introduce the graduate's main
  `Project` (`create_project`, once ever); plan each `Week` as a big task
  + exactly 5 subtasks (`plan_week`, with each subtask's deadline decided
  up front against the Saudi Sun-Thu workweek — see `app/scheduling.py`);
  hand out one subtask at a time as a real `Task` row
  (`release_next_subtask`, no LLM call — the plan was already decided);
  reply in a task's thread (`respond_in_thread`) when the graduate posts a
  message; and write the end-of-week progress review
  (`submit_week_progress`, `kind="week_progress"`) that HR's behavioral
  review reads alongside. All calibrated against `User.cv_raw_text` /
  `EmployeeFile.skills_json`.
- **Mentor** (`mentor.py`) — reads a submitted task's `github_link` via
  `github_client.py` (real GitHub API, unauthenticated, public repos only —
  matches Project-Summary.md's Stage 1 scope), writes a structured `Review`
  (`agent_type="mentor"`, `kind="task_review"`, `metrics_json` = verdict +
  rubric categories + inline comments — see `tools.py`'s
  `SUBMIT_REVIEW_TOOL`), posts a summary message, and moves the task to
  `reviewed` on an `approved` verdict or back to `in_progress` on
  `needs_changes` (iterative review), so the graduate can revise and
  resubmit rather than dead-ending either way. On approval it also stamps
  `Task.completed_at`, which `Task.is_late` compares against
  `Task.deadline`.
- **HR** (`hr.py`) — two jobs: `run_rollup` reads a graduate's Mentor
  review history and writes a rollup `Review` (`kind="skills_rollup"`,
  `task_id=None`), refreshing `EmployeeFile.skills_json` /
  `strengths_json` / `growth_areas_json` / `summary_text` (each holds
  `{"items": [...]}` once HR has run — see the storage note at the top of
  `hr.py`). `run_behavioral_review` writes the end-of-week behavioral
  evaluation (`kind="behavioral"`) — attendance/absence/lateness figures
  are computed in code from existing Task/TaskMessage timestamps (see
  `_active_days`; "attendance" = a day with a status change, submission,
  or resubmission — confirmed with Meshari), and the LLM only writes the
  narrative + a consistency rating on top of numbers it's handed.
- **weekly_cycle.py** — `get_next_task(db, user)` is the state machine:
  bootstrap a Project + Week 1 on the very first call, return the same
  in-flight subtask if one's still open (idempotent — no duplicates),
  release the next subtask once the current one's approved, or — once all
  5 are approved — run the end-of-week cascade (Manager's
  `submit_week_progress` then HR's `run_behavioral_review`, that order),
  close the Week, and roll straight into the next one. This is what
  `orchestrator.manager_assign_task` calls now; no new endpoint needed,
  `POST /agents/manager/assign-task` just does more than it used to.

## Files

```
agents/
├── llm_client.py     # thin Anthropic wrapper — swap providers here only
├── tools.py           # tool schemas (create_project, plan_week, post_message,
│                       #   submit_review, update_employee_file, submit_week_progress,
│                       #   submit_behavioral_review)
├── github_client.py   # unauthenticated GitHub API client for Mentor's repo context
├── manager.py         # create_project, plan_week, release_next_subtask,
│                       #   submit_week_progress, respond_in_thread
├── mentor.py          # review_task
├── hr.py              # run_rollup, run_behavioral_review
├── weekly_cycle.py    # get_next_task — the Project/Week/subtask/cascade state machine
└── orchestrator.py    # routes API calls to the above — see routers/agents.py
```

`app/scheduling.py` (not in `agents/` — it's plain date math, no LLM/DB)
computes Saudi workweek (Sun-Thu) deadlines that `plan_week` uses.

Triggered via `POST /agents/manager/assign-task`, `POST
/agents/manager/reply/{task_id}`, `POST /agents/mentor/review/{task_id}`,
`POST /agents/hr/rollup`. Read the results back via `GET /projects/me`
(the Project + all its Weeks), `GET /tasks/{task_id}/review`, `GET
/users/me/employee-file`, `GET /users/me/reviews`.

Test with `python smoke_test_agents.py` (basic per-agent sanity, mocked
LLM), `python smoke_test_weekly_cycle.py` (the Project/Week/Task schema +
the needs_changes bounce-back, Project/Week/Task written directly via the
ORM to isolate them from orchestration), and `python
smoke_test_orchestration.py` (the real thing end to end through the API:
bootstrap, idempotency, one-at-a-time release, the full cascade rolling
into week 2 — this is the one that actually proves weekly_cycle.py works).

## Still open

- **Task bank**: `plan_week`'s subtasks are still LLM-improvised from the
  CV/skills context alone, not sourced from a curated task bank — company-
  uploaded tasks and Phase 3's user-uploaded-project flow are confirmed as
  later, separate paths (not this bootcamp's scope), so this is expected
  to stay this way for now rather than being an open gap.
- **Rubric categories are a first pass**, not a finalized contract — see
  `tools.py`'s comment above `SUBMIT_REVIEW_TOOL`.
- **CV parsing** — Manager reads `cv_raw_text` as raw text in the prompt;
  no structured extraction into `EmployeeFile.skills_json` happens before
  HR's first rollup.
- **`needs_changes` is visually silent on the board** — it sends the task
  back to `in_progress`, the same column a never-reviewed task sits in.
  Whether that needs its own visible state is a product call, not made
  yet.
- **Frontend isn't wired to any of this** — `GET /projects/me` exists but
  nothing in `frontend/` calls it yet; the home board's node UI still
  needs building against real Project/Week data instead of mocks.
- **Attendance is only meaningfully testable over real elapsed days** —
  the "meaningful progress" days computation is correct and covered by
  `smoke_test_orchestration.py`, but that test runs in seconds, so
  everything lands on one calendar day. It hasn't been exercised against a
  week that actually spans multiple real days yet.
