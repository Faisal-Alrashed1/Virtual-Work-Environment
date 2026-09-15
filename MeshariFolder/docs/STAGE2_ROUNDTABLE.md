# Stage 2 — The Agent Roundtable (+ onboarding reset)

_Added Sep 2026. The capstone of Stage 2's "more collaborative, not just
assigning tasks" goal, plus a fix for graduates stuck on the onboarding
"already done" screen. Full regression: 300 backend checks across 14
suites, frontend eslint clean, full `next build` succeeds (13 routes)._

## 1. The roundtable — agents actually discussing with each other

Before this, the optional agents' task work (`STAGE2_AGENT_TASK_WORK.md`)
was *parallel*: each specialist looked at the submission alone and posted
an isolated comment, none of them aware of what the others said. That's
collaboration in name only — four monologues in one thread.

The roundtable (`app/agents/roundtable.py`) makes it a real conversation:

1. The Mentor writes its official review (unchanged — still the one
   structured `Review`, still the source of truth).
2. Each specialist on the graduate's team (Security Reviewer / Data
   Reviewer / DevOps) responds **in sequence, each seeing the Mentor's
   review and every prior specialist's turn** — so they build on, agree
   with, or push back on each other. A Data Reviewer can second a point
   the Security Reviewer raised; a DevOps agent can note something both
   missed.
3. The Manager reads the **whole discussion** and posts a short synthesis
   — the two or three things that actually matter most to act on next,
   reconciling any tension between what different agents emphasized. So
   the graduate gets one clear "here's what matters" instead of being
   left to reconcile four voices.

Verified directly (`smoke_test_stage2_roundtable.py`, 20 checks): a later
specialist's prompt provably contains an earlier specialist's exact
words, and the Manager's synthesis prompt contains the full transcript —
not just that messages get written, but that each agent genuinely *sees*
what came before.

### Bounded on purpose

- **One pass around the table**, not a free-running loop — deterministic,
  predictable cost, no runaway back-and-forth.
- **Deterministic speaker order** (sorted by agent type) so the thread
  reads consistently run to run.
- **Model routing**: specialists on the small model (quick, cheap takes);
  the Manager's synthesis on the main model (it's the judgment call that
  ties it together). Same split as the rest of Stage 2.
- **Best-effort per turn**: one agent erroring is skipped, the rest of
  the table carries on, and the Mentor's review that already succeeded is
  never affected. Verified with a forced mid-table failure.
- **Career Coach stays out**, same as co-reviews — coaching isn't a
  per-task code review.

### Relationship to co_reviewers.py

`co_reviewers.py` (the earlier parallel version) is still in the tree as
the simpler fallback, with its own unit test
(`smoke_test_stage2_co_reviews.py`, now testing `run_co_reviews`
directly rather than through the router). The router
(`POST /agents/mentor/review/{task_id}`) now routes to the roundtable via
`orchestrator.run_co_reviews` — kept that function name for continuity;
it's the same seam, richer implementation behind it.

## 2. Onboarding reset — no more dead-end "already done" screen

**The bug:** every graduate hitting `/onboarding/cv` saw "You've already
been through onboarding" with no way forward — a dead end. Root cause:
pre-Stage-2 user rows never had `onboarding_stage` properly initialized
(the column was added via `create_all` without a migration), so they read
as anything-but-`cv` and the wizard treated them as complete, with no
escape hatch even for someone who wanted to redo it.

**The fix:** `POST /onboarding/reset` sends a graduate back to the start
— clears the wizard's own state (stage → `cv`, the pending track
suggestion, the Q&A log, the confirmation flag) but deliberately leaves
their CV, selected agents, and any project/tasks intact. Redoing intake
shouldn't wipe the account. The "already done" screen now offers "Go
through it again" wired to this, so it's a real choice, not a wall — and
it's the clean fix for the stuck pre-Stage-2 users too.

## What this means for the code — built

- `backend/app/agents/roundtable.py` (new) — `ROUNDTABLE_AGENTS`,
  `run_roundtable(db, user, task)`.
- `backend/app/agents/orchestrator.py` — `run_co_reviews` now delegates
  to the roundtable (co_reviewers import dropped; module stands alone).
- `backend/app/routers/onboarding.py` — `POST /onboarding/reset`.
- `backend/smoke_test_stage2_roundtable.py` (new, 20 checks).
- `backend/smoke_test_stage2_co_reviews.py` — rewritten to unit-test
  `co_reviewers.run_co_reviews` directly (it's no longer on the router's
  path).
- `backend/smoke_test_stage2_onboarding_router.py` — reset-endpoint
  checks added.
- `frontend/src/lib/api.ts` — `onboarding.reset`.
- `frontend/src/app/onboarding/cv/page.tsx` — `handleRestart`, "Go
  through it again" on the already-done panel.
- `frontend/src/components/workspace/agents-meeting.tsx` — empty-state
  copy updated for the team-review flow (the roundtable already renders
  correctly here via `agentDisplay`, colored per speaker).

## Not built yet

- **Roundtable doesn't re-run selectively** on a `needs_changes`
  resubmission — the whole table fires again on the next review call
  (fine, just not a lighter "recheck only X" option).
- **Specialists still get filenames, not image contents** for image
  attachments (the Mentor gets real vision blocks; the roundtable
  specialists don't yet — `STAGE2_MEETING_AND_SUBMISSIONS.md` has the
  same note).
- **Onboarding mid-flow resume** (closing the tab mid-wizard) is still
  not supported — reset is all-or-nothing back to the CV step. Documented
  in `STAGE2_ONBOARDING_FRONTEND.md`.
