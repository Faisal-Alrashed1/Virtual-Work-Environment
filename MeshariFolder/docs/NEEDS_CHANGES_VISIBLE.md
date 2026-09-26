# "Needs changes" is now visible

## What was wrong

Your loop is: submit -> the Mentor reviews -> approved, or *needs changes* ->
revise and resubmit. When the Mentor asks for changes, the task goes back to
`in_progress` (`app/agents/mentor.py`). But `in_progress` is also what a task
looks like when you have simply *started* it and submitted nothing. So the
board, the task rail, the workspace and the home dashboard could not tell "I'm
working on this" from "the Mentor told me to fix something" - the state that
matters most in the demo was silent.

## The fix: derive it, don't store it

`Task.needs_changes` and `Task.revision_count` (in `app/models.py`) are computed
from the task's reviews:

- `needs_changes` is true while the task is `in_progress` **and** the Mentor's
  latest verdict on it was `needs_changes`. It goes false the moment the
  graduate resubmits (the status leaves `in_progress`), and stays false after
  approval.
- `revision_count` is how many times the Mentor has asked for changes on the
  task. It is kept after approval (2 means it took three attempts), which is a
  useful thing to show HR and the judges.

No new column and no migration: a stored flag could disagree with the reviews
after any edge case, whereas a value derived from them cannot. The migration
drift guard confirms the schema is unchanged. Both fields are on `TaskOut`, so
every task endpoint returns them. `GET /tasks` eager-loads the reviews, so
listing N tasks costs one extra query, not N (asserted in the test).

## Where it shows up

- **Task rail** (workspace): a red dot and a `Needs changes - revision N` badge on
  the task, still in the In-progress group.
- **Workspace**: a banner above the submit form - "The Mentor asked for
  changes", the revision number, and a pointer to the feedback in the thread.
- **Home dashboard**: the current-task card says "Needs changes" in red instead
  of "In progress".

English and Arabic (the build fails if either dictionary drifts).

## What was verified

`smoke_test_needs_changes.py` (29 checks): a task's whole life (fresh, started,
submitted, bounced, resubmitted, bounced again, approved); a started-but-never-
reviewed task and an untouched task are *not* flagged; the list endpoint carries
the fields; and listing tasks loads reviews in one query. Frontend: eslint clean,
full `next build`, built routes return 200, and the new strings are in the
compiled English and Arabic bundles.

## Not covered

- I have not looked at it in a browser: the badge/banner styling uses the
  existing danger colour and the same classes as neighbouring components, but
  the visual result is unchecked.
- The board's *graph* view (React Flow nodes) doesn't show per-task status today,
  so there was nothing to change there. If you want the Manager node to flag a
  bounced task, that is a small follow-up.
