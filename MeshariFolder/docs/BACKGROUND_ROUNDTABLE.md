# The roundtable runs in the background

## Why

After the Mentor wrote its review, the review endpoint *also* waited for the whole
specialist discussion (up to three small-model turns, then the Manager's main-model
synthesis) before answering. Real-key runs showed what that cost: about **25-28 seconds
per submission** with three specialists (74.7s for 3 submissions, 84.8s for 3, 407s for 15).
The graduate stared at "Mentor is reviewing..." for the discussion they hadn't asked for
yet, when the thing they were waiting for, the Mentor's verdict, was ready much earlier.

## What changed

The endpoint now returns as soon as the Mentor's review is written. The discussion runs
**in the background** and each comment appears in the task thread as it is written; the
workspace refreshes the task every 2.5 seconds while it is going, and shows "Your team is
discussing this submission...". The Manager's synthesis still comes last.

```
before:  submit -> [Mentor ~10s] -> [3 specialists + Manager ~15s] -> response      (~25s wait)
after:   submit -> [Mentor ~10s] -> response                                        (~10s wait)
                                    then, in the background: specialist, specialist,
                                    specialist, Manager, each landing in the thread
```

Nothing about *what* is said changed: same order (Data, DevOps, Security, then the Manager),
same models, same prompts.

## How it works

1. `POST /agents/mentor/review/{id}` runs the Mentor as before, then calls
   `orchestrator.start_roundtable`. If the graduate has no specialists, nothing is scheduled
   and nothing ever shows as "running".
2. Otherwise `begin_roundtable` stamps `tasks.roundtable_started_at` (migration `0004`)
   **before the response is sent**, so the very first fetch after the review already says
   "running" (no gap in which the frontend would think it was over).
3. A FastAPI background task runs `run_roundtable_job` with **ids, not objects** (the
   request's database session is gone by then, so it opens its own). The existing
   `run_roundtable` commits each message as it is posted, which is what makes live progress
   possible without redesigning it.
4. When it ends, `_mark_finished` sets `roundtable_finished_at`. **Only the latest run may
   declare the task finished**: if a fast resubmission started a newer discussion meanwhile,
   the older one finishing leaves the task "running". A per-task lock also makes two
   discussions for one task go one after the other instead of interleaving in the thread.
5. `Task.roundtable_running` (on every task response) is: started, not yet finished, and not
   older than 3 minutes. The 3-minute limit is a safety net: a worker that died mid-discussion
   never records "finished", and a spinner that outlives its worker would be worse than none.

**The state is in the database, not in memory**, on purpose. An in-memory flag would say
"not running" to a request served by a different worker, and the frontend would stop
refreshing halfway through (the same trap as the old in-memory onboarding checkpointer).

## Frontend

`app/workspace/page.tsx` refreshes any task whose `roundtableRunning` is true every 2.5s,
merging messages by id (so a message the graduate has just sent can never blink away),
and stops when the server says it is done, or after 150 seconds regardless (then it clears
the note rather than leave "discussing..." on screen). The thread shows the indicator; a
one-line note appears in the workspace panel too, for screens where the thread is hidden.
English and Arabic.

## If something goes wrong

- **The discussion fails** (provider error, anything): logged, the task is marked finished so
  nothing spins, and the Mentor's review, already delivered, stands. A single specialist
  failing is skipped, as before.
- **The server restarts mid-discussion:** the job dies with it. The thread just lacks the
  remaining comments and the flag clears itself after 3 minutes. The discussion is not
  resumed (see "Not covered").
- **Arabic:** the language instruction still reaches the background calls (tested).

## What was verified

- `smoke_test_background_roundtable.py` (43 checks). The deterministic half covers what is
  stored, the flag in every state it can be in, no specialists = nothing scheduled, a failing
  discussion never breaks the review, two discussions are ordered and only the latest can
  finish, and Arabic in the background. The **wire half runs a real uvicorn server with slow
  models** and shows over HTTP that the review response arrives *before* the discussion
  finishes (0.01s against a discussion of about 4s), that the flag is already true on the
  next fetch, and that the thread grows message by message. A test client cannot show this
  (it always waits for background work), which is why that half exists.
- **Mutation-checked**, including the two that matter most: running it inline again with the
  state still recorded is caught *only* by the wire half (4.03s instead of 0.01s), and letting
  an older run finish the task is caught by the ordering checks.
- **Two real uvicorn workers on PostgreSQL:** the review was sent to one, and 14 polls, each
  on a fresh connection so they spread across both, saw the flag flip exactly once
  (running to done, never flickering) and the thread grow 1 to 5 messages.
- All 23 earlier suites pass unchanged; the frontend passes eslint and a full `next build`,
  and the new strings are in the compiled English and Arabic bundles.
- `e2e_real_llm.py` now sends the review over real HTTP and prints **what a graduate waits**
  (the Mentor's verdict time, and when the discussion finished).

## Not covered

- **Not seen in a browser.** The logic is tested and the bundle builds, but I have not watched
  comments appear on screen. Please do that once, in English and Arabic.
- **Real-model numbers are still to be measured.** The design guarantees the graduate waits
  for the Mentor only; how long the Mentor itself takes (about 8-15s on Claude) is unchanged.
  Run `python e2e_real_llm.py` and read "WHAT A GRADUATE WAITS".
- **Refresh, not push.** Comments appear within 2.5 seconds of being written. Server-sent
  events would make it instant; not worth it here.
- **The per-task lock is per process.** With several workers, two discussions for one task
  could interleave if a resubmission's review lands on a different worker within seconds of
  the first. Rare, harmless (comments appear in slightly mixed order), and the flag stays
  correct either way.
- **A discussion killed by a restart is not resumed.**
