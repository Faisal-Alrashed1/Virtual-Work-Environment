# Stage 2 — Onboarding Flow

_Added Sep 2026. First slice of Stage 2: the onboarding graph (CV file ->
agent-generated Q&A -> track approval -> agent-roster approval) is built,
smoke-tested (`backend/smoke_test_stage2_onboarding.py`, 27 checks,
mocked LLM), and now wired to real endpoints
(`backend/smoke_test_stage2_onboarding_router.py`, 24 checks through the
real API). Not yet wired to the frontend — that's the next branch. See
`docs/PROJECT_STATUS.md` for the overall project state._

## The flow, end to end

**1. CV upload**
A real file now (PDF/.docx), not paste-only — `app/agents/graph/
cv_parsing.py` extracts text via `pypdf`/`python-docx`, falling back to
plain text for anything else so the existing paste-based
`POST /users/me/cv` keeps working unchanged.

**2. Adaptive Q&A**
An agent (small model — see "Model routing" below) reads the parsed CV
and proposes 1-4 short follow-up questions about whatever it doesn't
cover well. Each question is independently skippable, and the graduate
can add free text of their own on top. Confirmed with Meshari:
agent-generated rather than a fixed list, so it scales to every track
without a per-major question bank.

**3. Track selection**
The same agent suggests an IT track from the CV + Q&A + free text, with a
short reasoning shown alongside. The graduate approves it as given or
overrides it — either way, the choice is theirs. Confirmed: CV-inferred
suggestion **and** required user approval, not one or the other.

**4. Agent roster selection**
The default three (Manager/Mentor/HR) are always included. On top of
those, the agent suggests optional extras from `AgentCatalog`, filtered
to what fits the approved track, and the graduate approves/edits that
list — same suggest-then-approve pattern as track selection, confirmed
with Meshari for UX consistency. The catalog is a table specifically so
it can grow past today's four entries (security reviewer, data reviewer,
career coach, DevOps) without a schema change.

**5. Onboarding complete**
Feeds into the existing weekly-cycle flow (`STAGE1_PRODUCT_FLOW.md`) —
unchanged in this slice.

## Model routing

Confirmed with Meshari: don't always use the paid model for mechanical
steps. `app/agents/graph/models.py` exposes two factories:

- `small_model()` — `settings.small_llm_model` (default
  `claude-haiku-4-5-20251001`). Used for all four onboarding-graph nodes
  above — question generation, track suggestion, agent suggestion. None
  of these need heavyweight reasoning.
- `reasoning_model()` — `settings.llm_model` (unchanged, `claude-sonnet-5`
  by default). Not used yet in this slice; reserved for the weekly-cycle
  graph port (Mentor review, Manager/HR synthesis) in a later branch.

## Framework

LangGraph (`StateGraph`), not the plain custom orchestrator Stage 1 used.
Rationale, discussed with Meshari: the existing `weekly_cycle.py` state
machine is already conceptually a graph, so porting it formalizes what
was hand-rolled rather than replacing it with something unrelated.
LangGraph also gives persistence (the checkpointer) and human-in-the-loop
(`interrupt()`) for free, both of which this flow needed anyway. LangChain
itself is used only for `ChatAnthropic` — no `create_agent`, no LCEL;
everything here is deliberate `StateGraph` control flow so nothing is
implicit.

**Human-in-the-loop.** Three of the graph's steps need the graduate's
input mid-flow — the Q&A, the track approval, the agent-roster approval.
Each is modeled as two nodes: one that calls the small model and produces
a suggestion, and one that calls `interrupt(payload)` to pause the graph
and hand that payload to the caller. Resuming means invoking the graph
again with `Command(resume=...)` against the same `thread_id` (the
graduate's `user_id`) — state persists in the checkpointer in between, so
closing the tab mid-onboarding and coming back later just works.

**Known gotcha, worth remembering when the router is built:** don't
resume with an empty dict (`Command(resume={})`). LangGraph appears to
treat a falsy resume value as "nothing to resume" and replays the same
interrupt instead of advancing — confirmed by trial while writing the
smoke test. Always resume with a dict that has at least one key, even if
its value is `None` (e.g. `{"track": None}` to mean "no override, keep
the suggestion").

## Schema changes — built

- **`TrackEnum`** extended with six Stage 2 majors (software engineering,
  data science/AI, cybersecurity, networks/infrastructure, information
  systems, cloud/DevOps), keeping `junior_dev` for existing Stage 1 rows.
- **`AgentType`** extended with the four optional agents.
- **`OnboardingStage`** (new enum) — `cv` / `qa` / `track` / `agents` /
  `complete`, tracks where a graduate is in the flow.
- **`User`** gained `onboarding_stage`, `suggested_track` (the pending
  CV-inferred suggestion), `track_confirmed`, `intro_text` (the free-text
  field), `onboarding_qa_json` (the Q&A log,
  `[{"question": ..., "answer": ... | None}]` — same list-of-dicts-in-JSON
  pattern as `Week.subtasks_plan_json`). The existing `track` column is
  untouched in shape — it only changes value once the graduate approves,
  so `UserOut.track` stays non-optional and every existing caller keeps
  working.
- **`AgentCatalog`** (new table) — the optional-agent catalog, seeded at
  startup (`app/agents/graph/catalog.py`, called from `main.py` right
  after `create_all`, idempotent).
- **`UserAgent`** (new table) — which optional agents a graduate has
  added.
- No Alembic migration — same `create_all`-on-startup pattern Stage 1
  used; still an open item, now touching more schema than before.

## What this means for the code — built

- `app/agents/graph/` (new package, additive — nothing in Stage 1's
  `app/agents/` orchestrator/weekly_cycle.py/manager.py/etc. changed):
  - `state.py` — `OnboardingState` TypedDict.
  - `models.py` — the two model-routing factories above.
  - `cv_parsing.py` — PDF/.docx/plain-text extraction.
  - `catalog.py` — seed data + `seed_agent_catalog`/`catalog_as_dicts`.
  - `onboarding_graph.py` — the graph itself: 7 nodes, 3 `interrupt()`
    calls, `build_onboarding_graph(checkpointer=None)` (defaults to
    `InMemorySaver` — fine for dev, but process-local; swap for a
    persistent saver before this goes further than a dev box, or a
    restart loses every in-progress onboarding).
- `requirements.txt` — added `langgraph`, `langchain-core`,
  `langchain-anthropic`, `pypdf`, `python-docx`. Also fixed a stray
  duplicate `anthropic>=0.25` line left over from an earlier edit.
- `config.py` — added `small_llm_model` setting.
- `main.py` — calls `seed_agent_catalog` at startup.
- `smoke_test_stage2_onboarding.py` — 27 checks: schema defaults, catalog
  seed/idempotency, the graph through all 3 interrupts on two different
  paths (override vs. approve-as-suggested), and writing the graph's
  output back onto the `User` row. All 6 existing smoke suites still pass
  unchanged (no regressions).
- **The router** (`app/routers/onboarding.py`) — `POST /onboarding/cv`
  (file upload, starts the graph), `POST /onboarding/qa`, `POST
  /onboarding/track`, `POST /onboarding/agents` (each resumes the graph
  one step), `GET /onboarding/state` (so the frontend can figure out
  where to resume without replaying the graph). The compiled graph is a
  module-level singleton, reused across requests — its checkpointer is
  still in-memory/process-local (same caveat as above).
  `smoke_test_stage2_onboarding_router.py` — 24 checks through the real
  HTTP API (register, login, file upload, all 4 steps, both an
  approve-as-suggested and an override/reject path). All 8 smoke suites
  now pass together (187 checks total).

## Not built yet

- **Frontend for any of this** — `/onboarding/cv` is still Stage 1's
  paste-only page.
- **The weekly-cycle graph port.** `weekly_cycle.py` still runs as the
  plain custom state machine from Stage 1, untouched. Porting it to a
  `StateGraph` and adding the `ask_agent` collaboration tool (Manager/HR
  actually consulting the Mentor mid-cascade, not just reading its stored
  summary — the "more collaborative, not just assigning tasks" goal) is
  the next meaningful piece after the router.
- **Own-project path** (user uploads/chooses their own project instead of
  the Manager's curriculum) — confirmed as in scope for Stage 2, optional
  alternative, not started.
- **User-uploaded project's Manager-planning implications** — once
  started, `plan_week` needs a second mode that plans around a given
  project's stack instead of improvising one, per track.
- A persistent checkpointer (see gotcha above) before this leaves a dev
  box.
