# Onboarding resume and CV replacement

Two gaps from the "Not built yet" list, fixed together because they share a
cause: onboarding's real state lived in places that don't survive.

## What was wrong

- **A closed tab lost the questions.** The agent-generated Q&A was returned to
  the browser once and never saved server-side, so coming back meant starting
  over from the CV step (`reset` was all-or-nothing).
- **A server restart stranded graduates.** The onboarding graph's checkpointer is
  in-memory and per-process. The database said "stage: qa" but the graph had
  forgotten; the next request hit a thread with nothing to resume. The same
  happens with a redeploy, or with two API workers (each has its own memory).
- **Nothing could replace a CV after onboarding.** The board's "Update your CV"
  link led to the wizard, whose finished state offers only "go to board" or
  "redo everything".

## The design: the database is the source of truth

Every pause's output is saved on the `User` row as it happens:

| Pause | Saved (columns) |
|---|---|
| CV uploaded → questions generated | `onboarding_qa_json` (questions, answers still `null`) |
| Q&A submitted → track suggested | `suggested_track`, `suggested_track_reasoning`, `intro_text`, answers in `onboarding_qa_json` |
| Track approved → roster suggested | `track`, `track_confirmed`, `suggested_agent_ids_json` |

`GET /onboarding/resume` reads those columns and returns what the wizard needs
to re-draw the step the graduate stopped on. No LLM call, so the questions
are the *same* questions, not new ones.

When a step's answer arrives, `app/agents/graph/onboarding_resume.py` checks
the graph thread is paused where it should be. If it isn't (restart, other
worker, stale thread) it **rebuilds the thread from those columns** using
LangGraph's `update_state(..., as_node=...)`, which records "this node just
finished" without running it. The graph is left paused right before the human
step, and the answer resumes it normally. **Rebuilding makes zero LLM calls**
(asserted in `smoke_test_stage2_onboarding_resume.py`).

Why not just add a persistent LangGraph checkpointer (the item as originally
written)? It would fix restarts, but it adds a dependency per database
(`langgraph-checkpoint-sqlite` / `-postgres`, plus a driver change for
Postgres) and a second copy of state to keep consistent. Rebuilding from the
`User` row needs nothing new, works on any database, and also works with any
checkpointer you might add later.

## API changes

| Endpoint | Change |
|---|---|
| `GET /onboarding/resume` | **New.** `{onboarding_stage, resumable, questions, intro_text, suggested_track, reasoning, suggested_agents}`. `resumable: false` = start at the CV step. |
| `POST /onboarding/qa`, `/track`, `/agents` | Now **refuse out-of-order calls with 409** and rebuild the graph thread if needed. `/agents` also accepts `complete`, which is how a roster is edited after finishing. |
| `POST /onboarding/cv` | Starts a **clean** run (drops any stale thread and half-finished wizard output), saves the questions, and answers a corrupt/oversized file with 400/413 instead of a 500. |
| `POST /onboarding/reset` | Also clears the new saved fields and drops the thread. |
| `POST /users/me/cv/file` | **New.** Replace the CV with a PDF/Word/text file at any time after onboarding. Only the stored CV text changes: track, team, project and tasks are untouched; the Manager reads the new CV when it plans the *next* week. Refused (409) while the wizard is mid-flow, because its questions and track suggestion were built from the old CV. |

Migration `0002` adds the two new nullable columns (no backfill needed).

## Frontend

- `/onboarding/cv` asks `GET /onboarding/resume` on load and re-draws the saved
  step, with a "Welcome back" note. Catalog is fetched up front so every
  resumable step can reach the roster.
- New page `/profile/cv` ("Update your CV"). If the graduate is mid-wizard it
  says so and sends them back to resume, instead of dead-ending on a 409.
- The board's CV link points to `/profile/cv` when a CV exists, otherwise to the
  wizard. English and Arabic strings added (the build fails if either drifts).

## Things worth knowing

- **A double-clicked "continue" used to skip ahead.** Resuming the graph at the
  *next* pause with the previous step's payload made a second Q&A submit
  approve the suggested track silently. The stage guards close that.
- **Graduates already mid-wizard before this shipped.** Q&A stage: the questions
  were never saved, so `resumable` is false and they upload their CV again (a
  clear message says so). Track stage: works. Roster stage: works, but with no
  pre-selected suggestion; they pick from the full catalog.
- **The empty-dict gotcha still applies** — never resume with `Command(resume={})`.
  Every resume in the router sends a dict with at least one key.
- **If the graph gains or renames a node**, update `PAUSE_POINTS` in
  `onboarding_resume.py`. The resume suite fails loudly if it drifts.

## What was verified

`smoke_test_stage2_onboarding_resume.py` (54 checks) simulates a real restart by
swapping in a brand-new graph with an empty checkpointer, then walks the whole
wizard, restarting between every step. It also covers the 409 guards, the
double-click, legacy mid-wizard graduates, reset, a fresh CV upload replacing a
half-finished run, and every CV-replacement path (success, mid-wizard 409,
corrupt PDF 400, empty 400, oversized 413, no login 401). All backend suites pass
on SQLite and PostgreSQL 16; the frontend passes `eslint` and a full
`next build`, and the built routes return 200.

## Not covered

- **Typed-but-unsubmitted answers aren't saved** — only submitted steps resume.
  A graduate who types answers and closes the tab re-enters them.
- **The project step (step 5) isn't resumable.** It happens after the server
  already considers onboarding `complete`, so returning shows "you're all set".
- **Two browser tabs at once** aren't coordinated beyond the step guards (the
  second submit gets a 409, which is the safe outcome).
