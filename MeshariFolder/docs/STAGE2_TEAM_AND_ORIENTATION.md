# Stage 2 — Team Graph & Orientation

_Added Sep 2026. Fifth slice of Stage 2, from direct feedback: extra
agents picked during onboarding weren't showing up anywhere in the UI,
and first-time graduates landed on `/board` with no introduction to
their project, team, or how the app works. Both fixed. Full regression
verified: 214 backend checks across 10 suites, frontend lint clean, full
`next build` succeeds (13 routes, including the new `/orientation`). See
`docs/STAGE2_ONBOARDING_FRONTEND.md` for the slice this builds on._

## What changed

**1. Extra agents now show up everywhere the default three do.**
Previously `AGENT_ORDER`/`AGENTS` (the fixed Manager/Mentor/HR list) was
the only thing driving the board's agents graph, the "your team" cards,
and the detail panel — a graduate's onboarding roster was stored
(`UserAgent`) but never read back anywhere in the frontend. Now:

- `GET /users/me/agents` (new, `routers/users.py`) returns just the
  graduate's *selected extras* — Manager/Mentor/HR aren't in this list,
  they're not per-user rows.
- The board graph (`flow-section.tsx`) lays out however many extra
  agents the graduate has, at the same fixed gap as the default three,
  and recenters the `user`/`employee-file` nodes to the new total width.
  A new `CustomAgentNode` (`board/nodes.tsx`) renders them — dashed
  border, neutral dot instead of a reserved agent color (there are only
  three of those, per `DESIGN.md`, and they're spoken for).
- `AgentCards` and `DetailPanel` show the same extras, for the same
  reason: leaving one surface fixed and one dynamic would just be a
  different, subtler version of the same bug.
- **Honest scope note:** an extra agent's detail panel says plainly
  *"Not wired into the task flow yet — Manager, Mentor, and HR do the
  actual reviewing for now."* There's no working page or meeting-room
  chat for these four yet (`meeting.py`'s `_PERSONA` dict only has
  entries for the default three) — checked before writing any copy that
  might have promised otherwise.

**2. First-time orientation.** New `/orientation` route: shows the
graduate's project (bootstrapping it via the same `assignNextTask` call
the task board's "ask manager" button already makes, if they don't have
one yet — `weekly_cycle.py`'s bootstrap is idempotent, so this is safe
to call more than once), their full team, and a short static "how it
works" walkthrough (one task at a time, submit via GitHub link, the
week wraps up together, meeting room for direct chat). One button into
`/board`. The onboarding wizard's last step now redirects here instead
of showing its own "done" panel — orientation *is* the completion
screen now, not a second one after it.

## What this means for the code — built

- `backend/app/routers/users.py` — `GET /users/me/agents`.
  `smoke_test_stage2_onboarding_router.py` — 2 new checks.
- `frontend/src/lib/team.ts` (new) — `fetchMyExtraAgents()`, mirrors the
  other `lib/*.ts` fetch-wrapper pattern.
- `frontend/src/components/board/nodes.tsx` — `CustomAgentNode`.
- `frontend/src/components/dashboard/flow-section.tsx` — dynamic layout
  (`totalAgents = defaults + extras`, positions computed from that
  instead of a fixed 3-slot record).
- `frontend/src/components/dashboard/agent-cards.tsx` — renders extras
  after the default three, with a plain "Added during onboarding" line
  rather than fabricated activity data (there's nothing real to show
  yet for agents that don't do anything in the backend).
- `frontend/src/components/board/detail-panel.tsx` — `BoardSelection`
  widened from the fixed `AgentId` union to `string | null` (the
  catalog can grow, so a closed literal type doesn't fit); looks up
  `AGENTS` first, falls back to the passed-in `extraAgents` list.
- `frontend/src/app/board/page.tsx` — fetches extras alongside the
  existing tasks/project/dashboard/reviews calls, threads them through
  to all three components above.
- `frontend/src/app/orientation/page.tsx` (new).
- `frontend/src/app/onboarding/cv/page.tsx` — the `"done"` step and its
  state (`finalTrack`/`finalAgents`) removed; `handleApproveAgents` now
  redirects to `/orientation`.

## Not built yet

- **Extra agents still don't do anything.** They're a roster entry and a
  UI card — no task-flow hook, no meeting-room chat. Real "collaborative"
  behavior for these four (beyond the Mentor-consult piece from
  `STAGE2_WEEKLY_CYCLE_FLOW.md`, which only involves the default three)
  is unscoped.
- **Orientation is shown once, on the natural path only** — reachable via
  the onboarding wizard's completion redirect, not gated or re-shown for
  a returning graduate who lands on `/board` directly. No persistent
  "has seen orientation" flag; matches "first time" without adding state
  that isn't clearly needed yet.
- Same carried-over gaps as `STAGE2_ONBOARDING_FRONTEND.md`: no mid-flow
  onboarding resume, no CV re-upload after completion.
