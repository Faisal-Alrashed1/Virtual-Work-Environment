# Stage 1 Product Flow — Weekly Cycles

_Added Sep 2026. **Update:** fully built now, both schema and
orchestration. `Project`, `Week`, `Task.deadline`/`submitted_at`/
`completed_at`/`is_late`, and `Review.kind`/`week_id` exist in
`backend/app/models.py`; `backend/app/agents/weekly_cycle.py`'s
`get_next_task` is the state machine that actually drives the whole
Project -> Week -> subtask -> end-of-week cascade -> next Week lifecycle,
called from the existing `POST /agents/manager/assign-task` (no new
endpoint needed). Every open question below is resolved — confirmed with
Meshari directly, not just a working default. See `docs/PROJECT_STATUS.md`
for the fuller picture and `backend/app/agents/README.md`'s "Still open"
for what's left (task bank content, frontend wiring, multi-day attendance
testing)._

## The flow, end to end

**1. Onboarding**
CV intake (already built — `/onboarding/cv`, paste-only, skippable).
Optionally, later: a short Q&A or an extra selectable field during intake
— deferred for now, not needed yet.

**2. Orientation**
Before formal work starts, the user gets a walkthrough of how Venv works,
and is introduced to the "main project" they'll be working on. Not built
— this is a new UI step (`/board` today assumes the user already knows
what they're looking at).

**3. Formal work — week cycles**
Work runs in cycles of 5 workdays. Each week:
- The Manager first defines a "big task" (the week's overarching goal),
  then breaks it into 5 subtasks.
- The user receives subtasks **one at a time per topic** — gradual
  progression, not all 5 dropped on the board at once. Built:
  `Week.next_subtask_index` releases them one at a time as each prior
  one is approved — see `weekly_cycle.get_next_task`.
- Each task has a specific deadline. Completing it after that deadline
  marks it **late**. Example given: due October 1st, completed October
  2nd → late.
- Every task is reviewed until fully completed — the Mentor reviews each
  submitted subtask, and only moves it to `reviewed` on an `approved`
  verdict; `needs_changes` sends it back for resubmission and re-review.
- The Mentor is meant to work with the user throughout the week, not
  only through the task breakdown that the Manager does.

**4. End of week — the evaluation cascade**
Three steps, in this order:
1. **Mentor** has already been reviewing each subtask as it's submitted
   through the week.
2. **Manager** reviews the user's overall progress for the week, based
   on the Mentor's summary of that week's reviews.
3. **HR** evaluates behavioral aspects — attendance, consistency, and
   absence — after the Manager's review. Late submissions (from step 3
   above) feed into this behavioral evaluation.

## Task source

Two ways a task's content originates:
- **Companies** may upload tasks directly, or assign them to the agent
  (the agent then presents/formulates the task from what the company
  gave it). This is the near-term source — ties directly into the
  existing "task bank content" open item; the bank isn't purely
  Manager-improvised, it's meant to be sourced from real companies.
- **Phase 3**: the user can upload their own project to work on instead.

*Open question worth reconciling: `Project-Summary.md`'s three-stage
roadmap calls Stage 3 "companies build their own [environments]", while
this "Phase 3" is described as the user uploading their own project —
similar numbering, not obviously the same concept. Worth a quick check
with Meshari on whether "Phase 3" here is the same milestone as "Stage 3"
elsewhere, or a distinct sub-phase within Stage 1's task-sourcing model.*

## What this means for the schema — built

- **`Project`** — the "main project" introduced during orientation, what a
  week's big task belongs to. `title`, `description`, `status`
  (active/completed), owned by a `user_id`.
- **`Week`** — one 5-workday cycle within a `Project`: `week_number`,
  `status`, `big_task_title`/`big_task_description`, `started_at`/
  `target_end_at`/`ended_at`. The 5 subtasks the Manager plans up front
  live in `subtasks_plan_json` (each entry also carries its own
  `deadline`, decided at planning time — see `scheduling.py`) and get
  turned into real `Task` rows one at a time via `next_subtask_index` as
  each prior one is approved.
- **`Task.deadline` / `submitted_at` / `completed_at` / `is_late`** —
  `is_late` is a computed property (`completed_at > deadline`), `None`
  until both exist. Judged against `completed_at`, not `submitted_at`, per
  the Oct 1 / Oct 2 example, since a submission can bounce back and get
  resubmitted before it's actually done.
- **Iterative review.** `Mentor.review_task` sets `Task.status` to
  `reviewed` (+ stamps `completed_at`) only on `approved`; `needs_changes`
  sends it back to `in_progress` so the graduate can revise and resubmit.
- **`Review.kind`** (`task_review` / `week_progress` / `behavioral` /
  `skills_rollup`) and **`Review.week_id`** — the Manager's end-of-week
  progress review and HR's behavioral evaluation share the `reviews` table
  with the existing Mentor/rollup reviews.
- **HR behavioral evaluation** — attendance/absence/lateness are computed
  in code from existing Task/TaskMessage timestamps (a day counts if it
  had a status change, submission, or resubmission — see `hr.py`'s
  `_active_days`), and HR's LLM call only writes the narrative + a
  consistency rating on top of those numbers.

## What this means for orchestration — built

`backend/app/agents/weekly_cycle.py`'s `get_next_task(db, user)` is the
state machine, called from the existing `POST /agents/manager/assign-task`:

1. No active `Project` yet -> `manager.create_project`, then plan Week 1.
2. Active `Week`, current subtask still open (not yet approved) -> return
   it as-is. Idempotent — asking again doesn't create a duplicate or call
   the LLM again.
3. Current subtask approved, more planned this week -> hand out the next
   one (`manager.release_next_subtask` — no LLM call, the plan was already
   decided).
4. All 5 approved -> the end-of-week cascade: `manager.submit_week_progress`,
   then `hr.run_behavioral_review` (that order, per the confirmed cascade),
   close the `Week`, plan and start the next one, and hand out its first
   subtask — all in the same call, so the graduate always gets a task back.

Tested end to end (not just at the schema level) by
`backend/smoke_test_orchestration.py` — bootstrap, idempotency, five
subtasks through to a full cascade into week 2, all through the real API.

## Confirmed decisions (previously open questions)

All settled directly with Meshari:

1. **Task source**: for this project, LLM-generated by the Manager — not
   sourced from a task bank. Companies uploading tasks and Phase 3's
   user-uploaded-project flow are confirmed as separate, later paths, not
   this bootcamp's scope. `subtasks_plan_json`'s shape doesn't care where
   the subtasks came from, so a populated task bank can feed it later
   without a schema change.
2. **Attendance** = "meaningful progress" — a status change, a submission,
   or a resubmission counts as a day present; just opening the app doesn't.
   Fully derivable from existing timestamps, no new tracking needed.
3. **A "week" is calendar-based**, not self-paced — reversing the earlier
   working default. Attendance/absence only make sense against a real
   calendar. Saudi workweek is Sunday-Thursday (`scheduling.py`), not
   Monday-Friday.
4. **Phase 3 vs. Stage 3 naming** — still not explicitly reconciled, but
   no longer blocks anything: both are confirmed as later, out-of-scope
   paths regardless of what they're eventually called.
