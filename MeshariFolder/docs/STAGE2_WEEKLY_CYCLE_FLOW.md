# Stage 2 — Weekly-Cycle Collaboration

_Added Sep 2026. Second slice of Stage 2: the end-of-week cascade now
actually consults the Mentor (`ask_agent` — "more collaborative, not
just assigning tasks") instead of only reading its stored review text.
Smoke-tested at both the orchestration level (`smoke_test_orchestration.py`,
updated) and directly (`smoke_test_stage2_collaboration.py`, new). See
`docs/STAGE2_ONBOARDING_FLOW.md` for the first slice and
`docs/PROJECT_STATUS.md` for the overall project state._

## What changed

Stage 1's cascade (`STAGE1_PRODUCT_FLOW.md`): Manager writes the
week's progress review from the Mentor's *stored* per-subtask review
text, then HR writes the behavioral review the same way — both read-only
summarization, no real back-and-forth.

Stage 2: before writing, the Manager and HR each **ask the Mentor a
direct question** and get a fresh, specific answer — not a re-read of
what's already in the DB:

- Manager asks: *"How did the graduate do this week overall? Any
  patterns across the subtasks worth flagging?"*
- HR asks: *"Any concerns about consistency or engagement this week,
  beyond the raw attendance numbers?"*

Same two `Review` rows get created, same order, same shape — the
difference is entirely in what informs them.

## Framework — what's ported to LangGraph and what isn't

Only the **cascade** is a `StateGraph`
(`app/agents/graph/weekly_cycle_graph.py`, 4 nodes: consult -> Manager
writes -> consult -> HR writes). The rest of `weekly_cycle.py`'s state
machine — the idempotent "subtask still open, return it as-is" check,
releasing the next planned subtask — makes no LLM call either way, so
there's nothing a graph would add there; it stays the plain Python it
already was, untouched. The cascade is the one piece that's genuinely a
multi-step sequence with real dependencies, which is what a graph is
for.

No checkpointer/`thread_id`/`interrupt()` here, unlike the onboarding
graph — the cascade runs start to finish in one `invoke()`, no
human-in-the-loop pause needed.

## The `ask_agent` primitive

`app/agents/graph/collaboration.py`'s `ask_mentor(db, user, week,
question)` — deliberately **not** built on the new LangChain/small-model
tier from the onboarding graph. It uses `llm_client.call_with_tool`, the
same pattern `manager.py`/`mentor.py`/`hr.py` already use, because this
is a consult between two *existing* agents at their existing model tier
— introducing a different framework or model for it would be
inconsistent for no real benefit. What "ported to LangGraph" means here
is the cascade's sequencing, not every individual model call.

`manager.submit_week_progress` and `hr.run_behavioral_review` both
gained an optional `mentor_consult: str | None = None` param — the
Mentor's answer gets folded into the prompt when present. Defaults to
`None`, so calling either function without it (nothing outside the new
cascade graph does) behaves exactly as it did in Stage 1 — confirmed by
a dedicated backward-compatibility check in
`smoke_test_stage2_collaboration.py`.

## What this means for the code — built

- `app/agents/graph/collaboration.py` (new) — `ask_mentor` + its tool
  schema.
- `app/agents/graph/weekly_cycle_graph.py` (new) — the 4-node cascade
  `StateGraph`, `run_end_of_week_cascade(db, user, week)` as the
  drop-in replacement for the two flat calls.
- `app/agents/manager.py` / `app/agents/hr.py` — `mentor_consult` param
  added to `submit_week_progress`/`run_behavioral_review`. Nothing else
  in either file changed.
- `app/agents/weekly_cycle.py` — the cascade's two flat calls replaced
  with one call to `run_end_of_week_cascade`. Nothing else in this file
  changed; the rest of `get_next_task` is untouched.
- `smoke_test_orchestration.py` — updated: a new mock for the 2
  collaboration calls (patched separately from Manager/Mentor/HR's own
  mocks, so it doesn't interfere with their existing call counts/
  side-effect lists), plus an assertion that the Mentor was consulted
  exactly twice. All prior assertions in this file needed no changes —
  same review counts, same kinds, same dashboard numbers.
- `smoke_test_stage2_collaboration.py` (new) — 9 checks, ORM-level:
  proves the consult questions are what's documented above, proves the
  Mentor's actual reply text reaches the Manager/HR prompts (not just
  that a `Review` gets written), and proves the backward-compatibility
  default.
- All 9 smoke suites pass together — 197 checks total, no regressions.

## Not built yet

- **The own-project path** — confirmed in scope for Stage 2, optional
  alternative to the Manager's improvised curriculum, not started. Once
  it is, `manager.plan_week` needs a second mode that plans around a
  given project's stack instead of improvising one.
- **Frontend** — nothing in `frontend/` reflects any of Stage 2 yet
  (onboarding or this).
- **A persistent checkpointer** for the onboarding graph (see
  `STAGE2_ONBOARDING_FLOW.md`) — unrelated to this piece, still open.
- Broader agent-to-agent collaboration beyond the cascade (e.g. the
  Mentor proactively flagging a concern mid-week instead of only being
  asked at the end of it) — not attempted here; this slice is the
  end-of-week consult specifically.
