# Agents that answer in Arabic

The interface has been fully Arabic-capable (RTL, dictionaries) since the Arabic
i18n work, but every agent still answered in English: the Manager's task titles
and descriptions, the Mentor's reviews, HR's summaries, meeting-room replies,
the roundtable, the onboarding questions. The frontend notes even listed this as
"out of scope, a backend change". With an Arabic-speaking audience, an Arabic UI
wrapped around English agent text looks unfinished. This is that backend change.

## How it works

1. The frontend sends `X-Venv-Language: ar|en` with **every** API call
   (`lib/api.ts`), read from `<html lang>` - what the UI is showing right now.
2. `LanguageMiddleware` (`app/language.py`) stores it in a `ContextVar` for the
   life of that request.
3. `llm_client.call_with_tool` and `call_agentic` - the two functions every agent
   call goes through - append one short instruction to the system prompt
   (`with_language`). The two onboarding-graph prompts that produce free text do
   the same.

The instruction tells the model to write everything a *person* reads (titles,
descriptions, questions, review text, comments, reasoning, chat) in clear Modern
Standard Arabic, and to leave everything a *program* reads alone: JSON keys, tool
names, enum values (`approved`, `needs_changes`, track and agent ids), code, file
names, URLs, and common technical terms (API, JWT, Docker, Git...).

**English is the default and adds nothing** - an English request's prompts are
byte-for-byte what they were before.

## Why a header, not a saved setting

- It is what the UI shows *now*: no sync problem after a toggle, across devices, or
  on a fresh login.
- No database column, no migration, nothing to backfill.
- Every agent call is already triggered by an HTTP request, so there is always a
  request to read it from.
- A new agent gets it for free if it goes through `llm_client`. (If one ever calls a
  LangChain model directly, wrap its `SystemMessage` text in `with_language(...)`,
  as `onboarding_graph.py` does.)

The trade-off: a client that doesn't send the header (curl, another tool) gets
English. That's the safe default.

## What was verified

`smoke_test_agent_language.py` (34 checks) runs the **real endpoints and agents**
with only the model SDK faked, recording the system prompt each call actually
sends: Manager, Mentor, meeting room, HR, the roundtable's specialists and
synthesis, and the onboarding graph, plus the OpenAI-compatible providers
(DeepSeek/Qwen/OpenAI). It proves: every Arabic call carries the instruction,
exactly once; English calls carry none; one request's language never leaks into
the next; `ar-SA`/`AR` work and unsupported values fall back to English. I also
mutation-checked it: removing the middleware, either `llm_client` hook, or an
onboarding hook each makes it fail.

`python e2e_real_llm.py --language ar` is the check for **real** models: it sends
the header and *fails* if the onboarding questions, the task, the Mentor's review or
a chat reply come back without Arabic text.

**Browsers and CORS.** Every request now carries a non-standard header, so a browser first
sends a preflight (`OPTIONS`) asking whether it may. The test client never does that, so the
suite sends one explicitly and checks that `x-venv-language` is allowed, and that a real
cross-origin request carrying it is answered with CORS headers. If CORS is ever tightened to
a fixed header list, this fails loudly instead of every browser request being silently blocked.

## Not covered / worth knowing

- **Quality is the provider's.** The instruction is verified; how good the Arabic is
  isn't - run the check above with each provider you'll demo with (Qwen and Claude
  are usually strong; judge DeepSeek/OpenAI yourself).
- **Content stays in the language it was written in.** A week planned while the UI
  was English stays English if the graduate switches later; only new content follows.
- **Rubric category labels** ("Code quality"...) are written by the model, so they
  follow the language; the *keys* stay English.
- **The optional-agent catalog** (names/descriptions of Security Reviewer, Data
  Reviewer, ...) comes from the backend database, not the dictionaries, and is still
  English - a small follow-up if you want it.
- **Company reports (Stage 3)** should use the same mechanism: the report is written
  in the language of the person viewing/requesting it.
