# Task chat: an agent switcher, and a narrower Manager

**Why.** Every message in a task thread used to go to the Manager — the
only in-task reply endpoint that existed
(`POST /agents/manager/reply/{task_id}`), called unconditionally by the
workspace on every send. That's backwards: the Manager should be the one
handing out big tasks and writing end-of-week feedback, not fielding
"how do I structure this component?" on a Tuesday afternoon. The Mentor —
whose whole job is reviewing the work — is who a graduate should actually
be working *with*, the way a junior engineer sits next to a senior one.

## What changed

**Backend**

- `app/agents/guardrails.py` — three pieces of instruction text, shared
  across every agent conversation surface (task threads, the Meeting
  Room, the Team Room):
  - `ROLE_BOUNDARY` — every agent declines requests outside its job at
    Venv (personal topics, general trivia, unrelated help) instead of
    answering as a generic assistant.
  - `MANAGER_DELEGATES_TASK_WORK` — added to the Manager's prompt
    whenever it's talking with the graduate about their work. Hands-on
    task help (debugging, "how do I approach this?", reviewing their
    thinking on what they're building right now) gets redirected to the
    Mentor instead of answered directly. Genuine project/week-level
    questions still get answered.
  - `MENTOR_TASK_SENIOR_FRAMING` — added to the Mentor's prompt in a task
    thread: frames it as the graduate's day-to-day point of contact on
    *this* task, not just the agent that reviews it once submitted.

  These are plain instructions for the model to weigh, not keyword
  filters — the same approach the Mentor's rubric and the task bank's
  principles already use elsewhere in this codebase.

- `app/agents/mentor.py` gained `respond_in_thread(db, task, user)`,
  mirroring `manager.respond_in_thread`'s shape (same history-building,
  same `post_message` tool, same message-persisting pattern) but with
  `MENTOR_TASK_SENIOR_FRAMING` in its system prompt.

- `app/agents/manager.py`'s existing `respond_in_thread` now includes
  `MANAGER_DELEGATES_TASK_WORK` in its system prompt. Nothing else about
  it changed — same endpoint, same function signature, same tool.

- `app/agents/task_chat.py` (new) — routes a task-thread reply to
  whichever agent the graduate is addressing:
  - `TASK_CHAT_AGENTS = {MENTOR, MANAGER, SECURITY_REVIEWER, DATA_REVIEWER, DEVOPS}`,
    default `MENTOR`.
  - `is_available_for_task(db, user, agent)` — `agent` must be in
    `TASK_CHAT_AGENTS` *and* on the graduate's team
    (`meeting.is_on_users_team`). HR and Career Coach are deliberately
    excluded — HR's job is periodic/behavioral, not task-level; Career
    Coach is about career topics, not the task at hand. Both stay
    reachable in the Meeting Room and the Team Room.
  - `reply_in_thread(db, task, user, agent_type)` dispatches: Manager and
    Mentor go to their own `respond_in_thread`; a technical roster agent
    (Security Reviewer/Data Reviewer/DevOps) goes through
    `_roster_agent_reply`, which reuses `meeting.PERSONA` plus the task's
    context — those three have no task-flow module of their own, same as
    how `roundtable.py` already reuses `meeting.PERSONA` for its
    specialists.

- New endpoint: `POST /agents/task/{task_id}/reply`, body
  `{"agent_type": "mentor"}` (defaults to `mentor` if the body is
  omitted entirely — `payload: TaskChatRequest = TaskChatRequest()` in
  the route signature, needed because FastAPI otherwise 422s a POST with
  no body at all even when every field has a default). 403s if the agent
  isn't available for task chat. `POST /agents/manager/reply/{task_id}`
  is unchanged and still works for any caller still using it directly —
  the workspace itself now calls the new endpoint instead.

**Frontend**

- `components/workspace/agents-meeting.tsx` gained a "working with" row:
  buttons for Mentor, Manager, and any technical roster agent the
  graduate has added, mirroring `TASK_CHAT_AGENTS` exactly
  (`lib/tasks.ts`'s `TASK_CHAT_AGENTS`/`DEFAULT_TASK_CHAT_AGENT`). Picking
  one sets which agent the next message goes to. Message bubbles resolve
  each speaker's own name/color rather than assuming a single fixed
  agent, since a thread can now have Mentor, Manager, and DevOps replies
  side by side.
- `components/workspace/task-workspace.tsx` gained a banner — "New task
  from {Manager}" — shown while `task.status === "todo"` (a fresh,
  unstarted task), styled in the assigning agent's color. Previously a
  new task was only announced by a quiet meta line and the Manager's
  intro message in the thread.
- `app/workspace/page.tsx` carries `chatAgent` state, reset to the Mentor
  every time a different task is opened (so switching tasks never leaves
  you "still talking to DevOps" on an unrelated task by accident).
  `handleSendMessage` now takes the addressed agent and calls
  `taskChatReply` (`lib/tasks.ts`) instead of the old, Manager-only
  `managerReply`.

## Decisions worth knowing about

- **Why HR and Career Coach are out of task chat.** Both have a real job
  elsewhere (HR's periodic rollup, Career Coach's Meeting-Room/Team-Room
  conversations) that isn't "help with this specific task." Keeping them
  out of `TASK_CHAT_AGENTS` is a product decision, not a technical limit
  — `is_available_for_task` would need one line changed to add either
  back if that's wanted later.
- **Why a roster agent's task reply has no dedicated module.** Security
  Reviewer/Data Reviewer/DevOps already only exist as Meeting-Room
  personas and roundtable specialists (`meeting.PERSONA`) — they've never
  had their own `agents/*.py` file. Giving them one just for task chat
  would duplicate `meeting.PERSONA` for no real benefit; `task_chat.py`
  reuses it instead, the same way `roundtable.py` already does.
- **The guardrails are prompt text, not code-level filters.** A graduate
  asking the Manager "can you help me debug this?" isn't blocked — the
  Manager can still choose to say something like "that's really one for
  the Mentor" and then actually engage if the graduate insists it's
  project-level. This is a judgment call handed to the model, consistent
  with how the rest of this codebase already treats agent behavior.

## Testing

`backend/smoke_test_task_chat.py` (mocked LLM, no API key needed) covers:
default reply routes to the Mentor; explicitly addressing the Manager
still works; HR is refused (403) even though it's a default agent
elsewhere; an un-added roster agent is refused, then works once added;
the thread ends up with Mentor, Manager, and DevOps replies all visible
together.

## Not done / worth knowing

- The Manager's redirect and every agent's role-boundary are steered by
  prompt instructions, not verified against real model behavior yet —
  only mocked in tests. Worth a real-key pass (`e2e_real_llm.py`) before
  calling this demo-ready, the same caveat `PROJECT_STATUS.md` already
  carries for the rest of the agent logic.
- Nobody has clicked through the new "working with" switcher or the
  "new task" banner in an actual browser yet.
