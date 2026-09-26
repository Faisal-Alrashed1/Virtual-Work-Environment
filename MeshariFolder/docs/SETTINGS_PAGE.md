# Settings page

**Why.** There was no single place for a graduate to rename themselves,
change their password, or find the CV-replacement flow (`/profile/cv`,
already built) and the language/theme toggles (already built, but only
ever shown inline in each page's header). "The usual things a settings
page has on any site" — profile, password, preferences — plus the one
thing specific to Venv, updating the CV the Manager plans around.

## What changed

**Backend**

- `app/schemas.py`'s `UserUpdate` — every field optional
  (`full_name`, `current_password`, `new_password`), so one endpoint
  covers "just rename me," "just change my password," or both at once.
- `PATCH /users/me` (`app/routers/users.py`, next to the existing
  `GET /users/me`):
  - A password change requires `current_password` to match what's on
    file (`verify_password` against `hashed_password`) and
    `new_password` to be 8+ characters — either failure is a 400 that
    touches nothing (a bad password attempt doesn't silently rename you
    just because `full_name` was also in the payload, and vice versa).
  - `full_name`, if given, is stripped and rejected (400) if empty.
  - Returns the updated `UserOut`, same shape `GET /users/me` returns.

**Frontend**

- New `/settings` page — three independent forms (profile / password /
  preferences) plus a CV section, deliberately kept independent so
  saving one never risks another (renaming yourself doesn't require
  re-entering a password):
  - **Profile** — email shown read-only (changing login email isn't
    supported — a real change would need re-verification, out of scope
    here), full name editable, track shown read-only
    (`useTrackLabels`).
  - **Password** — current + new password, calls `PATCH /users/me`.
  - **CV** — links to the existing `/profile/cv` replacement flow rather
    than duplicating it.
  - **Preferences** — the existing `LocaleToggle`/`ThemeToggle`
    components, surfaced here too so there's one place to find them,
    not a second implementation of language/theme switching.
- `lib/api.ts` gained `api.updateMe(payload)` → `PATCH /users/me`.
- Settings links added to the board, workspace, and meeting page headers
  (`nav.settings` in both `en.ts`/`ar.ts`).

## Decisions worth knowing about

- **No email change.** A real email change needs re-verification and
  touches login identity — deliberately left out rather than half-built.
  The email field is shown, read-only, so the graduate can at least see
  what's on file.
- **No account deletion.** Not asked for explicitly, and a destructive,
  irreversible action deserves its own careful design (what happens to
  the Project/Tasks/Reviews, whether it's soft or hard delete) rather
  than being bolted onto this pass. Left out entirely rather than built
  half-safely.
- **Three independent forms, not one big "save everything" form.** A
  single combined form risks a graduate re-typing their password just to
  fix a typo in their name, or the reverse — separating them means each
  save only touches what it says it touches.

## Testing

`backend/smoke_test_settings.py` (no LLM calls at all — pure auth/DB
logic) covers: rename alone; a blank name rejected without touching the
existing name; a password change attempted with no `current_password`
rejected; a password change with the *wrong* `current_password` rejected,
confirmed by the old password still working afterward; a too-short new
password rejected; a correct password change succeeding, confirmed by
the new password working and the old one no longer working; and a
combined rename + password change in one call.

Frontend: `next build` and `eslint` both clean with the new `/settings`
route (now 15 routes total, up from 14).

## Not done / worth knowing

- Nobody has clicked through the settings page in an actual browser yet.
- No rate-limiting or lockout on repeated failed password-change
  attempts — same as the rest of this codebase's auth surface today, not
  a gap introduced by this change specifically, but worth knowing before
  a real deployment.
