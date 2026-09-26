# Team Room: a shared chat with the whole team

**Why.** The Meeting Room (`docs/STAGE2_MEETING_AND_SUBMISSIONS.md`) was
always one running thread per `(user, agent)` pair — a real 1:1, but
never a room the graduate and their whole team could actually talk in
together the way a real team channel works. The Team Room is that: one
shared thread, everyone in it.

## What changed

**Backend**

- New table `team_messages` (`app/models.py`'s `TeamMessage`,
  `alembic/versions/0006_team_messages.py`) — one thread **per user**,
  unlike `chat_messages` which is one thread per `(user, agent)`.
  `agent_type` is nullable: `None` for the graduate's own messages, set
  to whichever agent replied otherwise. Reuses the same `agenttype`/
  `sendertype` enum types `chat_messages` already created
  (`create_type=False` in the migration — `CREATE TYPE` already ran for
  those in the baseline migration, on Postgres).

- `app/agents/meeting.py` gained the Team Room machinery, appended after
  the existing 1:1 functions:
  - `team_roster(db, user)` — every agent on the graduate's team
    (Manager/Mentor/HR plus whatever optional agents they added),
    defaults first.
  - `get_team_history(db, user)` — the shared thread, chronological.
  - `send_team_message(db, user, content)` — the entry point. Persists
    the graduate's message, then:
    1. **Routes** the message to one teammate via a forced tool call
       (`route_to_agent`, small tier — cheap, mechanical, same tier
       `roundtable.py`'s specialist turns use) — the router sees the
       whole thread and picks whichever team member it's actually that
       teammate's job to answer (code questions → Mentor, growth/
       behavior → HR, security → Security Reviewer, and so on; the
       Manager is the default only for something genuinely about the
       project or team as a whole).
    2. **Replies** as that agent (`meeting.PERSONA[chosen]` plus the
       Team Room framing plus the shared guardrails —
       `guardrails.MANAGER_DELEGATES_TASK_WORK` when the Manager was
       picked, `guardrails.ROLE_BOUNDARY` always), seeing the *entire*
       thread — every past turn, including other agents' replies,
       labeled by who said them (`[agent_id] content`) so an agent can
       pick up on what a teammate said earlier.
    3. **Persists and returns** the reply.

    A routing failure, or the model picking an agent that isn't actually
    on the roster, falls back to the Manager rather than ever failing
    the request — same "best-effort, never block the room" spirit as
    `roundtable.py`'s per-specialist turns.

- New endpoints: `GET /meeting/team` (history, empty list until the
  graduate's first message) and `POST /meeting/team` (send + get the
  reply). Registered in `routers/meeting.py` **before** the existing
  `GET/POST /meeting/{agent}` routes — Starlette matches routes in
  registration order, so the literal path `/meeting/team` has to be
  matched there rather than parsed as `agent: AgentType` (which would
  422 trying to parse "team" as an enum member).

**Frontend**

- `app/meeting/page.tsx` gained a "Team room" entry above the existing
  1:1 agent list, visually distinct (an icon, not a colored dot) since
  it's a different *kind* of conversation, not one more agent to pick.
  Selecting it swaps the thread source (`fetchTeamConversation`/
  `sendTeamMessage`, `lib/meeting.ts`) and renders each past turn with
  *that turn's own* speaker name and color (`m.agentType` varies message
  to message here, unlike a 1:1 thread where it's always the same
  agent) — so the room reads as one conversation with several people in
  it, not a single fixed persona.
- `lib/meeting.ts` gained a `TeamMessage` type (`agentType: string | null`,
  vs. `ChatMessage`'s always-set `agentType`) and the two fetch/send
  wrappers.

## Decisions worth knowing about

- **Only one agent replies per message, not all of them.** An earlier
  option was every agent on the roster replying to every graduate
  message — technically simpler, but unusable once someone has 4+
  optional agents: a "shared room" that answers every question four
  times over isn't actually shared, it's noisy. Routing to one relevant
  teammate, while keeping the *whole* thread visible to whoever replies
  next, is what makes it read as a room instead of a broadcast.
- **The router is a small-tier, single forced tool call** — cheap and
  fast, the same tier/pattern used for other mechanical decisions in
  this codebase (roundtable specialist comments, onboarding
  suggestions). The actual reply still runs on the main tier, same as
  everywhere else a judgment call is being made.
- **Team Room and the 1:1 Meeting Room are fully separate threads.**
  Talking to the Manager in the Team Room doesn't add anything to your
  1:1 Manager thread and vice versa — confirmed in
  `smoke_test_team_room.py`. This was a deliberate simplicity choice, not
  a limitation discovered later: merging the two would mean deciding how
  a 1:1 turn and a routed Team Room turn interleave, which isn't an
  obviously-right call to make without product input.

## Testing

`backend/smoke_test_team_room.py` (mocked LLM, no API key needed) covers:
empty room to start; a message routed to the Manager, with the reply's
content actually coming from the mock; message history ordering and
`agent_type` (`None` for the user's own turn); a second message routed to
the Mentor, with the Mentor's own persona text actually present in the
system prompt sent to the model (not the Manager's); a routing failure
(`RuntimeError`) falling back to the Manager instead of 500ing; an
out-of-roster pick (devops, not yet added) also falling back; devops
becoming reachable once added to the roster; the 1:1 Manager thread
staying untouched by Team Room activity; isolation between two different
users' rooms.

`smoke_test_migrations.py`'s model-drift guard (`compare_metadata` against
`Base.metadata`) passes with the new table on SQLite.

## Not done / worth knowing

- **The `0006_team_messages` migration has not been verified against
  PostgreSQL** — this session's sandbox had no reachable Postgres
  instance (`docker-compose.yml` needs Docker, not available here).
  `smoke_test_migrations.py` has a Postgres section
  (`MIGRATIONS_TEST_POSTGRES_URL`) that will catch a drift/enum problem
  if one exists — run it before trusting this in anything beyond
  SQLite/dev.
- Routing quality (does the model actually pick the right teammate for a
  given message) has only been exercised with mocked LLM responses in
  tests — not checked against a real model yet.
- Nobody has clicked through the Team Room tab in an actual browser yet.
