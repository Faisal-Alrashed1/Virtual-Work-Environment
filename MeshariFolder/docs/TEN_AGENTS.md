# Ten agents

**Why.** The roster had sat at 7 agents (Manager/Mentor/HR plus four
optional specialists) for a while, and Career Coach — despite being on
the roster since Stage 2 — had never had anything of its own to *do*
beyond chat. This pass does two things: grows the roster to a genuine
10 agents, and makes sure growing the number wasn't the only thing that
happened — every agent added or touched here is reachable somewhere
real, not just a name in a catalog.

## The roster, all ten

| Agent | Default? | Meeting/Team Room | Task chat | Roundtable | Dedicated action |
|---|---|---|---|---|---|
| Manager | yes | yes | yes (scoped to big-picture) | synthesis | plan_week, assign, week review |
| Mentor | yes | yes | yes (default) | writes the review | review_task |
| HR | yes | yes | no | no | skills rollup, behavioral review |
| Security Reviewer | no | yes | yes | yes | — |
| Data Reviewer | no | yes | yes | yes | — |
| DevOps | no | yes | yes | yes | — |
| **QA Engineer** *(new)* | no | yes | yes | yes | — |
| **UX Reviewer** *(new)* | no | yes | yes | yes | — |
| Career Coach | no | yes | no | no | **career check-in** *(new)* |
| **Technical Writer** *(new)* | no | yes | no | no | — |

Three new agents, and one existing one (Career Coach) finally getting a
real dedicated action instead of staying chat-only forever.

## What's built

### QA Engineer and UX Reviewer — full technical specialists

Added to every place the existing three technical specialists
(Security Reviewer, Data Reviewer, DevOps) already lived:

- `app/agents/meeting.py`'s `PERSONA` — a real persona each, not a
  placeholder.
- `app/agents/task_chat.py`'s `TASK_CHAT_AGENTS` — addressable directly
  in a task thread while the graduate is still working (e.g. "is this
  test coverage enough?" straight to QA Engineer).
- `app/agents/roundtable.py`'s `ROUNDTABLE_AGENTS` — eligible to join
  the post-submission specialist discussion once a graduate has added
  them, exactly like Security/Data/DevOps already were.
- `app/agents/graph/catalog.py` — seeded so they're actually offered
  during onboarding, with `suggested_for_tracks_json` pointing at the
  tracks where they're most relevant (Software Engineering, Data
  Science & AI, Information Systems).

No new architecture was needed for either — the whole point of
`AgentCatalog` being a table instead of hardcoded logic (a Stage 2
decision) is that this really is additive: three new rows, three new
`PERSONA` entries, two small set additions.

### Technical Writer — chat-only, on purpose

Reachable in the Meeting Room and Team Room, seeded in the catalog
(suggested for every track, like Career Coach — documentation feedback
is universally relevant), but **deliberately not** in `TASK_CHAT_AGENTS`
or `ROUNDTABLE_AGENTS`. The reasoning mirrors why Career Coach and HR
were already excluded from those: documentation quality is a
review-time concern, not a "help me while I'm mid-task" or "review this
specific submission" one. Adding it to task chat or the roundtable
would have been easy technically and wrong for the same reason Career
Coach was never eligible for the roundtable — this doc exists partly so
that reasoning doesn't get "fixed" back to symmetry later without
someone re-deciding it on purpose.

### Career Coach's career check-in (`app/agents/career_coach.py`)

The actual gap this pass closes: every other agent that isn't
chat-only writes something durable — Mentor's `review_task`, HR's
`run_rollup`/`run_behavioral_review`, Manager's `plan_week`/week
review. Career Coach had none of that; "resume feedback and interview
prep" only ever happened in a chat window that scrolls away.

`run_checkin(db, user)` reads the graduate's actual Employee File (and
CV, if on file) and produces, via a forced tool call
(`CAREER_CHECKIN_TOOL` in `app/agents/tools.py`): a short honest
assessment, 2-4 real resume-bullet-shaped highlights, and one concrete
thing to focus on next. Saved as a `Review`
(`ReviewKind.CAREER_CHECKIN`, new) — the same pattern every other
agent's durable output already follows, not a special case.

- `POST /agents/career-coach/checkin` — gated behind
  `meeting.is_on_users_team(db, user, AgentType.CAREER_COACH)`, the same
  roster check every other optional-agent action already uses. 400 if
  there's no Employee File yet (nothing to work from — mirrors HR's
  `run_rollup` precondition exactly).
- Frontend: `/growth` gained an "Ask Career Coach for a check-in"
  button (shown only once Career Coach is actually on the roster) and a
  real display of what it returns — the resume highlights as a list,
  the suggested focus as its own line.

## Decisions worth knowing about

- **Why these three roles and not others.** QA Engineer and UX Reviewer
  fill genuinely distinct gaps in a realistic team (testing, interface
  quality) without overlapping Manager's job (planning/assignment) or
  Mentor's (code review generally). A "Product Manager" role was
  considered and dropped specifically because it would have overlapped
  Manager's big-picture role too much to justify as a separate agent.
  Technical Writer was chosen over "Performance Engineer" or
  "Accessibility Specialist" because documentation/communication is a
  real, often-underweighted skill in how junior engineers are actually
  evaluated — and ties naturally to this project's own "readiness gap"
  thesis.
- **Why Career Coach got the dedicated-action treatment and not QA/UX
  too.** QA Engineer and UX Reviewer immediately gained *more*
  functional surface area than Career Coach ever had, just by joining
  task chat and the roundtable (two conversational surfaces Career
  Coach was never going to be part of, task-appropriateness-wise). Career
  Coach was the one agent left with a single, thin surface (chat only)
  and no durable output — the clearest, most bounded gap to close well,
  rather than inventing a bespoke action for every agent and diluting
  the effort.

## The PostgreSQL story, round two

Migration 0010 needed something genuinely new relative to every earlier
migration: `AgentType` and `ReviewKind` are both *existing*, already-
populated Postgres enum types, used across several already-populated
tables — there's no "just add a column with its own type" escape hatch
the way `Organization.organization_id`-driven Stage 3 features had.

**`ALTER TYPE ... ADD VALUE`, applied carefully.** PostgreSQL 12+ (this
project targets 16) allows adding an enum label inside a transaction;
the only real restriction is that the new value can't be *used* — in an
INSERT or UPDATE — within that same transaction. This migration only
adds labels, nothing in it writes a row using any of them, so that
restriction never applies. This is narrower and safer than the
`ProjectSource` case Stage 3 deliberately avoided (see
`docs/STAGE3_COMPANY_RAG.md`) — there, an alternative signal
(`organization_id`) existed and made altering the enum simply
unnecessary. Here, an agent's identity is *the* field new agents need;
there's no workaround, so the migration does the ALTER, correctly.

**A second, quieter lesson**, only caught by actually running the
drift guard rather than assuming symmetry with the AgentType case:
`CAREER_CHECKIN` (14 characters) is longer than every prior `ReviewKind`
member — the previous longest, `SKILLS_ROLLUP`, is 13. SQLAlchemy's
`Enum` type sizes its SQLite representation to the longest member
*name* at the column's original creation time, so `reviews.kind`
stayed `VARCHAR(13)` even after the Python-side enum grew — a real
mismatch the model-drift guard caught immediately (SQLite never
enforces the length at the data level, so this was never a functional
bug, purely a metadata one, but the guard is right to have caught it).
Fixed by explicitly widening that one column in the same migration.
`AgentType`-typed columns needed no equivalent fix: none of the three
new agent names (`QA_ENGINEER`, `UX_REVIEWER`, `TECHNICAL_WRITER`)
exceed the existing 18-character max (`SECURITY_REVIEWER`).

**Not verified against real PostgreSQL as of this migration** — per
Meshari's explicit steer this round, local/SQLite verification is the
bar for now. The reasoning above is sound and was applied carefully,
but "reasoned through carefully" and "proven against the real thing"
are different claims, as the Stage 3 Postgres pass demonstrated twice
over. Re-run `smoke_test_migrations.py`'s Postgres section
(`MIGRATIONS_TEST_POSTGRES_URL=postgresql://venv:venv@localhost:5432/venv_test`)
before trusting this against a real Postgres instance.

## Testing

`smoke_test_ten_agents.py` (mocked LLM, no API key needed) covers:
the catalog now seeds exactly 7 optional agents (10 total with the
defaults) including all three new ones; QA Engineer/UX Reviewer/
Technical Writer are all reachable in the Meeting Room once added, and
refused (403) for a student who hasn't added them; QA Engineer and UX
Reviewer are directly addressable in task chat while Technical Writer
is correctly refused there; QA Engineer and UX Reviewer show up as
eligible roundtable specialists while Technical Writer correctly does
not; and the full Career Coach check-in lifecycle — no employee file
yet (400), a real check-in with real structured output (201, tagged
`career_coach`/`career_checkin`, real resume highlights), and refused
(403) for a student who hasn't added Career Coach.

Two pre-existing tests (`smoke_test_stage2_onboarding.py`,
`smoke_test_stage2_onboarding_router.py`) hardcoded the old 4-agent
catalog count — fixed to 7, not bugs introduced by this pass, just
assertions that needed updating for the larger roster.

Full suite: **36 files, 931 checks, all passing.**

## Frontend

- No changes needed to `lib/agents.ts` (the default-3 agent id/order
  list) or to any per-agent translation strings — confirmed by design:
  optional agents' name/description have always come from the backend
  catalog, not `lib/i18n`, specifically so adding one is additive on the
  frontend too.
- `lib/tasks.ts`'s `TASK_CHAT_AGENTS` mirror updated to match the
  backend exactly (QA Engineer, UX Reviewer added; Technical Writer
  deliberately not).
- **A real, pre-existing type safety issue fixed along the way**:
  `lib/reviews.ts`'s `Review.agentType` was typed as `AgentId` (only
  `"manager" | "mentor" | "hr"`) with a comment explicitly asserting
  "always one of the three default agents today" — true until Career
  Coach started writing reviews. Widened to the full `ApiAgentType`
  union, and a real `CareerCheckin` field added (resume highlights +
  suggested focus) instead of the old `isMentorMetrics`-only type guard
  silently dropping a career-checkin review's `metrics_json` to `null`.
- `/growth` gained the "Ask Career Coach for a check-in" button and
  display section described above.
- `next build` and `eslint` both clean; 20 routes, unchanged (no new
  pages this pass, only new capability on an existing one).

## Not built / worth knowing

- No dedicated action for QA Engineer or UX Reviewer beyond what they
  already get through task chat and the roundtable — a deliberate scope
  choice this pass (see "Decisions worth knowing about"), not an
  oversight.
- Nobody has clicked through any of this in an actual browser yet —
  same caveat every other stage's docs in this repo carry, still true
  here.
- The Postgres verification gap above.
