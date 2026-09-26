# Hardening the onboarding graph's tool calls

## What a real run found

Running `e2e_real_llm.py` (real keys, no mocking) surfaced two things no mocked test
could:

1. **DeepSeek returned 5 follow-up questions where the schema caps it at 4**
   (`QUESTIONS_TOOL`'s `maxItems: 4`). Nothing was checking it — the e2e script's own
   assertion (`1-4 questions`) simply failed.
2. Reading the code around that call surfaced something worse: **`submit_qa` and
   `approve_track` both do `TrackEnum(result["suggested_track"])` with no
   try/except.** If a model ever returns a track string outside the six known values
   (a typo, a different casing, an invented one), that is an **uncaught `ValueError`**
   — a 500 on the graduate's very first onboarding screen.

## Why the earlier hardening pass missed this

`docs/LLM_PROVIDER_FAILOVER.md` ("Malformed tool output") already built repair/check/
retry protection — but only for `llm_client.call_with_tool`, the path the Manager,
Mentor, HR and roundtable all go through. **The onboarding graph is a separate
tool-calling path** (LangChain's `model.bind_tools(...).invoke(...)`, in
`onboarding_graph.py`'s `_forced_tool_call`), built before that hardening pass and
never brought into it. It had no repair, no structural checks, and retried only on
outright connectivity errors — never on a response that was simply unusable.

## The fix

`_forced_tool_call` now mirrors `call_with_tool` exactly, reusing the same
`agents/tool_output.py` functions:

1. **Repair** what can be fixed for certain (a JSON-string list, a numeric string).
2. **Check** structural problems (a required field missing, an array shorter than the
   schema's `minItems`, the model not calling the tool at all).
3. An optional **`validate`** hook per tool, for anything schema-shape alone can't
   catch.
4. Unusable output is **retried on the same provider** (`MAX_ATTEMPTS_PER_PROVIDER`,
   shared with `call_with_tool`), then the **next provider**; only once every provider
   is exhausted does it raise — a `RuntimeError` prefixed with `ALL_PROVIDERS_FAILED`,
   which `app/main.py`'s existing handler turns into a clean 503, never a 500.

Applied per tool:

- **`generate_questions`**: too many questions is **truncated** to the schema's own
  `maxItems`, not retried — free, graceful, the same precedent as the Manager's
  `subtasks[:5]` and the Mentor's `comments[:MAX_COMMENTS]` (`rubric.py`). There is no
  legitimate reason to spend a retry asking a model to count to 4.
- **`suggest_track`**: a new `_check_track` validates the value against the six known
  tracks (`validate=`) — **retried**, since there is no safe way to auto-correct an
  invented track. This is what closes the uncaught-`ValueError` crash.
- **`suggest_agents`**: already filtered its output against the real catalog before
  this change (`[a for a in args["agent_ids"] if a in valid_ids]`) — safe already, no
  crash risk. It was also missing `with_language()` (harmless today, since it returns
  only ids, no free text — but it made the "every onboarding call is localized" claim
  in `docs/AGENT_LANGUAGE.md` not quite true, since it was never actually exercised by
  the Arabic test). Added and now tested.

## What was verified

`smoke_test_onboarding_graph_hardening.py` (16 checks): the repair/truncate/retry/
validate logic directly on `_forced_tool_call`; a connectivity error still fails over
immediately, unretried; and, through the real onboarding endpoints with a scripted
fake model — the exact reported bug (5 questions -> 4 delivered, the first 4), an
invalid track recovering on retry, an always-invalid track giving a clean 503 (not the
original crash), all 3 onboarding calls carrying the language instruction, and a
healthy model never being retried needlessly (no hidden latency/cost regression).
Mutation-checked: removing the truncation, the track validate hook, or the retry loop
each reproduces exactly the bug being fixed (confirmed by re-running with the fix
reverted — the truncation-removal is a clean `[FAIL]`; the validate-removal and
retry-removal each crash with the *original* traceback, `ValueError: '...' is not a
valid TrackEnum` and the original malformed-output `RuntimeError`, proving the fix is
load-bearing, not decorative).

All 26 suites (733 checks) pass on SQLite; app suites pass on PostgreSQL 16.

## Not covered

- **Not yet re-run against real DeepSeek** to confirm it no longer produces 5
  questions in practice (the fix truncates regardless of *why* a model overshoots, so
  it should hold for any provider's quirk, but hasn't been observed with real DeepSeek
  since the fix).
- **`suggest_agents`'s hallucinated-id filtering** was already safe; no test existed
  for it before this pass and none was added now — it is unchanged behaviour, out of
  this fix's scope.
