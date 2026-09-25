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

## 3. The Manager sees the submission when replying in a task thread

**Owner of the code:** Manager (`app/agents/manager.py`,
`respond_in_thread`).

**What was wrong:** when the graduate posts in a task thread, the Manager's
prompt had the task title, status, CV context, and the thread — but nothing
about what was submitted, not even file names. "Is my app.py okay?" got a
guess.

**What changed:**
- New `_submission_context(task)` in `manager.py`: the GitHub link, the
  graduate's notes, and uploaded file content (via
  `submission_files.read_submitted_files`), plus the names of files that
  can't be read. Added to the system prompt of `respond_in_thread`.
- Files are cut to **1,500 chars each** (the Mentor gets 4,000): thread
  replies answer questions rather than review, and happen on every message,
  so this keeps the cost down.
- The GitHub link is passed as text, **not fetched**, so thread replies
  don't spend GitHub's 60-requests/hour limit.
- `create_project`, `plan_week`, `submit_week_progress`, and the
  roundtable synthesis are unchanged.

**Result in the live test:** asked "Is there anything risky in my app.py?",
the Manager quoted the vulnerable SQL line, gave the parameterized fix, and
mentioned the hardcoded secrets.

**Check it:** `python smoke_test_manager_sees_submission.py`.

---

## 4. Workspace: the agents thread no longer shows up empty

**Owner of the code:** Frontend (`frontend/src/app/workspace/page.tsx`).

**What was wrong:** `GET /tasks` (and the start/submit endpoints) return
tasks *without* their thread; only `GET /tasks/{id}` includes it. The page
replaced tasks with those thread-less versions, so the agents panel went
blank in three cases:
1. **On page load:** a task is auto-selected, but its thread was only
   loaded on click — the panel said "No discussion yet" even with 5 messages.
2. **Clicking "Start this task":** the response has no thread, and it
   replaced the task — the Manager's "New task" message disappeared.
3. **Switching language (AR/EN):** `t` from `useLocale` is recreated when
   the locale changes, which re-runs `refresh()`, which replaced every task
   with its thread-less version.

**What changed (`workspace/page.tsx` only):**
- New `keepThread(next, prev)`: when a task comes back without messages,
  keep the thread already loaded for it (a thread never shrinks). Used in
  `refresh()`, after "Start", and after submitting.
- New `loadThread(id)` + an effect on `selectedId`: the thread loads
  whenever a task becomes selected — on page load, after "Ask manager", or
  on click. Clicking the task that's already open reloads its thread.

**How it was checked** (in the browser; there's no frontend test setup yet):
the thread shows on load without clicking; it survives switching to Arabic
and back; a todo task's thread message is still there after "Start this
task". `npm run lint` and `npx tsc --noEmit` are clean.

---

## 5. Times no longer show 3 hours off

**Owner of the code:** Frontend (`frontend/src/lib/format.ts`).

**What was wrong:** the backend stores UTC times (`datetime.utcnow()`) and
the API sends them with no timezone suffix, e.g. `2026-09-24T17:05:20`.
JavaScript reads a date-time with no suffix as *local* time, so in Riyadh
(UTC+3) every time was 3 hours off: "3h ago" for something just created.

**What changed:** new `parseServerTime()` in `lib/format.ts` reads a
suffix-less date-time as UTC (strings that already have `Z` or an offset
are left alone). `timeAgo` and `timeUntil` use it — every relative time in
the app goes through those two, so this is the only file changed. The API
itself is unchanged.

**Heads-up — deadlines now show later than before, and that's the correct
time.** Deadlines are stored as 23:59:59 **UTC** (see "Known issues" below),
which is 02:59 in Riyadh, and that's when the backend actually marks a task
late. The UI used to show them 3 hours earlier than that.

**How it was checked** (browser): a message posted a moment ago shows "just
now" and one from 4 minutes earlier shows "4m ago" (both showed "3h ago"
before). `npm run lint` and `npx tsc --noEmit` are clean.

---

## 6. The Mentor can't approve work it couldn't see

**Owner of the code:** Mentor (`app/agents/mentor.py`) + frontend growth
view (`frontend/src/app/growth/page.tsx`).

**What was wrong:** found by Fahad testing by hand — he uploaded his CV (a
PDF) as the submission for "Set up project structure and virtual
environment". The Mentor can't open PDFs, so all it had was the file name,
and the model **invented a whole review**: it described `data/`, `src/`,
`tests/` folders, a virtual environment and a `requirements.txt` that
didn't exist, **approved the task, and scored it 5/5**. The Manager's
synthesis then congratulated him on it. That approval also counts toward
HR's evaluation of the graduate. (The Security/Data Reviewers handled it
correctly — they already had a guard for this, see #0.)

**What changed:**
- `mentor.py`: if a submission has no GitHub link, no notes, no readable
  file, and no image — only files that can't be opened — the review is
  decided **in code, with no LLM call**: `needs_changes`, no rubric scores,
  `"not_reviewable": true` in `metrics_json`, and a message naming the file
  and saying what to upload. The task goes back to `in_progress`.
- A line in `SYSTEM_PROMPT`: it can't approve work it hasn't seen, for the
  mixed cases (e.g. notes that describe the work plus an unreadable file).
- Notes-only and image-only submissions are **still reviewed** as before.
- `growth/page.tsx`: a review with no rubric scores shows "—" instead of
  "0.00/5" and is left out of the score chart (the backend dashboard
  average already skipped these).

**Result in the live test** (same situation: a PDF only): the Mentor says it
can't open the PDF and can't approve, the task is back in progress, no
scores are stored, and the only LLM call is the Manager's synthesis (which
now correctly asks for the actual files).

**Check it:** `python smoke_test_mentor_file_reading.py`.

---

## 7. Agents can read PDF, Word, and zipped projects

**Owner of the code:** shared `app/agents/submission_files.py` (used by the
Mentor, the Security/Data Reviewers, and the Manager's thread replies).

**What was wrong:** only plain-text files and notebooks could be read. A
PDF report, a Word document, or — very common — a whole project uploaded
as a `.zip` came through as "can't be opened", so the Python files inside a
zip were never seen.

**What changed:**
- PDF and `.docx` text is extracted with the same code the CV upload
  already uses (`graph/cv_parsing.extract_cv_text`: pypdf / python-docx).
- `.zip`: the readable files inside are read and named like
  `project.zip/src/app.py`, so the agents (and the static checks) treat
  each one like an uploaded file. Skips binaries, `.git/`,
  `__pycache__/`, `node_modules/`, `venv/`.
- Zip limits, so one archive can't flood the prompt or the server: at
  most 15 files, each at most 1 MB once decompressed (protects against zip
  bombs), and at most 3 files' worth of text in total.
- A corrupt PDF / zip is reported as unreadable, never a crash.

**Check it:** `python smoke_test_submission_files.py`.

---

## 8. Optional `GITHUB_TOKEN` for GitHub's request limit

**Owner of the code:** shared `app/agents/github_client.py` (Mentor and the
Security/Data Reviewers) + `app/config.py`.

**What was wrong:** GitHub allows 60 unauthenticated API requests per hour
per IP, and one review with a GitHub link spends several. During testing
it ran out twice ("API rate limit exceeded"), after which every agent saw
"GitHub didn't respond" for every link until the hour reset.

**What changed:**
- New optional setting `GITHUB_TOKEN` (`config.py`, documented in
  `.env.example`). When set, every GitHub request sends it as a Bearer
  token: 5,000 requests/hour, and private repos the token can read.
- The three places that opened their own `httpx.Client` now share one
  `_client()` helper. Behavior without a token is unchanged.

**To use it:** create a personal access token on GitHub (Settings →
Developer settings → Personal access tokens; read-only public access is
enough), then add `GITHUB_TOKEN=...` to your own `backend/.env` (never to
`.env.example`) and restart the backend.

**Check it:** `python smoke_test_stage2_specialist_reviewers.py` (#14).

---

## 9. A "needs changes" review no longer looks like no review at all

**Owner of the code:** Frontend (`components/workspace/task-workspace.tsx`,
`app/workspace/page.tsx`, `lib/i18n/en.ts` + `ar.ts`).

**What was wrong:** reported by Fahad — "I submitted but the review never
came." The review had come (server log: Mentor, both specialists and the
Manager answered within ~20 seconds), but:
1. On `needs_changes` the task goes back to `in_progress`, and the page just
   showed the empty submit form again. The "Reviewed by the mentor" notice
   and the review link only existed for approved tasks.
2. The agents discussion panel is `hidden` below the `xl` breakpoint
   (1280px), so on a laptop or a non-maximized window the agents' replies
   weren't visible anywhere.

**What changed:**
- On an `in_progress` task where the Mentor has already posted, a notice
  above the form: "The mentor asked for changes", the Mentor's message,
  a "See the full review" link, and "Update your work and submit it again
  below." (English + Arabic).
- Under `xl`, the same `AgentsMeeting` discussion (with the message box)
  renders under the task, via a new `discussion` prop on `TaskWorkspace`.
  At `xl` and wider it's hidden there and the side panel is used as before.

**How it was checked** (browser, on the account that reported it): at
1100px the notice shows with the Mentor's feedback and the full discussion
(Manager, Mentor, Data/Security Reviewers, Manager) is under the task; at
1440px it's in the side panel and not duplicated. Lint and tsc are clean.

---

## 10. The Meeting Room sees the graduate's latest submission

**Owner of the code:** Meeting Room (`app/agents/meeting.py`).

**What was wrong:** reported by Fahad — asking an agent in the meeting room
about "the solution I sent" got a guess. Meeting agents only had the CV,
the HR summary and the current project/week; nothing about submissions.

**What changed:** new `_latest_submission_context()`, added to every
meeting agent's context: the most recently submitted task (title, status,
description), its GitHub link and notes, the uploaded files' content (1,500
chars each, same as the Manager's thread replies — this runs on every
message), and the Mentor's latest review of it.

**Result in the live test:** asked "وش رأيك في آخر حل أرسلته لك؟", the Mentor
named the submitted file and the task it was for, and what was missing.

**Check it:** `python smoke_test_meeting_sees_submission.py`.

---

## 11. Agents answer in Saudi (Najdi) Arabic when the graduate writes in Arabic

**Owner of the code:** new `app/agents/language.py`, used by `meeting.py`,
`manager.py` (thread replies), `mentor.py`, `security_reviewer.py`,
`data_reviewer.py`, `roundtable.py`.

**What changed:** one shared `LANGUAGE_RULE` appended to the system prompt
of every agent that writes text a graduate reads: answer in the graduate's
language; if they write in Arabic (messages or submission notes), use Saudi
Najdi dialect rather than formal MSA; keep code, file names and technical
terms as-is. **English is unchanged** — no Arabic input, English output.

---

## 12. Arabic UI rewritten in Saudi (Najdi) dialect, and fully Arabic

**Owner of the code:** Frontend (`lib/i18n/ar.ts`, `en.ts`, `locale.tsx`,
`lib/format.ts`, and the components that show times or agent names).

**What was wrong:** the Arabic UI was formal MSA, and parts stayed English in
Arabic mode — every relative time ("3h ago", "due in 2d") and the optional
agents' names ("Data reviewer"), which come from the backend catalog.

**What changed:**
- `ar.ts` rewritten in Najdi dialect, as plain UTF-8 Arabic instead of
  `\u` escapes so it can be read and edited directly. Same keys — TypeScript
  still fails the build if it drifts from `en.ts`.
- Relative times are translated: new `time` keys in both dictionaries,
  `timeAgo`/`timeUntil` take the labels, and components get them through the
  new `useRelativeTime()` hook ("قبل 3 ساعة", "الموعد بعد 2 يوم").
- Optional agents' names are translated in conversations: new
  `extraAgentNames` keys + `useExtraAgentNames()`, passed to
  `resolveAgentDisplay`.

**How it was checked** (browser): in Arabic, the workspace shows Arabic times
and agent names with no English left; in English nothing changed.

---

## 13. Language and theme choices survive a page reload

**Owner of the code:** Frontend (`lib/i18n/locale.tsx`, `lib/theme.tsx`).

**What was wrong:** choosing Arabic (or light mode) was lost on every
reload, and the stored choice was overwritten with the default. The
providers saved the state to `localStorage` from an effect, which also ran
on the first mount with the default value ("en" / "dark"); under dev
`StrictMode` the adoption step then re-read `<html lang>` after that effect
had reset it.

**What changed:** the choice is saved only when the user toggles it, and on
load it's read from `localStorage` (same rule as the anti-flash script in
`app/layout.tsx`), not from the `<html>` attribute.

**How it was checked** (browser): switched to Arabic + light, reloaded:
still Arabic, right-to-left, light; no hydration warnings in the console.

---

## 14. Follow-up to #10/#11: agents actually use the submission, in Najdi

**What was wrong after #10/#11:** Fahad re-tested — meeting agents still
said "I can't access the solution you sent", with Egyptian-sounding words
('ما عنديش', 'مش'). Replaying his exact question on his real context showed
the submission *was* in the prompt; the model just fell back to a stock
"I can't see your files" answer (helped along by his earlier replies saying
the same), and the Mentor said it had seen only part of the file (1,500
chars).

**What changed:**
- `meeting.py`: the meeting framing now states that the agent has the
  graduate's latest submission below and must answer from it (and correct
  an earlier reply that said otherwise); with no submission, the context
  says so explicitly. Per-file slice raised to 4,000 chars (same as the
  Mentor's review).
- `language.py`: explicit Najdi word list (وش / أبي / مو / ما عندي /
  الحين ...) with the Egyptian/Levantine/Hijazi forms to avoid, no '-ش'
  negation, no formal connectors, an example of the tone, and "don't copy
  the dialect of earlier replies".

**Result** (his real context and history, 6 replays, nothing written to his
account): 6/6 named his file and discussed its content, 0/6 denied access,
no '-ش' negations. Still some MSA mixed in — the model's limit with Najdi.

---

## Config note (not a code change)

`qwen/qwen3.7-flash` via OpenRouter **does not reliably follow a forced tool
call**: it sometimes answers in plain text, sometimes returns broken JSON.
That breaks CV upload (onboarding) and every structured review. If you use
Qwen through OpenRouter, set `QWEN_SMALL_MODEL=qwen/qwen3-30b-a3b-instruct-2507`
in your `backend/.env` (about the same price, verified to work).

If `/growth` shows "Module not found: Can't resolve 'victory-vendor/d3-scale'",
your `node_modules/victory-vendor` install is incomplete (its `es/` and
`lib/` folders are missing). Fix it with
`rm -rf node_modules/victory-vendor && npm install` in `frontend/` — the
lockfile doesn't change.

## Known issues not fixed yet

- **Deadlines are end-of-day UTC, not end-of-day Saudi time.**
  `scheduling.n_workdays_from` works on UTC dates, so a subtask's deadline
  is 23:59:59 UTC = 02:59 the next morning in Riyadh, and the Fri/Sat
  weekend check runs on the UTC date (between 00:00 and 03:00 Riyadh time
  the UTC date is still the previous day). HR's attendance (`hr._active_days`)
  also counts UTC dates. Fixing it means computing these in `Asia/Riyadh`;
  it changes when work counts as late, so it needs a team decision first.
