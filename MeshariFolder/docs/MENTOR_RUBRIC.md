# The Mentor's rubric, v2

You asked for a rubric and said "you decide the best". These are **proposed
defaults, ready for the team to confirm** - every number and anchor lives in one
file, `backend/app/agents/rubric.py`, and is meant to be edited.

## What was wrong with the first pass

The prompt was five sentences: four category names, "score 1-5", "be specific".

- A **"3" meant whatever the model felt that day**, so scores weren't comparable
  between tasks, weeks or graduates - and the average score on the dashboard and
  in HR's rollup was built on them.
- **Nothing tied the verdict to the scores.** A model could write "approved" next
  to a correctness score of 1.
- **On a resubmission the Mentor couldn't see its own earlier feedback.** It could
  not check its requests were met, and tended to invent new ones - an endless
  needs-changes loop, which is exactly the part of the product you will demo.
- It knew nothing about the graduate (track, week) and had no rule against
  claiming to have run code it can only read.

## The rubric

Scores are 1-5; 2 and 4 sit between the anchors.

| Category | 1 | 3 | 5 |
|---|---|---|---|
| **Meets requirements** (`correctness`) - *blocking* | Doesn't attempt it, or it can't work at all | Goal substantially met; some edge cases/secondary parts missing | Meets the goal fully and thoughtfully, beyond the brief where sensible |
| **Code quality** | Hard to follow: no structure, unclear names, copy-paste | Readable, sensible structure, some duplication | Clear, well-structured, idiomatic, easy to change |
| **Testing** | No verification where the task plainly needed some | Some tests, or a clear note on how it was checked by hand | Meaningful tests for key behaviour and an edge case or two |
| **Documentation** | No explanation of what it is or how to run it | Short README/notes: what it does, how to run it | Clear, usable docs incl. decisions and known limits |

Testing is judged against the task's size: a small exercise that didn't ask for
tests doesn't get a 1 for lacking them. (Anchors for 2 and 4 are left to the
model on purpose: fewer anchors, less prompt, and 1/3/5 are the ones that matter.)

## The verdict rule (and what the code enforces)

> **`needs_changes` only when "Meets requirements" scores below 3.** Otherwise
> `approved`. Weak code quality, tests or docs never block on their own - approve
> and say what to improve next time.

This is the same philosophy as before ("only when something genuinely blocks the
goal"), now precise. The **code enforces one contradiction**: if the model says
*approved* but scores correctness below 3, the verdict is changed to
`needs_changes`, the summary explains why ("Verdict adjusted..., 2/5 is below the
approval bar of 3/5"), and the stored review carries `verdict_adjusted: true` and
`rubric_version: "2"`. The adjusted verdict is what moves the task, so the board and
the review can't disagree.

Deliberately **not** enforced: the reverse (needs_changes with decent scores). The
model may be flagging a real blocker its numbers don't capture, and bouncing is the
cautious direction.

## Context and memory the Mentor now gets

- The graduate's **track** and **program week** (calibration: good *junior* work,
  a little more expected each week).
- **On a resubmission, its own previous feedback** - the summary and every comment -
  plus the revision number, and the instruction to judge mainly whether those points
  were addressed and to approve if the blockers are fixed, rather than raise new
  non-blocking issues.
- A rule about **honesty**: it can read what it's given, it cannot run code or tests,
  and must never claim otherwise or mention files it wasn't shown. It is also told what
  it *does* see of a GitHub repo - the first 25 file names and the first 2,000 characters
  of the README, not the code - so it asks for evidence to be added rather than assuming
  something is missing from code it never read (see `docs/TASK_BANK.md`).

## Style of the feedback

At most **3 comments** when bouncing (most important first: what's wrong, why it
matters, the concrete fix) and **2** when approving (what to improve next time).
Every comment must point at something concrete in the submission, or say plainly
that it couldn't verify. The tool schema caps comments (4) and requires exactly four
categories; the code trims anything longer.

## Decisions for the team to confirm

These are my defaults; change them in `rubric.py`.

1. **Approval bar = 3** (`APPROVAL_BAR`). Lower it to 2 to be more forgiving; raise it
   to 4 for a stricter mentor (expect more bounces in the demo).
2. **Only "Meets requirements" can block.** If you want a hard rule like "no tests =
   no approval" for some tracks, that would be a per-track override (not built).
3. **Comment caps 3 / 2** (`MAX_COMMENTS`, `REVIEW_STYLE`).
4. **Anchors' wording** - especially "3 = acceptable for a junior".

## Why this helps when the judges ask "why and how"

Every review can now be explained: the rubric is a short readable file, the verdict
follows one stated rule, the numbers and the verdict can't contradict, the stored
review says which rubric version produced it and whether it was adjusted, and the
Mentor demonstrably reads its own earlier feedback.

## What was verified

`smoke_test_mentor_rubric.py` (49 checks): the rubric and the tool schema can't drift
apart; every category has anchors in the prompt; the enforcement table (flips at
1 and 2, not at 3, not for weak tests/docs, reverse left alone); malformed shapes
real models return (dict-shaped categories, junk, boolean scores, plain-string
comments) never crash a review; the Arabic adjustment note; and, through the real
endpoint, exactly what the Mentor is sent - track, week, first-submission vs
revision N, and its previous feedback. Mutation-checked: removing the enforcement or
the previous-feedback hook makes it fail. All 19 earlier suites still pass unchanged.

## Not covered

- **Not tested with real models.** The wiring is verified; how a real model scores
  against these anchors, and how often it contradicts itself, is not. Run
  `python e2e_real_llm.py` (it now reports when the rule adjusts a verdict) and watch
  a few reviews before the demo.
- **The task bank is still open.** The Manager's task content is still improvised;
  a per-track bank of example projects is the natural next step.
- **Scores from before v2** in existing data used the old, unanchored scale; the
  dashboard average mixes them. Fine for a demo database.
