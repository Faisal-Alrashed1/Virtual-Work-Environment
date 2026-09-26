# Making sure all ten agents actually work

**The ask.** Not "are the agents wired up" (they are — see
`docs/TEN_AGENTS.md`) but "do they do real work": read real context, not
empty or placeholder data; write real, correct output; and have that
output verified by tests that check the actual content, not just that a
request returned 200.

## What this pass did

**1. A code audit.** Grepped every file in `app/agents/` and
`app/agents/graph/` for `TODO`, `FIXME`, `not implemented`,
`placeholder`, `hardcoded`, `stub` — the usual markers of unfinished
work. One hit, and it was benign (a comment explaining *why* something
is a database table instead of hardcoded logic). No stubs, no fake data
paths, no agent quietly returning canned output instead of a real model
call.

**2. A spot-check of the most complex agent.** Read `mentor.py`'s
`review_task` in full: it genuinely fetches the submitted GitHub repo's
real content (`github_client.fetch_repo_context`), reads the graduate's
own submission notes, reads prior review feedback on a resubmission
(so it doesn't invent new asks each round), and — for image
attachments — builds real `{"type": "image", "source": {...}}` content
blocks with the actual base64 image data, not just a text mention that
an image exists. This gave real confidence the rest of the roster,
built with the same care, would hold up too.

**3. `smoke_test_agent_read_write.py`** — a new test file held to a
specific, higher standard than "did this return 200": for each agent
that writes something, does the mocked LLM call *genuinely receive*
the real context it's supposed to (asserted on what was actually sent,
not just that a request succeeded), and does what it writes back
*genuinely round-trip* through a subsequent read.

## Three real gaps this closed

No earlier test had actually verified these — not because the
underlying code was wrong (it wasn't), but because nothing had checked
it this specifically:

1. **HR's attendance/lateness figures.** `hr.py`'s own docstring is
   explicit: "the LLM only writes the narrative and a rating on top of
   numbers it's handed, not the figures themselves." Those figures
   (`attended_days`, `absent_days`, `late_task_count`) are computed in
   plain Python from real `Task`/`TaskMessage` timestamps — but no test
   had ever checked them against a hand-computed expected answer, only
   that *some* numbers came back. This test constructs an exact, known
   week (a real Saudi Sunday-Thursday workweek, five deliberately
   timestamped tasks — one on-time, one late, two untouched beyond
   creation) and asserts the exact expected numbers: 4 attended, 1
   absent, 1 late, 5 total. All four matched on the first correctly-
   written attempt.
2. **The roundtable's "a conversation, not a stack of monologues"
   claim.** `roundtable.py`'s own docstring promises specialists "see
   the Mentor's review and everything said before it." No test had
   verified that literally — only that specialist messages appeared in
   the thread afterward, which would look identical whether or not
   they actually read each other. This test asserts the SECOND
   specialist's prompt genuinely contains the FIRST specialist's actual
   reply text (not a paraphrase, not a mention — the literal words),
   and that the Manager's synthesis afterward genuinely sees the whole
   discussion, not just the Mentor's original review.
3. **Mentor's vision path**, confirmed with an actual PNG: the test
   submits a real 1×1 image attachment and asserts the resulting
   `call_with_tool` invocation's `messages` payload contains exactly
   one real `image` content block — not a filename mentioned in the
   text prompt, an actual image the model can look at.

## A genuinely interesting finding along the way

Writing the roundtable check surfaced something about the code itself
worth knowing, not just about the test: the Manager's post-roundtable
synthesis does **not** call a separately-scoped `manager.call_agentic`
— it reuses the exact same `call_agentic` reference the specialists
just used, only borrowing `manager.SYSTEM_PROMPT` as plain system-
prompt *text*. A first version of this test patched
`roundtable.call_agentic` for specialists and a separate
`roundtable.manager.call_agentic` for the synthesis, assuming two
distinct call sites — that patch was silently a no-op for the
synthesis call, and the test caught its own mistake immediately (a
call count of 3 where 2 was expected) rather than passing on a false
premise. Fixed by reading `roundtable.py`'s actual synthesis code
directly instead of assuming symmetry with how the specialists are
called. This is arguably the most useful kind of bug a test like this
can surface: not "the code is wrong" but "my mental model of the code
was wrong," caught by the test actually failing honestly.

Every other fix this test needed along the way was similarly to its
**own** mock setup, never to production code: a wrong field name
(`cv_text` vs the real `cv_raw_text`), a wrong mock target
(`call_agentic` vs the real `call_with_tool` that `mentor.review_task`
and `hr.run_behavioral_review` actually use), and the real
`SUBMIT_REVIEW_TOOL` data shape (`categories` is an array of
`{key, label, score}` objects, not a flat dict; `verdict` is
`"approved"` / `"needs_changes"`, not an invented string). Each was
caught by the test failing honestly against the real implementation,
not by the implementation being wrong.

## What's covered, per agent

| Agent | What this test verifies |
|---|---|
| Manager | `plan_week`'s prompt genuinely contains the graduate's real CV text; the created Project and planned subtask round-trip through `GET /projects/me` and `GET /tasks` |
| Mentor | a real image attachment produces a real image content block sent to the model; the review round-trips through `GET /tasks/{id}/review` |
| HR | attendance/lateness figures are exactly correct against a hand-computed expected answer, not just "some numbers came back" |
| Security Reviewer / Data Reviewer (roundtable) | the second specialist's prompt genuinely contains the first's actual words; the Manager's synthesis genuinely sees the whole discussion; both specialists' messages persist in the real thread |
| QA Engineer (task chat) | a direct reply to a specific technical question persists and round-trips correctly tagged in the thread |
| Career Coach | its own persona is used, not a generic or wrong one; a second Meeting Room turn genuinely includes the first turn's real content (real conversation memory, not amnesia) |
| Technical Writer | its own persona is used; confirmed it does NOT bleed into Career Coach's prompt or vice versa |

Manager's `create_project`/`week_progress`, Mentor's rubric scoring,
HR's skills rollup, and Career Coach's full check-in lifecycle already
had deep dedicated coverage elsewhere (`smoke_test_task_bank.py`,
`smoke_test_mentor_rubric.py`, `smoke_test_agents.py`,
`smoke_test_ten_agents.py`) — this file adds the read/write-integrity
angle on top, not a duplicate of what already existed.

## A finding worth knowing about, not acted on this pass

While tracing what actually gets called in the agent roundtable, it's
worth noting `app/agents/co_reviewers.py` still exists in the codebase
— the original, simpler parallel-comment implementation the richer
conversational roundtable (`roundtable.py`) superseded. Nothing in the
production code path actually imports or calls it anymore (confirmed:
only comment mentions and its own dedicated test,
`smoke_test_stage2_co_reviews.py`, reference it) — despite
`orchestrator.py`'s docstring describing it as still living on "as the
simpler fallback," there's no code path that would actually fall back
to it. This isn't a broken agent — the real path (`roundtable.py`) is
solid, tested, and this pass leaned on it directly — but the
"fallback" framing in that docstring overstates what's actually wired.
Left as-is this round (out of scope for "make the agents work"; this is
housekeeping, not a functionality gap), flagged here so it doesn't get
mistaken for an active safety net it isn't.

## Testing

`smoke_test_agent_read_write.py` — 23 checks, all passing, as described
above. Full suite: **37 files, 955 checks, all passing.**
