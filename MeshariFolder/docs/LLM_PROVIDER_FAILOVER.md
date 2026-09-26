# Multi-Provider LLM Failover

## Overview

The backend now supports multiple LLM providers instead of being hard-wired to Anthropic. Each developer configures their own **priority-ordered list** of providers in `backend/.env`. At runtime, the app tries each provider in order and automatically falls over to the next one if a provider is unavailable (missing/invalid key, no credit, rate-limited, or unreachable).

This makes the platform provider-agnostic and easy to extend with new providers in the future.

## Supported Providers

- Anthropic
- OpenAI
- DeepSeek
- Qwen (OpenAI-compatible API)

## Configuration

Set your own priority order in `backend/.env`:

```env
LLM_PROVIDER_PRIORITY=anthropic,openai,deepseek,qwen

ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
DEEPSEEK_API_KEY=...
QWEN_API_KEY=...
```

- List 2-4 providers, in the order you want them tried.
- Only providers with a non-empty API key are used; the rest are skipped automatically.
- Each teammate can use a different set/order depending on which keys they have (e.g. Qwen first, DeepSeek second).

## Tier-aware routing — choosing *which* model intelligently, not just failing over

Every call in the app already carries a **tier**: `"main"` for real judgment
(Mentor's review, the Manager's plans and end-of-week synthesis, HR's
behavioral evaluation) or `"small"` for cheap, mechanical steps (onboarding's
suggestions, a roundtable specialist's quick comment). Tier already picked
the right *model size* within one provider (`ANTHROPIC_SMALL_MODEL` vs
`ANTHROPIC_MODEL`, etc.) — what was still missing was letting different tiers
prefer different *providers* too, not just a flat priority list applied to
every call regardless of complexity.

Two optional overrides make that real:

```env
LLM_PROVIDER_PRIORITY_MAIN=anthropic,openai
LLM_PROVIDER_PRIORITY_SMALL=qwen,deepseek,anthropic
```

- `LLM_PROVIDER_PRIORITY_MAIN` is used for any `tier="main"` call.
- `LLM_PROVIDER_PRIORITY_SMALL` is used for any `tier="small"` call.
- Either left blank falls back to the shared `LLM_PROVIDER_PRIORITY` for that
  tier — fully backward compatible with a single flat list.
- Same "skip anything without a key" rule applies to both.

This is genuinely different from just swapping model names: a developer can
route the Mentor's review and the Manager's synthesis to their strongest,
most reliable provider, while sending onboarding's throwaway suggestions and
the roundtable specialists' quick takes to whichever provider is fastest or
cheapest — real cost/quality tradeoffs, made intelligently per call rather
than uniformly.

## How Failover Works

1. The app resolves the provider chain for the call's tier — the
   tier-specific priority if set, else the shared `LLM_PROVIDER_PRIORITY` —
   keeping only providers that have a key set.
2. It calls the first provider in that chain.
3. If that call fails with an availability-related error (auth error, rate limit, no credit, connection error), it automatically retries with the next provider in the chain.
4. If all configured providers fail, the API returns a clear `503` error instead of crashing.
5. If no provider has a key configured at all, the API returns a `503` explaining that `LLM_PROVIDER_PRIORITY` (or the tier-specific override) / API keys need to be set.

## Files Changed

| File | Change |
|---|---|
| `backend/app/config.py` | Added per-provider settings (keys, models, base URLs), `LLM_PROVIDER_PRIORITY`, and the tier-specific `LLM_PROVIDER_PRIORITY_MAIN`/`_SMALL` overrides. |
| `backend/.env.example` | Added example values for all providers, the shared priority variable, and the tier-specific overrides. |
| `backend/requirements.txt` | Added `openai` and `langchain-openai`. |
| `backend/app/agents/llm_client.py` | Core provider abstraction: `resolve_provider_chain(tier)` resolves the right chain per tier, and runs the failover loop for both tool calls and agentic replies. `call_with_tool` also gained a `tier` param (defaults to `"main"`, so every existing caller is unaffected) for symmetry with `call_agentic`. |
| `backend/app/agents/manager.py` | Updated to use the normalized reply shape from `llm_client`. |
| `backend/app/agents/co_reviewers.py` | Updated to use the normalized reply shape; already correctly passes `tier="small"`. |
| `backend/app/agents/roundtable.py` | Updated to use the normalized reply shape; specialists pass `tier="small"`, the Manager's synthesis passes `tier="main"` — now this actually changes which *provider* chain gets tried too, not just the model name. |
| `backend/app/agents/meeting.py` | Migrated off the removed single-client function to the new failover client. |
| `backend/app/agents/graph/models.py` | LangGraph models now built as a provider chain instead of a single model, correctly threaded through the tier the caller asked for. |
| `backend/app/agents/graph/onboarding_graph.py` | Tool schemas and forced tool-calling updated to work across providers with failover. |
| `backend/app/main.py` | Added a clean `503` error handler for "all providers failed" / missing configuration. |

## Terminal logging — which provider/model actually answered

Every `call_with_tool`/`call_agentic` call (and the LangGraph onboarding
path) logs one line when it gets an answer, and one line per provider
skipped via failover:

```
[LLM] anthropic (claude-sonnet-5, main-tier) -> reply
[LLM] qwen unavailable (401 invalid api key) — failing over
[LLM] deepseek (deepseek-chat, small-tier) -> generate_questions
```

Configured with its own handler/level (`logging.getLogger("venv.llm")`,
`propagate = False`) rather than relying on uvicorn's own logging setup —
by default, uvicorn only configures *its own* loggers for INFO output;
any other logger's INFO records get silently dropped unless something
explicitly enables them. Without this, these lines would produce no
terminal output at all despite the code running correctly — confirmed by
testing a plain `logging.getLogger(...).info(...)` call with zero config
first, seeing it swallowed, then fixing it this way.



- No code changes are required to add a new provider's *model choice* - just add its key and put it in the relevant priority variable(s).
- Adding a brand-new provider (beyond the four above) requires adding its settings in `config.py` and its client setup in `llm_client.py`.
- **A real bug caught while adding tier-aware routing**: `call_agentic` and `graph/models.py`'s `_model_chain` both already accepted a `tier` argument, but neither actually passed it into `resolve_provider_chain()` — so tier was silently only ever affecting the model *name* within a provider, never which providers got tried at all. Fixed as part of this same change; see `smoke_test_llm_provider_routing.py` for the regression test that would have caught it.

## Malformed tool output: repair, retry, fail over

Failover above handles a provider being *down*. This handles a provider being *up but
wrong* - which only real models do, and no mocked test can show.

**What happened.** Running the real models (`e2e_real_llm.py`), Claude returned the
Manager's `subtasks` as a JSON *string* instead of a list. `len()` of that string is
large, so the "at least 5 subtasks" check passed; the loop then iterated single
characters and `s["title"]` raised `TypeError: string indices must be integers`. A
random 500 in the middle of "Ask manager", about one run in a few.

**What `llm_client.call_with_tool` does now** (code in `agents/tool_output.py`):

1. **Repair** what can be repaired with certainty: a JSON string where the schema wants
   a list/object (the bug above), a number sent as a string (`"4"` -> `4`; `"4.5"` is
   *not* truncated to an integer). Every repair is logged, so you can see how often a
   model does it.
2. **Check** what would certainly crash the caller: a required field missing or null, a
   list that isn't a list, a list shorter than the schema's `minItems`, no tool call at
   all, arguments that aren't valid JSON (this last one used to be an unhandled crash on
   DeepSeek/Qwen/OpenAI).
3. **Retry** the same provider once (a model's answer is nondeterministic - it usually
   comes right on the second try), then **fail over** to the next provider. A provider
   that is *down* still fails over immediately; it is never retried.
4. Only when every provider has failed: a clean `503` whose message says the answers
   were malformed, per provider - never a 500.

The Manager also passes its own `validate` hook: a plan must be five objects, each with a
title and a description; a project needs a title and description.

**Deliberately not checked:** what is *inside* list items in general (only the Manager
opts in). Item shapes differ between providers, and a stricter generic check could reject
output that works today - a regression we can't test without keys.

`e2e_real_llm.py` now prints a "REPAIRED" and a "MALFORMED" section, so a real run tells
you how flaky each provider is on your schemas.

**Verified:** `smoke_test_llm_tool_output.py` (48 checks) - the repair/check functions,
every retry/failover path for Anthropic and OpenAI-compatible providers, and the real
failure through the real endpoint. It fails on the old code with the exact original
`TypeError`.

**Not covered:** the retry adds latency when a model is flaky (one extra call); and
`call_agentic` (chat replies) has no schema to repair, so it is unchanged.

