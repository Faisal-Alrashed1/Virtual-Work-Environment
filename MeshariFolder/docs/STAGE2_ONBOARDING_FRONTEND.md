# Stage 2 — Onboarding Frontend

_Added Sep 2026. Fourth slice of Stage 2: `/onboarding/cv` is now the
real 4-step wizard (CV file → adaptive Q&A → track approval → agent-
roster approval), replacing Stage 1's paste-only textarea. TypeScript
compiles clean, ESLint clean, full `next build` succeeds. See
`docs/STAGE2_ONBOARDING_FLOW.md` for the backend this wires up._

## What's built

`src/app/onboarding/cv/page.tsx` is now a small client-side state
machine (`cv → qa → track → agents → done`, plus an `already-done` state
for a graduate who's already been through it), driving the 5 endpoints
from `STAGE2_ONBOARDING_FLOW.md` in order:

1. **CV** — a real file input (PDF/.docx/.txt), styled as a drop-zone
   consistent with the rest of the app's hairline-border look. "Skip for
   now" still exits straight to `/board`, same as Stage 1.
2. **Q&A** — the agent-generated questions render as plain text inputs;
   leaving one blank is how a graduate skips it (no separate skip
   button needed — the field is just optional). A free-text box underneath
   for anything they want to add themselves.
3. **Track** — shows the suggestion + the agent's one-line reasoning, plus
   a `<select>` (defaulting to the suggestion) to override it. Submitting
   sends `null` if unchanged, the picked value if not — matching the
   backend's "`null` = approve as-is" contract.
4. **Agents** — every catalog entry (`GET /onboarding/catalog`, not just
   the suggested subset — see below) as a checkbox list, pre-checked with
   whatever was suggested for the approved track.
5. **Done** — final track + roster, one button back to `/board`.

## Why `GET /onboarding/catalog` needed adding

The router (previous slice) only ever returned the *suggested* agents at
the track-approval step — there was no way for the frontend to show the
graduate the full pickable set so they could add something that wasn't
suggested. Added a small public (no-auth) endpoint that returns the whole
`AgentCatalog` table; the roster screen fetches it once, right alongside
the CV upload call, and pre-checks it with whatever the track step later
suggests.

## Known gaps, carried over honestly rather than papered over

- **No mid-flow resume.** `STAGE2_ONBOARDING_FLOW.md`'s gotcha still
  applies — the graph can't cleanly restart a thread that has a pending
  interrupt. On load, the page only distinguishes "already complete"
  (shows a done screen) from everything else (starts the wizard fresh at
  the CV step). A graduate who uploaded a CV, closed the tab, and comes
  back mid-Q&A will re-upload rather than pick up where they left off.
  Real fix needs the router to expose the last interrupt's payload
  alongside `onboarding_stage`, not just the stage name — worth a look
  next time this page is touched.
- **No re-upload after completion.** Once `onboarding_stage` is
  `complete`, this page only offers a link back to `/board` — it doesn't
  attempt to re-run the graph, since that path is untested (a fresh
  `invoke()` on a thread that already reached `END`, not one with a
  pending interrupt — plausibly fine, just not verified, so the copy
  doesn't promise it). **`detail-panel.tsx`'s board panel still links
  here with "Add/Update" copy from Stage 1** — that promise is now
  slightly stale for a graduate who's already onboarded; worth fixing
  either that link's copy or actually building the re-upload path, not
  both left as-is indefinitely.
- **Track override always uses the `<select>` list**, not something
  smarter (no re-suggestion, no reasoning shown for alternatives) — a
  deliberate small scope, not a missed corner.

## What this means for the code — built

- `src/app/onboarding/cv/page.tsx` — rewritten (previously ~90 lines,
  paste-only; now the 5-step wizard above).
- `src/lib/api.ts` — Stage 2 wire types + `api.onboarding.*` (catalog,
  state, uploadCv, submitQa, approveTrack, approveAgents). Also fixed a
  real bug the file-upload work surfaced: `request()` was force-setting
  `Content-Type: application/json` on every body including `FormData`,
  which would have broken the multipart boundary — excluded `FormData`
  alongside the existing `URLSearchParams` exclusion.
- `src/lib/tracks.ts` (new) — track display names + the selectable-track
  list for the override dropdown, mirroring `lib/agents.ts`'s pattern.
- `backend/app/routers/onboarding.py` — added `GET /onboarding/catalog`
  (public). `smoke_test_stage2_onboarding_router.py` — 3 new checks for
  it. All 10 backend smoke suites still pass together — 212 checks,
  no regressions.
- Verified: `tsc --noEmit` clean (one pre-existing, unrelated
  `LayoutProps` error confirmed present even with every Stage 2 frontend
  change stashed — a Next.js 16 generated-types quirk, not something this
  work touched), `eslint` clean on every changed file, full `next build`
  succeeds.

## Not built yet

- The two gaps above (mid-flow resume, post-completion re-upload).
- Nothing else in `frontend/` reflects Stage 2 yet — the home board
  doesn't show track or the agent roster anywhere, and the weekly-cycle
  collaboration/own-project backend pieces have no frontend surface at
  all. Whichever of those is next, same pattern as this slice: check
  `DESIGN.md` and the existing page it's closest to before writing
  anything new.
