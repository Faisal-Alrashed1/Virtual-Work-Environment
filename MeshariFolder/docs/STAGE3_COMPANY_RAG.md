# Stage 3: companies on Venv

**Why.** The original spec: companies register, define job titles (any
field — not just IT), build a knowledge base per job title, invite
specific people to work under their account (with real company tasks or
the ordinary platform track), and see how those people are actually
doing. This doc covers all of it — company accounts, the RAG knowledge
base, a company's own real projects, the invite-with-consent flow, and
the roster/report view.

## Decisions confirmed with Meshari before building

Four scoping questions were open before this started; all four are
answered and reflected in what follows:

1. **Job titles are free text** — any company, any field, not drawn from
   the six IT tracks the *student* side still uses. (The student-side
   six-track system is untouched — opening that up to "all fields" too
   was floated but is a separate, much larger project.)
2. **RAG uses real embeddings + cosine-similarity retrieval, no vector
   database** — given the time constraint, the fastest path to genuine
   retrieval (not just truncated text in a prompt) without standing up
   new infrastructure.
3. **Company accounts are separate logins per rep, each with a role**
   (admin/HR/tech lead) — not one shared company login, but built to
   reuse the exact same auth system as everyone else, not a parallel one.
4. **A company's own real projects are distinct from a student's own
   project** — a company-authored project template
   (`CompanyProject`) is a different thing from a graduate bringing their
   own project (`Project`, `source=OWN`); the former becomes the latter
   only once a specific invited student accepts it.
5. **A student must see and explicitly consent** to what a company will
   be able to see before working under a company account — enforced
   server-side, not just a UI nicety.

## What's built

### Company accounts (`app/routers/company.py`, `app/routers/auth.py` unchanged)

- `AccountType` (`STUDENT`/`COMPANY`) and `CompanyRole`
  (`ADMIN`/`HR`/`TECH_LEAD`) on `User`. Every pre-Stage-3 row is
  `STUDENT` by default — purely additive.
- `Organization` gained `field` (free text) and `join_code` (a short,
  unambiguous code — no `0`/`O`/`1`/`I` — a teammate uses to join the
  same company instead of accidentally founding a new one).
- `POST /company/register` — two shapes in one endpoint: found a new
  company (`company_name` required, becomes its first `ADMIN`) or join
  an existing one via `join_code` + a self-picked `role`. **There's no
  email/invite delivery system in this app**, so joining is deliberately
  self-serve: anyone with the code picks their own role. That's an MVP
  simplification for a bootcamp demo, not a security boundary — a real
  deployment would want the founding admin to approve joiners, or at
  least restrict who can mint additional admins.
- Login is the **exact same** `POST /auth/login` every student uses — a
  company rep is just a `User` row with `account_type=COMPANY`, nothing
  parallel.
- `PATCH /users/me` (the existing settings endpoint) works for company
  users too — nothing there is student-specific.

### RAG knowledge base (`app/rag.py`, `KnowledgeMaterial`/`KnowledgeChunk`)

- Company uploads pasted text or a file (PDF/Word/plain text — reuses
  the CV-intake file-extraction helper) per job title.
- `chunk_text`: paragraph/sentence-aware chunking (breaks on `\n\n` or
  `. ` near the target size when it can find one, hard cut otherwise),
  ~1200 chars with 150 overlap.
- Chunks are embedded with OpenAI's `text-embedding-3-small` (batched,
  96 per call) and stored as plain `list[float]` in a JSON column —
  **no pgvector, no external vector DB service**. Retrieval
  (`app/rag.py:retrieve`) pulls every chunk for a job title and ranks by
  in-Python cosine similarity. Fine at a single company's realistic
  scale (a handful of documents per job title); a real vector index is a
  contained swap of `retrieve()`'s internals later, not a rewrite.
- `POST /company/job-titles/{id}/query` exposes real retrieval with real
  scores — a company can sanity-check what the knowledge base actually
  surfaces for a question. The frontend's "test the knowledge base" box
  on the job title page calls this directly, no mock in the UI either.
- Missing `OPENAI_API_KEY` fails cleanly (503 via the existing
  `LLMConfigError`/`ALL_PROVIDERS_FAILED` machinery in
  `app/agents/llm_client.py`) rather than a raw 500 — embeddings are
  OpenAI-specific here (no failover chain the way chat completions have
  one across providers).

### A company's own real projects (`CompanyProject`)

- Per job title, a company can create one or more **real** projects —
  title, description, and materials (same `combine_materials` helper and
  6000-char cap as a graduate's own project, extracted into
  `app/materials.py` so both features share it instead of duplicating
  it). This is a template, not yet any student's working project.
- Distinct on purpose from `Project(source=OWN)` — a graduate's own
  project is their own material about their own idea; a `CompanyProject`
  is the company's real work, offered to whichever student accepts it.

### Invitations, with enforced consent (`app/routers/invitations.py`)

- `POST /company/job-titles/{id}/invitations` — invite an email, with or
  without a named `CompanyProject` (the ordinary Manager-improvised
  platform track if none is named).
- `GET /invitations/mine` — every invitation sent to the logged-in
  account's email, matched by email so **the student doesn't need an
  account yet when the invite is sent**.
- `POST /invitations/{id}/accept` — **requires `consent: true` in the
  body**; missing or `false` is refused with a 400. The response the
  student sees before accepting (`INVITATION_DATA_NOTICE`, in
  `app/schemas.py`) spells out exactly what's shared (task
  submissions/progress and Mentor reviews for *this* project) and,
  explicitly, what isn't (CV, other projects, other agents, other
  conversations).
- Accepting does two things: affiliates the student with the company
  (`User.organization_id`, set unconditionally) and, if a `CompanyProject`
  was named, copies it into the student's actual `Project`
  (`title`/`description`/`materials_text`, `source` stays `OWN` — see
  "Why `ProjectSource` wasn't touched" below). **That `Project` is
  picked up automatically by the graduate's next
  `POST /agents/manager/assign-task` call, exactly the way an own-project
  already is — zero changes were needed to `weekly_cycle.py`.**
- `POST /invitations/{id}/decline` — no side effects.
- A company account can't accept its own invitation (403); only a
  `STUDENT` account can accept/decline.
- **Real email** (`app/email.py`): sending an invitation now also sends
  an actual email over SMTP (any provider — Gmail, SendGrid, Mailgun,
  AWS SES, Postmark's relay, a real mail server), with the company/job-
  title/project named and a link back to the frontend's `/invitations`
  page. Optional by design, same spirit as `OPENAI_API_KEY` for RAG: no
  `SMTP_HOST` configured, or a real send failure, never blocks creating
  the invitation — `Invitation.email_sent` (migration 0009) tracks
  honestly whether it actually went out, and the student can always
  find the invitation via `GET /invitations/mine` regardless.

### The company's roster + "end-of-week report" (`GET /company/students`, `GET /company/students/{invitation_id}`)

- **Built as ordinary polling REST endpoints, not websockets.** Nothing
  in this codebase uses websockets anywhere; the existing pattern for
  anything live-ish (the roundtable's running state,
  `docs/BACKGROUND_ROUNDTABLE.md`) is already poll-and-refresh, so this
  matches rather than introduces a new mechanism.
- The **"end-of-week report" is deliberately not a new report-generation
  pipeline** — it's the Manager's `WEEK_PROGRESS` review and HR's
  `BEHAVIORAL` review, the same reviews the weekly cycle already writes
  for every student (company-affiliated or not), surfaced per week to
  the company that invited this student. Zero new agent/LLM logic.
- Scope is exactly `INVITATION_DATA_NOTICE`'s promise: reuses `TaskOut`
  and `ReviewOut` as-is (the existing schemas already used for the
  student's own view), plus name/email (already known — the company
  addressed the invite to that person).
- **The join key is `User.organization_id`, not `Project.organization_id`.**
  A platform-track invitation (no named `CompanyProject`) still produces
  a real `Project` through the ordinary `assign-task` bootstrap, which
  has no reason to know about organizations — so that column stays
  unset for it. `User.organization_id`, set unconditionally on accept,
  is the join that works for both cases.

### Role permissions (`require_company_role` in `app/routers/company.py`)

`CompanyRole` was modeled from the start but didn't gate anything until
this pass. Two actions now are, chosen because they carry real
organizational weight rather than being routine content curation:
sending an invitation (**ADMIN/HR** — a hiring decision) and creating a
company's own real project (**ADMIN/TECH_LEAD** — a technical/scope
decision). Everything else in the company router — job titles, material
upload, RAG query, the roster, listing — stays open to any company role,
deliberately: over-restricting a small company's day-to-day use adds
friction without much real benefit at this stage. `smoke_test_company_roles.py`
covers both restrictions (the allowed roles succeed, the disallowed one
gets a 403 naming which roles are allowed) and confirms the unrestricted
actions still work for every role.

### A student's own visibility (`GET /invitations/{id}/visibility`, `app/company_roster.py`)

The consent notice at accept time says what the company *will* see;
this is the live, checkable answer to whether that's still true —
reachable any time after accepting, not just taken on faith once.
Extracted the roster-building logic (`student_project`, `task_counts`,
`current_week_number`, `student_summary`, `student_detail`) out of
`routers/company.py` into a shared module, `app/company_roster.py`, so
both the company's `GET /company/students/{id}` and the student's
`GET /invitations/{id}/visibility` call the **literal same functions**
— a transparency feature that reused nothing would risk quietly
drifting out of sync with what the company actually sees; this one
architecturally can't. `smoke_test_student_visibility.py` proves it
directly: after a real task/submission/review cycle (mocked LLM), the
student's response and the company's response for the same invitation
are asserted **byte-for-byte identical**
(`r_student.json() == r_company.json()`), not just similar-looking.
404s until the invitation is accepted ("nothing has been shared yet").

## Decisions worth knowing about

- **Why `ProjectSource` was never touched.** A company-sourced project
  could have been a new `ProjectSource.COMPANY` enum value. It wasn't:
  extending an *existing* Postgres native enum type needs
  `ALTER TYPE ... ADD VALUE`, which has real transactional footguns (it
  can't always run inside the same transaction as later statements that
  use the new value, depending on Postgres version and how Alembic
  batches things) — not worth the risk when `organization_id` being set
  is sufficient signal and needs no new migration surface at all. A
  company-sourced project's `source` stays `OWN`.
- **Why joining a company is self-serve.** No email delivery system
  exists anywhere in this app. A real deployment would want the founding
  admin to approve additional members, or at least gate who can mint
  another `ADMIN`. Flagged here rather than silently shipped as if it
  were the intended long-term design.
- **Why the roster/report reuses `TaskOut`/`ReviewOut` instead of new
  schemas.** They already return exactly what `INVITATION_DATA_NOTICE`
  promises and nothing more — reusing them is both less code and a
  built-in guarantee that the company view can't accidentally leak a
  field the consent notice didn't mention.
- **Why RAG has no vector database.** Chunked embeddings as plain JSON
  arrays, ranked by in-Python cosine similarity, is genuine retrieval —
  not a mock, not truncated text — while adding zero new infrastructure.
  It's O(n) per query over however many chunks a job title has, which is
  fine at a single company's realistic scale (see `app/rag.py`'s
  docstring for the upgrade path if that stops being true).

## The PostgreSQL story (read this if anything about migrations 0006-0008 looks off)

Every earlier checkpoint in this stage's build carried the caveat "not
verified against PostgreSQL — no instance reachable in this sandbox."
That changed: Postgres 16 was installed directly in the sandbox (`apt`,
not Docker — this sandbox's network allowlist includes
`archive.ubuntu.com`/`security.ubuntu.com`) and the full migration suite
plus a broad swath of application smoke tests were run against it for
real. **Two real, deploy-breaking bugs turned up** that SQLite's total
lack of enum/CHECK enforcement had let through completely undetected —
both now fixed, both worth understanding if you write a future migration
that adds or reuses a Postgres enum type:

1. **`ADD COLUMN` doesn't auto-create the enum type it references.**
   `op.create_table(...)` with an `Enum` column emits `CREATE TYPE`
   automatically. `batch_alter_table(...).add_column(...)` does not.
   Migration 0007 originally referenced `accounttype`/`companyrole`
   without ever creating them — fixed by creating both types explicitly
   (`checkfirst=True`, Postgres-only) before the `ADD COLUMN`.
2. **Generic `sa.Enum(..., create_type=False)` does not reliably
   suppress `CREATE TYPE` inside `op.create_table`.** Traced into
   SQLAlchemy's source: the generic `Enum` type's dialect-adaptation
   path drops the `create_type=False` setting before the DDL event that
   actually emits `CREATE TYPE` fires, so `op.create_table` tries to
   recreate an already-existing type and fails with
   `DuplicateObject: type "X" already exists`. This one was latent in
   **migration 0006** (`team_messages`, reusing `agenttype`/`sendertype`
   from the baseline) since the session it was written — never actually
   hit until this verification pass. Fixed by switching every Enum
   column across 0006/0007/0008 to
   `sqlalchemy.dialects.postgresql.ENUM` specifically, which honors
   `create_type` correctly — confirmed it also degrades cleanly to an
   ordinary column on SQLite, so no per-dialect branching is needed at
   the column-definition level.

A third, smaller bug: a `server_default='student'` (lowercase) on the
new `account_type` column didn't match the enum's actual label spelling
— this codebase's `Enum` columns store the Python member's *name*
(`'STUDENT'`), not its `.value` (`'student'`), and Postgres's native enum
type validates that strictly where SQLite doesn't check at all. Fixed to
`server_default='STUDENT'`.

**What's now genuinely verified, on a real Postgres 16 instance,
matching the project's stated target exactly:**
`smoke_test_migrations.py`'s full Postgres section (fresh build, the
model-drift guard, enum type creation, downgrade including enum
cleanup, upgrade-after-downgrade, legacy-database adoption,
stale-database refusal) plus 14 application-level smoke test files
spanning Stage 1 through Stage 3 (872 checks total, run against both
SQLite and Postgres, all passing identically on both).

**What's still not verified:** the sandbox Postgres instance is
ephemeral to this container and gets wiped between sessions — this
verification needs to be re-run (`docker-compose up`, then
`MIGRATIONS_TEST_POSTGRES_URL=postgresql://venv:venv@localhost:5432/venv_test
python smoke_test_migrations.py`, per that file's own header comment) on
whatever's used for actual deployment before trusting it there. The fix
itself is sound and was proven against the real thing, but "proven once
in a throwaway sandbox" and "proven in your deployment target" are
different claims.

## Testing

Four dedicated smoke test files, no shared fixtures beyond the pattern
every other suite in this repo already uses:

- **`smoke_test_company_rag.py`** — registration (found/join), role
  assignment, student accounts blocked from company endpoints, job
  titles, material upload and chunking, cross-org isolation, and —
  importantly — **real retrieval ranking**: embeddings are mocked with a
  small deterministic keyword-vector fake (not just a canned return
  value), so "a Python-heavy chunk actually outranks a Kubernetes-heavy
  one for a 'python' query, with a real cosine score" is a genuine
  assertion, not theater. Also covers the missing-`OPENAI_API_KEY` → 503
  path.
- **`smoke_test_company_invitations.py`** — company projects distinct
  from own-projects, invitations with and without a named project, a
  project from the wrong job title refused, consent enforcement
  (missing/`false` both 400), double-response prevention, a company
  account blocked from accepting its own invitation, and end-to-end
  confirmation that an accepted company project surfaces through
  `/projects/me`.
- **`smoke_test_company_students.py`** — empty roster before acceptance,
  a still-pending invitation never appearing on the roster, cross-org
  isolation on both the list and detail endpoints, and a real run
  through actual `assign-task`/`plan_week` (mocked LLM) confirming the
  roster reflects real task creation — plus a direct check that a
  written `WEEK_PROGRESS` review surfaces through the detail endpoint.
- **`smoke_test_company_roles.py`** — each restricted action succeeds
  for its allowed roles and 403s (naming the allowed roles) for the
  disallowed one; confirms the unrestricted actions still work for
  every role.
- **`smoke_test_invitation_emails.py`** — graceful degradation (no SMTP
  configured, and a real send failure) never blocks creating the
  invitation, plus the one that matters most: a genuine local SMTP
  server (`aiosmtpd`, not a mock) actually receiving a correctly-
  addressed, correctly-worded email through the real HTTP endpoint —
  envelope from/to, company/job-title/project content, the accept link,
  and both MIME parts all checked against what the server really got.
- **`smoke_test_student_visibility.py`** — 404 before accepting, cross-
  student isolation, a declined invitation still refused, and a real
  end-to-end run (task assignment, submission, a mocked Mentor review)
  proving the student's and the company's responses for the same
  invitation come back byte-for-byte identical.
- **`smoke_test_migrations.py`**'s Postgres section — see above.

Full suite: **35 files, 911 checks, all passing** — on SQLite always,
and confirmed identically on real Postgres 16 as of the pass that added
migrations 0007/0008 (re-run that section against your actual
deployment target before trusting it there too — the sandbox instance
this was checked against doesn't persist between sessions).

## Frontend

- `/company/register` — found a company or join one via code + role.
- `/company` — org card (name, field, copyable join code), job title
  creation, job titles list.
- `/company/job-titles/[id]` — material upload (paste or file),
  materials list, **real projects** (create/list), **invite a
  candidate** (email + optional project picker, shows sent invitations
  and their status), and the RAG **"test the knowledge base"** search
  box (real scores, not mocked).
- `/company/students` — the roster: name, email, job title, project
  title, current week, task-count snapshot.
- `/company/students/[invitationId]` — week-by-week detail: each week's
  tasks and whichever end-of-week reviews exist for it so far.
- `/invitations` — the student's consent screen. Each pending invitation
  shows the company, job title, and the named project (or "platform
  track"), plus the exact data-sharing notice in its own block. Accept
  is disabled until an explicit checkbox is ticked, mirroring the
  server-side rule rather than just trusting the click. An accepted
  invitation gets a **"See what they see"** link.
- `/invitations/[id]/visibility` — the promise checked live: the exact
  same week/task/review data the company's own roster detail page
  shows them, reusing the same layout so the two are visibly the same
  view, not just described as equivalent.
- `/login` now branches post-login on `account_type` (company → `/company`,
  student → `/board`); `/board` gained a discoverable "Invitations" nav
  link with a pending-count badge.

`next build` and `eslint` both clean — 20 routes total (up from 14
before this stage).

## Not built / worth knowing

- Nobody has clicked through any of this in an actual browser yet — same
  caveat every other stage's docs in this repo carry, still true here.
- The guardrail/agent-behavior pieces from the task-chat/Team Room work
  (`docs/TASK_CHAT.md`) weren't extended to anything company-specific —
  there's no agent-facing "you're now planning for a company-sourced
  project" framing anywhere; the Manager/Mentor treat a company-sourced
  project exactly like any graduate's own project, which is correct
  today but worth knowing if company-specific agent behavior is ever
  wanted.
