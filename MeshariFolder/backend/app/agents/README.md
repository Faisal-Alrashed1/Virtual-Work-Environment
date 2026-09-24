# Agents

Manager, Mentor, HR, and the Meeting Room drive the full weekly-cycle
flow from `docs/STAGE1_PRODUCT_FLOW.md`. Stage 2 (`docs/STAGE2_*.md`,
one doc per slice, listed in `docs/PROJECT_STATUS.md`) added: onboarding
(a LangGraph agent), real collaboration in the weekly cascade, a
selectable optional-agent roster, and the **agent roundtable** —
optional agents discussing a submission with each other, not just
posting isolated comments.

LLM: Anthropic Claude. Two model tiers, both configurable via `.env`:
`LLM_MODEL` (default `claude-sonnet-5`) for primary judgment calls —
Mentor's review, Manager's plans and progress writeups, the roundtable's
Manager synthesis — and `SMALL_LLM_MODEL` (default
`claude-haiku-4-5-20251001`) for cheap/mechanical steps — onboarding's
suggestions, the roundtable's specialist comments. See
`docs/STAGE2_ONBOARDING_FLOW.md` for the reasoning.

Orchestration is mostly a plain custom router (`orchestrator.py`) plus a
small state machine (`weekly_cycle.py`) — not a framework, for the
original three agents sharing one Employee File. Stage 2 introduced
**LangGraph** (`graph/` subpackage) specifically for onboarding's
human-in-the-loop flow and the weekly cascade's sequencing — see
`docs/STAGE2_ONBOARDING_FLOW.md` and `STAGE2_WEEKLY_CYCLE_FLOW.md` for
why those two pieces got the framework treatment and the rest stayed
plain Python.

## The agents

- **Manager** (`manager.py`) — introduces the graduate's main `Project`
  (`create_project`, skipped entirely if the graduate brought their own
  via `POST /projects/own` — see `STAGE2_OWN_PROJECT.md`); plans each
  `Week` as a big task + exactly 5 subtasks (`plan_week`, deadlines
  against the Saudi Sun-Thu workweek — `app/scheduling.py`); hands out
  one subtask at a time (`release_next_subtask`, no LLM call); replies in
  a task's thread (`respond_in_thread`); writes the end-of-week progress
  review (`submit_week_progress`) — now informed by actually consulting
  the Mentor first (`mentor_consult` param, see below); and, in the
  roundtable, reads the whole team's discussion and posts a synthesis.
- **Mentor** (`mentor.py`) — reads a submission (GitHub link via
  `github_client.py`, free text, and/or image attachments as real vision
  content blocks — any combination, not github_link-specifically since
  Stage 2), writes a structured `Review` (`kind="task_review"`,
  `metrics_json` = verdict + rubric + inline comments — `tools.py`'s
  `SUBMIT_REVIEW_TOOL`), posts a summary message, and moves the task to
  `reviewed` on `approved` or back to `in_progress` on `needs_changes`
  (iterative review).
- **HR** (`hr.py`) — `run_rollup` reads Mentor review history into
  `EmployeeFile` (`skills_json`/`strengths_json`/`growth_areas_json`/
  `summary_text`) plus a `skills_rollup` `Review`. `run_behavioral_review`
  writes the end-of-week behavioral evaluation from computed
  attendance/lateness numbers (`_active_days`) plus, since Stage 2, the
  Mentor's direct answer when actually asked about consistency
  (`mentor_consult`).
- **Meeting** (`meeting.py`) — the task-free direct chat (`/meeting`).
  `PERSONA` (public — shared with `co_reviewers.py`/`roundtable.py`) has
  an entry for all seven `AgentType`s now, not just the default three.
  `is_on_users_team` gates access: the default three are always
  available, an optional agent only if it's actually on the graduate's
  roster (`UserAgent`) — the router 403s otherwise.
- **weekly_cycle.py** — `get_next_task(db, user)`, the state machine:
  bootstrap on the first call (skipped if an own-project already exists),
  return the same in-flight subtask idempotently, release the next one
  once approved, or run the end-of-week cascade and roll into the next
  week. Since Stage 2, the cascade itself
  (`graph/weekly_cycle_graph.py`) is a small LangGraph `StateGraph` — see
  `STAGE2_WEEKLY_CYCLE_FLOW.md` for why only that piece, not the whole
  state machine, moved to a graph.
- **co_reviewers.py** — the original, simpler parallel version of
  optional agents reviewing a submission: each one comments independently,
  no awareness of the others. Superseded by the roundtable below as
  what actually runs, but kept as a documented fallback with its own
  unit test.
- **roundtable.py** — the current version, and the deeper "more
  collaborative" piece. After the Mentor's review, each optional
  specialist on the roster (Security Reviewer/Data Reviewer/DevOps)
  responds **in sequence, seeing the Mentor's review and every prior
  specialist's turn** — building on, agreeing with, or pushing back on
  each other — then the Manager reads the whole discussion and
  synthesizes what matters most. Career Coach is deliberately excluded
  (not a per-task code review; stays meeting-room-only). One bounded pass,
  deterministic speaker order, best-effort per turn. See
  `docs/STAGE2_ROUNDTABLE.md`.
  - **Security Reviewer** (`security_reviewer.py`) and **Data Reviewer**
    (`data_reviewer.py`) are upgraded from a free-text persona comment to
    a real reviewer each: their own system prompt, the actual content of
    uploaded files (read via `submission_files.py`) plus real repo content
    fetched via `github_client.py` (dependency/config files for
    Security; notebook code cells for Data), a deterministic code-level
    check ahead of the LLM call (a committed `.env` for Security; no
    visible eval/test file for Data — same "compute the fact in code,
    let the LLM narrate it" pattern as `hr.py`'s `_active_days`), and
    structured output (`tools.SUBMIT_SECURITY_REVIEW_TOOL` /
    `SUBMIT_DATA_REVIEW_TOOL`: verdict/risk_level/findings, not a
    paragraph) stored as a `Review` with `kind=SPECIALIST_REVIEW`,
    including `reviewed_files`/`unreadable_files` so every verdict shows
    what it was based on. If nothing readable was submitted (notes only,
    or only a zip/image), no LLM call is made and the verdict is
    `not_reviewed` with a message telling the graduate what to upload —
    never a guessed "clear". Before the LLM call, `static_checks.py` runs
    rule-based checks over the same content (hardcoded secrets for
    Security; preprocessing fit before the split / scoring on training
    data for Data). A match is always stored as a finding (marked
    `"source": "static_check"`, secret values masked) and leads the
    thread message, even if the model missed it — in live testing the
    small model caught an SQL injection but missed two hardcoded
    secrets beside it. Both
    still take `discussion_so_far` and stay part of the actual roundtable
    conversation — the structured output is in addition to, not instead
    of, being a real teammate in the discussion. DevOps is unchanged
    (still the original free-text pass) — only these two were in scope
    for this upgrade.

## graph/ — the LangGraph agents

- **`onboarding_graph.py`** — CV → agent-generated Q&A → track
  suggestion+approval → agent-roster suggestion+approval, with
  `interrupt()` pausing the graph at each human-in-the-loop point. Driven
  by `routers/onboarding.py`.
- **`weekly_cycle_graph.py`** — the end-of-week cascade: consult the
  Mentor → Manager writes → consult the Mentor → HR writes.
- **`collaboration.py`** — `ask_mentor`, the primitive both of the above
  use to actually consult the Mentor rather than just reading its stored
  review text.
- **`models.py`** — the two model-routing factories (`small_model()`,
  `reasoning_model()`).
- **`catalog.py`** — the optional-agent catalog seed data + read helpers.
- **`cv_parsing.py`** — PDF/.docx/plain-text extraction for the CV
  upload step.

## Files

```
agents/
├── llm_client.py     # thin Anthropic wrapper — swap providers here only;
│                      #   call_agentic takes an optional model= override
│                      #   for the small-model tier (roundtable, co_reviewers)
├── tools.py           # tool schemas (create_project, plan_week, post_message,
│                       #   submit_review, update_employee_file, submit_week_progress,
│                       #   submit_behavioral_review)
├── github_client.py   # unauthenticated GitHub API client for Mentor's repo context
├── manager.py         # create_project, plan_week, release_next_subtask,
│                       #   submit_week_progress, respond_in_thread
├── mentor.py          # review_task — link/text/images, any combination
├── hr.py              # run_rollup, run_behavioral_review
├── meeting.py         # send_message, get_history, PERSONA, is_on_users_team
├── security_reviewer.py # review_task — real repo/dependency analysis, structured findings
├── data_reviewer.py     # review_task — real notebook analysis, structured findings
├── submission_files.py  # reads uploaded attachments' content (text/code/notebooks) —
│                         #   shared; Mentor/Manager still only see names today
├── static_checks.py     # rule-based checks run before the LLM (hardcoded secrets,
│                         #   data leakage) — a match is always kept in the findings
├── co_reviewers.py     # the simpler parallel fallback (see roundtable.py)
├── roundtable.py       # the real thing — sequential discussion + Manager synthesis
├── weekly_cycle.py     # get_next_task — the Project/Week/subtask/cascade state machine
├── orchestrator.py     # routes API calls to the above — see routers/agents.py
└── graph/               # LangGraph agents — onboarding, the cascade's sequencing
```

`app/scheduling.py` (not in `agents/` — plain date math, no LLM/DB)
computes Saudi workweek (Sun-Thu) deadlines that `plan_week` uses.
`app/storage.py` (also not in `agents/`) handles task-attachment files on
disk, read by `mentor.py`/`roundtable.py` for vision content blocks.

Triggered via `POST /agents/manager/assign-task`, `POST
/agents/manager/reply/{task_id}`, `POST /agents/mentor/review/{task_id}`
(runs the Mentor's review *and* the roundtable), `POST /agents/hr/rollup`,
plus the full `/onboarding/*` and `/meeting/{agent}` surfaces. Read
results back via `GET /projects/me`, `GET /tasks/{task_id}/review`, `GET
/users/me/employee-file`, `/reviews`, `/agents`.

Test with the full smoke suite listed in `docs/PROJECT_STATUS.md` — in
particular `smoke_test_stage2_roundtable.py` (proves the specialists
actually see each other's prior turns, not just that messages get
written) and `smoke_test_orchestration.py` (the original weekly cycle,
end to end, still the one that proves the core loop works).

## Still open

- **Task bank**: `plan_week`'s subtasks are still LLM-improvised, not
  sourced from a curated bank — confirmed as the intended behavior for
  now, not a gap.
- **Rubric categories are a first pass**, not a finalized contract — see
  `tools.py`'s comment above `SUBMIT_REVIEW_TOOL`.
- **`needs_changes` is visually silent on the board** — still sends the
  task back to `in_progress`, same column as a never-reviewed task.
- **Roundtable specialists don't get vision** — only the Mentor's review
  sees image attachments as real content blocks.
- **Attendance is only meaningfully testable over real elapsed days** —
  correct and covered by `smoke_test_orchestration.py`, but that test
  runs in seconds, so it hasn't been exercised against a week that
  actually spans multiple real days.
- **Onboarding's checkpointer is in-memory** — fine for one dev box,
  loses in-progress onboarding on a restart.
