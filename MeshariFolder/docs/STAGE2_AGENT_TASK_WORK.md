# Stage 2 — Optional Agents Doing Real Task Work

_Added Sep 2026. Seventh slice of Stage 2, and the deeper version of
"more collaborative, not just assigning tasks" for the four optional
agents specifically — until now they were roster entries and meeting-
room chat only (`STAGE2_TEAM_AND_ORIENTATION.md`,
`STAGE2_MEETING_AND_SUBMISSIONS.md`), nothing tied to actual submitted
work. Full regression: 278 backend checks across 13 suites, frontend
eslint clean, full `next build` succeeds (13 routes). See
`docs/PROJECT_STATUS.md` for the overall state._

## The design decision, up front

Three of the four optional agents — Security Reviewer, Data Reviewer,
DevOps — got wired into the submission review flow. **Career Coach
deliberately did not.** Resume and interview coaching isn't a code
review; forcing it into the per-task flow would mean either a career
comment on every single submission (noise) or some ad hoc rule for when
it applies (arbitrary). It stays exactly where it already worked well:
meeting-room conversation, on demand. This is a scope boundary, not an
oversight — worth remembering if a future session is tempted to "finish
the set" by bolting Career Coach onto the review flow too.

## The flow

Right after the Mentor writes its official review (`POST
/agents/mentor/review/{task_id}`, unchanged in shape and behavior —
still the one structured `Review`, still the source of truth for
approved/needs_changes), each of the three above **that's on the
graduate's roster** posts one follow-up comment in the task thread —
their specialty lens on the same submission, not a second competing
review. A graduate with none of the three added sees exactly what they
saw before this slice: just the Mentor's message.

Each agent's call is independent and best-effort — `co_reviewers.py`
catches per-agent exceptions, so one flaky call (a rate limit, whatever)
never blocks the others or the Mentor's review that already succeeded.
Verified directly: a smoke test forces one agent to raise and confirms
the other still posts and the endpoint still returns 201.

**Model routing:** these run on the small model
(`settings.small_llm_model`), not the default tier — a quick specialty
comment, not the primary judgment call the Mentor already made, same
reasoning as the onboarding graph's routing decision
(`STAGE2_ONBOARDING_FLOW.md`). Required a small addition to
`llm_client.call_agentic`, which had no way to override the model
before this — added an optional `model` param, defaulting to
`settings.llm_model` so every existing caller is unaffected.

## What this means for the code — built

- `backend/app/agents/llm_client.py` — `call_agentic` gained an optional
  `model` param.
- `backend/app/agents/meeting.py` — `_PERSONA` → `PERSONA` (made public;
  now shared with `co_reviewers.py` rather than duplicated).
- `backend/app/agents/co_reviewers.py` (new) — `CO_REVIEW_AGENTS`,
  `run_co_reviews(db, user, task)`.
- `backend/app/agents/orchestrator.py` — `run_co_reviews` wrapper,
  following the file's existing routing-layer pattern.
- `backend/app/routers/agents.py` — calls it right after
  `orchestrator.mentor_review` succeeds.
- `backend/smoke_test_stage2_co_reviews.py` (new, 15 checks): no extras
  on roster → no co-review messages; two extras added, one not → exactly
  those two post, not the third; Career Coach on roster → never called,
  confirming the deliberate exclusion; one agent erroring → the other
  still posts and the endpoint still succeeds; model routing verified
  directly (the actual `model` kwarg sent).
- **Frontend — fixing a real bug this surfaced.** `TaskMessage.agentType`
  had been narrowed to the fixed three-agent type on the assumption only
  the Manager ever posts thread messages — now false, so it's widened
  back to a plain agent id string. `agents-meeting.tsx` was doing
  `AGENTS[m.agentType]` directly, which would've returned `undefined`
  for a co-reviewer's message and — worse — silently misattributed it to
  "You" (the code's fallback for "no agent metadata found"). Fixed with
  a new shared `lib/agent-display.ts` (extracted from a near-identical
  helper that had been living locally in `meeting/page.tsx` — now both
  screens share one implementation instead of two copies drifting
  apart). `workspace/page.tsx` now fetches the graduate's extra agents
  alongside tasks and passes them to `AgentsMeeting`, same pattern
  already used on `/board` and `/meeting`.
- Verified: eslint clean, full `next build` succeeds.

## Not built yet

- **Vision for co-reviewers.** The Mentor's review already sends image
  attachments as real vision content blocks
  (`STAGE2_MEETING_AND_SUBMISSIONS.md`); co-reviewers only get filenames
  listed in text, not the images themselves. Reasonable for a first cut
  — kept the per-agent prompt small and cheap — but worth revisiting if
  a Security Reviewer ever needs to look at a screenshot.
- **No way to ask a co-reviewer to look again** after a `needs_changes`
  resubmission — they only ever fire once, right after the Mentor's
  first pass on a given review call. If a graduate resubmits and the
  Mentor reviews again, the co-reviewers fire again too (nothing special
  needed there — same call path), but there's no lighter "just recheck
  the security angle" option.
- Career Coach remains meeting-room-only, as designed above.
