# Team changes log

Changes made to shared code or to code another teammate owns, so nobody is
surprised by them. Each entry: what was wrong, how it was found, what
changed, which files, and how to check it. Newest at the bottom.

All of these came out of a **live test** with a real LLM key (Qwen via
OpenRouter): a submission with an `app.py` containing two hardcoded secrets
and an SQL injection, plus a notebook that scales data before the
train/test split and scores only on training data.

---

## 0. Security Reviewer / Data Reviewer upgraded (commit `77cd784`)

**Owner:** Fahad. Listed here because it touched shared files.

**What was wrong:** both were free-text personas that only saw uploaded
files' *names*. In the live test the Security Reviewer said "no hardcoded
secrets, no injection risks" about a file with both, and the result was
stored as `clear` / `low`.

**What changed:**
- New `app/agents/security_reviewer.py`, `data_reviewer.py`: read the actual
  uploaded files and GitHub repo files, return structured findings stored as
  a `Review` with `kind=specialist_review`.
- New shared `app/agents/submission_files.py`: reads uploaded attachments'
  content (text, code, notebook code cells). **Anyone can use it.**
- New `app/agents/static_checks.py`: rule-based checks run before the LLM
  (hardcoded secrets, data leakage). A match is always kept in the findings,
  even if the model misses it. Adding a rule is a few lines.
- If nothing readable was submitted, no LLM call is made and the verdict is
  `not_reviewed` (instead of a guessed "clear").

**Shared files touched (additive, nothing removed):**
- `models.py`: new `ReviewKind.SPECIALIST_REVIEW`.
- `tools.py`: new `SUBMIT_SECURITY_REVIEW_TOOL`, `SUBMIT_DATA_REVIEW_TOOL`.
- `github_client.py`: new `list_repo_paths()` and `fetch_file_content()`.
  `fetch_repo_context()` (used by the Mentor) is unchanged.
- `roundtable.py`: Security/Data Reviewer go through their new modules;
  **DevOps and the Manager's synthesis are unchanged.**

**Check it:** `python smoke_test_stage2_specialist_reviewers.py`,
`python smoke_test_static_checks.py`, `python smoke_test_stage2_roundtable.py`.

---

## 1. The Mentor now reads uploaded files

**Owner of the code:** Mentor (`app/agents/mentor.py`).

**What was wrong:** for any uploaded file that isn't an image, the Mentor's
prompt contained only the file's name, with the instruction
`"not previewable here, judge by name/context"`. So it reviewed code it never
saw. In the live test its whole review was about missing folders; it didn't
notice the hardcoded password or the SQL injection. This also affects HR,
which builds the graduate's Employee File from the Mentor's reviews.

**How it was confirmed:** captured the exact prompt the Mentor sends to the
model for that submission. Word for word, the only mention of the two files
was: `Other files submitted (not previewable here, judge by name/context):
app.py, analysis.ipynb`.

**What changed (`mentor.py`):**
- Uploaded text/code/notebook files go into the prompt as their content,
  through the shared `submission_files.read_submitted_files()`.
- Files that can't be read (zip, pdf, binaries) are listed as "can't be
  opened here (don't guess at their contents)".
- **Images are unchanged** — still sent as vision content blocks.
- One line added to `SYSTEM_PROMPT`: only judge files whose content it was
  shown.

**Result in the live test:** the Mentor now names the SQL injection (quoting
the line), both hardcoded secrets, and the training-set-only evaluation.

**Check it:** `python smoke_test_mentor_file_reading.py` (captures the exact
prompt; no API key needed).

---

## 2. A model that skips its tool call no longer crashes the request

**Owner of the code:** LLM client (`app/agents/llm_client.py`) and onboarding
(`app/agents/graph/onboarding_graph.py`).

**What was wrong:** every agent asks the model to answer through a specific
tool (a "forced tool call"). When a model answered in plain text instead, or
returned broken JSON arguments, the code raised an unhandled error:
- The request returned a **raw 500**.
- There was **no retry and no failover** to the next provider, even though
  the failover chain exists for exactly this kind of thing.
- That 500 had **no CORS headers**, so the browser blocked it and the
  frontend showed **"Can't reach the server — is the backend running?"**
  while the backend was actually running fine. This is what happened on the
  very first CV upload with `qwen3.7-flash`.

**How it was confirmed:** sent a request with a browser `Origin` header
while the model skipped its tool call: status 500, no
`access-control-allow-origin` header. The existing 503 path does have it.

**What changed:**
- New `ToolCallError` in `llm_client.py` for "the model answered, but not
  with a valid tool call" (no call, or arguments that aren't a JSON object).
- `call_with_tool` / `call_agentic` now share one loop (`_run_chain`): a
  `ToolCallError` is retried once on the same provider (`TOOL_CALL_ATTEMPTS
  = 2`), then fails over like an outage. When every provider fails, it
  raises the existing `ALL_PROVIDERS_FAILED` error, which `main.py` already
  turns into a **503 with a readable message** (and CORS headers).
- `onboarding_graph._forced_tool_call` follows the same policy.
- **Unchanged on purpose:** a genuine bug (any other exception) still comes
  back as a 500 — `smoke_test_llm_errors.py` checks this.

**Result in the live test** (CV upload on `qwen3.7-flash`, 3 tries): two
succeeded; the third failed twice in a row and came back as a 503 saying
"model answered without calling 'generate_questions'", readable in the
browser — before, that was the "Can't reach the server" error.

**Check it:** `python smoke_test_llm_tool_call_failover.py`.

---

## Config note (not a code change)

`qwen/qwen3.7-flash` via OpenRouter **does not reliably follow a forced tool
call**: it sometimes answers in plain text, sometimes returns broken JSON.
That breaks CV upload (onboarding) and every structured review. If you use
Qwen through OpenRouter, set `QWEN_SMALL_MODEL=qwen/qwen3-30b-a3b-instruct-2507`
in your `backend/.env` (about the same price, verified to work).

## Known issues not fixed yet

- The Manager's thread replies (`manager.respond_in_thread`) don't see
  uploaded files at all, not even their names.
- `/workspace`: the agents thread shows as empty on first load until the task
  is clicked.
- Timestamps display 3 hours off ("3h ago" for something just created) —
  likely naive UTC shown as local time.
- GitHub's unauthenticated limit is 60 requests/hour; a few submissions with
  GitHub links use it up. Planned fix: an optional `GITHUB_TOKEN`.
