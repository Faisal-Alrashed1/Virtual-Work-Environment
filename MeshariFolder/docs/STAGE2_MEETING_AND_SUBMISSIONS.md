# Stage 2 — Meeting Room Extras & Richer Submissions

_Added Sep 2026. Sixth slice of Stage 2, from direct feedback: agents
added during onboarding couldn't be reached in the meeting room, and
submission was GitHub-link-only. Both fixed. Full regression verified:
264 backend checks across 12 suites, frontend lint clean, full `next
build` succeeds (13 routes). See `docs/STAGE2_TEAM_AND_ORIENTATION.md`
for the slice right before this one._

## 1. Extra agents in the meeting room

`meeting.py`'s `_PERSONA` dict only had entries for the default three —
chatting with an optional agent would have hit a `KeyError`. Fixed:

- Each of the four optional agents (Security Reviewer, Data Reviewer,
  Career Coach, DevOps) now has its own conversational persona, written
  directly in `meeting.py` (they don't have task-flow modules of their
  own the way Manager/Mentor/HR do, so there's nothing to reuse from).
- **Access is gated on the roster, not just the enum.** A graduate can
  only chat with an optional agent they actually added during
  onboarding — `meeting.is_on_users_team` checks `UserAgent`, and the
  router 403s otherwise. The default three stay unconditionally
  available, same as Stage 1.
- Frontend: the meeting room's agent picker, message bubbles, and opener
  text all now read from the graduate's real roster (`GET
  /users/me/agents`, already built for the board graph — see
  `STAGE2_TEAM_AND_ORIENTATION.md`) instead of the fixed three-agent
  list. `BoardSelection`'s widening pattern from that slice repeats here:
  `ApiAgentType` and `ChatMessage.agentType` both widened from the fixed
  three-value union to the full seven, with a small `displayFor()`
  helper falling back to the roster list when an id isn't one of the
  three defaults.

**Ripple effect worth knowing about:** widening `ApiAgentType` broke
type-checking in two places that had quietly assumed an agent id is
always one of the three defaults — `Task.createdByAgent` and
`Review.agentType`/`TaskMessage.agentType`. Both assumptions are
actually still correct today (only the Manager creates tasks or posts
thread replies; only Manager/Mentor/HR write reviews — the optional
agents don't do any of that yet), so those three stayed narrowed to
`AgentId`, with an explicit cast and a comment at each mapping boundary
(`toTask`, `toTaskMessage`, `toReview`) explaining why, rather than
widening domain types for a case that can't currently happen. Caught by
`next build`'s type-check, not left for someone to hit later.

## 2. Submissions: GitHub link, text, and files/images — any combination

Previously `PATCH /tasks/{id}/status` took an optional `github_link` and
that was the entire submission surface — nothing else was possible, and
the Mentor's review (`mentor.py`) hard-required a `github_link` or
raised `ValueError`.

- **`POST /tasks/{id}/submit`** (new, multipart) — `github_link`,
  `submission_text`, and up to 5 files, any non-empty combination (at
  least one of the three, checked server-side). Files capped at 10MB
  each. The older PATCH path still works unchanged for anything else
  calling it; this is the richer path the frontend now uses exclusively.
- **`TaskAttachment`** (new table) + **`app/storage.py`** — local disk
  under `settings.upload_dir` (`backend/uploads/`, gitignored), one
  helper module so a future swap to real cloud storage touches one file,
  same reasoning as `llm_client.py` being the one place that knows about
  the Anthropic SDK.
- **`GET /tasks/{id}/attachments/{attachment_id}`** (new) — download,
  task-owner-only (same 404-on-someone-else's-task pattern every other
  task endpoint already uses).
- **Mentor review, relaxed and extended** (`mentor.py`): reviews from
  whatever was actually submitted — repo context if there's a link,
  the graduate's own notes if there's text, filenames for non-image
  files. **Images go in as real vision content blocks**, not just named
  in the prompt — the Mentor can actually look at a submitted
  screenshot. Verified directly: a smoke-test image attachment's exact
  bytes, base64-encoded, land in the API call's content list.

**Frontend:** the workspace submission form now has a GitHub-link field
(optional), a notes textarea, and a file/image picker (up to 5, with
remove-before-submit). Attachments render as inline thumbnails for
images or download buttons for everything else, on both the workspace
task view and the review page — both fetch the file as an authenticated
blob first (`lib/attachments.ts`), since a plain `<img src>` or
`<a href>` can't attach the bearer token the download endpoint requires.

## What this means for the code — built

- `backend/app/agents/meeting.py` — 4 new personas, `is_on_users_team`.
- `backend/app/routers/meeting.py` — `_require_on_team` check on both
  endpoints.
- `backend/smoke_test_stage2_meeting.py` (new, 9 checks).
- `backend/app/models.py` — `TaskAttachment`, `Task.submission_text`,
  `Task.attachments` relationship.
- `backend/app/storage.py` (new) — save/read/base64 helpers.
- `backend/app/config.py` — `upload_dir` setting.
- `backend/app/routers/tasks.py` — `POST /{id}/submit`, `GET
  /{id}/attachments/{attachment_id}`, `MAX_ATTACHMENTS`/
  `MAX_ATTACHMENT_BYTES` constants.
- `backend/app/agents/mentor.py` — relaxed submission requirement,
  vision content blocks for images.
- `backend/app/routers/agents.py` — `mentor_review`'s docstring updated
  (was stale, said "github_link" specifically).
- `backend/smoke_test_stage2_submissions.py` (new, 41 checks).
- `.gitignore` — `backend/uploads/`.
- `frontend/src/lib/api.ts` — `ApiAgentType` widened to 7 values,
  `TaskAttachmentApiOut`, `TaskApiOut` extended, `requestBlob` helper,
  `api.tasks.submit`/`attachmentBlob`, `api.meeting.*` widened to plain
  `string` agent ids.
- `frontend/src/lib/tasks.ts` — `TaskAttachment` type, `Task` extended,
  `submitTask` rewritten for the multipart payload.
- `frontend/src/lib/meeting.ts`, `src/app/meeting/page.tsx` — extras
  support, `displayFor()` fallback.
- `frontend/src/lib/attachments.ts` (new), `frontend/src/components/
  workspace/attachment-list.tsx` (new).
- `frontend/src/components/workspace/task-workspace.tsx` — full
  submission form; `frontend/src/app/workspace/page.tsx` — `handleAdvance`
  widened to the richer payload; `frontend/src/app/tasks/[id]/review/
  page.tsx` — shows submission text/attachments alongside the link.
- `frontend/src/lib/reviews.ts` — cast + comment at `toReview` (see
  ripple-effect note above).
- All 12 backend smoke suites pass together — 264 checks, no
  regressions. Frontend eslint clean across `src/`, full `next build`
  succeeds (13 routes).

## Not built yet

- Non-image file *contents* aren't reviewed — only filenames are passed
  to the Mentor. Fine for now (there's no general "read arbitrary file
  type" story yet); worth revisiting if graduates start submitting
  things like PDFs or design files where content matters.
- No attachment preview for anything except images (no PDF thumbnail,
  no syntax-highlighted text preview) — just a download button.
- Local disk storage, as flagged in `storage.py`'s own docstring — fine
  for one box, would need swapping before any multi-instance deploy.
- Extra agents in the meeting room are still conversation-only — same
  "not wired into the task flow" limitation noted in
  `STAGE2_TEAM_AND_ORIENTATION.md`, unchanged by this slice.
