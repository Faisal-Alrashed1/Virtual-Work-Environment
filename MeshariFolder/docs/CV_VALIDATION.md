# CV content validation

**The bug, reported directly**: uploading any readable file as a "CV" —
an invoice, an essay, a random PDF someone had lying around — was
silently accepted. Nothing anywhere checked that the extracted text
actually *read like* a CV, only that some text could be extracted from
the file at all.

This mattered more than it might sound like at first: `cv_raw_text` is
read by the Manager (calibrating the graduate's first task), folded
into HR's employee-file rollups, and read directly by the Career
Coach's check-in. A wrong upload didn't just fail loudly and get
caught — it silently poisoned every one of those downstream judgments
with content that had nothing to do with the graduate at all.

## Where the gap actually was

`app/agents/graph/cv_parsing.py`'s `read_cv_upload` (the one function
every CV-intake endpoint already routed through) checked exactly two
things: is the file under the size cap, and did *some* text come out of
it. Neither check has anything to do with whether that text is a CV.

## Why the fix isn't inside `read_cv_upload` itself

`read_cv_upload` is genuinely shared, not CV-specific despite its name
— `app/materials.py` (a graduate's own-project materials) and
`app/routers/company.py` (a company's RAG knowledge-base uploads) both
reuse it for extracting text from *any* uploaded document, and neither
of those should ever be judged as "is this a CV." Baking a CV check
into the shared extractor would have wrongly started rejecting
perfectly legitimate project write-ups and company documents. The fix
is a separate function, `validate_is_cv`, called only at the three
places that are genuinely CV intake.

## What's built

**`validate_is_cv(text)`** in `cv_parsing.py` — judged by a real model
via a forced tool call (`CV_CLASSIFICATION_TOOL`), the same pattern
every other quality judgment in this codebase already uses (Mentor's
review, HR's rollup), not a keyword or length heuristic. A heuristic
would be trivial to fool by accident: a wrong upload can easily be long
and text-rich (an essay, a manual, an invoice with a long itemized
list) without being remotely CV-shaped, and a genuinely short or
unusually-formatted real CV shouldn't be punished for it. The model is
asked to judge content only, explicitly told not to evaluate quality,
length, or formatting.

A fast, model-free path handles the trivial case first: genuinely
blank or whitespace-only text is rejected immediately, no LLM call
spent on nothing.

**Wired into all three real CV-intake points**, each already using
`CVReadError` → `HTTPException` for other reasons (a corrupt file, an
oversized file), so this slots into an existing error path rather than
adding a new one:
- `POST /onboarding/cv` — a file upload, starts onboarding.
- `POST /users/me/cv` — pasted text, no file at all. The same bug
  class applies here too: someone can paste anything, not just upload
  a wrong file.
- `POST /users/me/cv/file` — replacing an existing CV later. Checked
  specifically that a rejected replacement never overwrites the
  original, valid CV that was already on file.

**The rejection message is genuinely useful, not generic**: it
includes the model's actual stated reason ("That doesn't look like a
CV — it reads like a restaurant invoice, not a résumé. Please upload
your actual CV or résumé."), and — confirmed by reading `app/
language.py` rather than assuming — needed zero extra code to also
work in Arabic: every `call_with_tool` system prompt is already wrapped
with the language instruction for the whole app, so a new caller gets
correct-language output for free.

**Frontend needs no changes.** Every CV-upload page already displays
`ApiError.message` generically for any upload failure (a corrupt file,
an oversized file); this rejection surfaces through that exact same
existing path.

## Fixing what it broke — a real, expected consequence

Adding a second LLM call to what used to be a single-call CV-upload
flow broke seven pre-existing tests that had exactly one call mocked.
Fixing each one required first understanding *how* that specific file
tracks calls, not just adding a mock and hoping:

- Some test files (`smoke_test_agent_language.py`) intercept every
  `call_with_tool` invocation generically to check language wrapping —
  these needed both the new mock *and* an updated expected call count
  (2 → 3).
- Others (`smoke_test_onboarding_graph_hardening.py`) only track the
  LangChain graph model specifically, completely separate from
  `call_with_tool` — these needed only the new mock, with their
  existing call-count assertions correctly left untouched. Verified
  this by reading each file's own tracking code rather than assuming
  symmetry between them, which would have produced a confusing,
  hard-to-diagnose false failure in the language-instruction count.

## Testing

`smoke_test_cv_validation.py` — 16 checks, the actual point of this
change: an invoice, a grocery list, and a novel excerpt each genuinely
refused at all three intake points with the model's real stated
reason; a genuine CV genuinely accepted at each; a rejected replacement
confirmed to never overwrite an existing valid CV; a blank paste
refused via the fast, LLM-free path (asserted directly: zero calls to
the mocked `call_with_tool`); and confirmed the non-CV upload path
(own-project materials) is completely unaffected — no CV-classification
mock active for that check at all, so an accidental call would have
hit the real API and failed the test.

Full suite: **38 files, 970 checks, all passing.**
