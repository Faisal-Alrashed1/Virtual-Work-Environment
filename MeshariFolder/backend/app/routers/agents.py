from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.agents import meeting, orchestrator, task_chat
from app.auth import get_current_user
from app.database import get_db
from app.models import AgentType, Task, TaskStatus, User
from app.schemas import ReviewOut, TaskChatRequest, TaskMessageOut, TaskOut

router = APIRouter(prefix="/agents", tags=["agents"])


def _get_owned_task(task_id: str, current_user: User, db: Session) -> Task:
    task = db.get(Task, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/manager/assign-task", response_model=TaskOut, status_code=201)
def manager_assign_task(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Manager assigns the next task — the graduate's first one at
    registration, or any time they're ready for more (frontend calls this
    from the home board's Manager node, or once a task reaches 'reviewed').
    """
    return orchestrator.manager_assign_task(db, current_user)


@router.post("/manager/reply/{task_id}", response_model=TaskMessageOut, status_code=201)
def manager_reply(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manager reads the task thread and replies — call after the graduate
    posts a message via POST /tasks/{id}/messages."""
    task = _get_owned_task(task_id, current_user, db)
    return orchestrator.manager_reply(db, task, current_user)


@router.post("/task/{task_id}/reply", response_model=TaskMessageOut, status_code=201)
def task_chat_reply(
    task_id: str,
    payload: TaskChatRequest = TaskChatRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reply in a task's thread from whichever team member the graduate is
    addressing (docs/TASK_CHAT.md) — the Mentor by default, or the
    Manager / a technical roster agent (Security Reviewer, Data Reviewer,
    DevOps) if the graduate picked one in the workspace's agent switcher.
    Call after POST /tasks/{id}/messages. This is the endpoint the app
    itself now uses; /agents/manager/reply/{task_id} above still works
    unchanged for anything still calling it directly."""
    task = _get_owned_task(task_id, current_user, db)
    if not task_chat.is_available_for_task(db, current_user, payload.agent_type):
        raise HTTPException(
            status_code=403,
            detail="That agent isn't available for this task yet.",
        )
    return orchestrator.task_chat_reply(db, task, current_user, payload.agent_type)


@router.post("/mentor/review/{task_id}", response_model=ReviewOut, status_code=201)
def mentor_review(
    task_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mentor reviews a submitted task and moves it to 'reviewed'. Stage 2:
    the submission can be a GitHub link, free text, image/file
    attachments, or any mix (docs/STAGE2_MEETING_AND_SUBMISSIONS.md), not
    github_link specifically. Only valid once the task is 'submitted' —
    the frontend's task detail panel already assumes this gate; this is
    the server-side version of it.
    """
    task = _get_owned_task(task_id, current_user, db)
    if task.status != TaskStatus.SUBMITTED:
        raise HTTPException(
            status_code=400,
            detail=f"Task must be 'submitted' to review (currently '{task.status.value}').",
        )
    try:
        review = orchestrator.mentor_review(db, task, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Stage 2: Security Reviewer/Data Reviewer/DevOps weigh in too, if the
    # graduate has any of them on their team, then the Manager synthesizes.
    # That discussion runs in the BACKGROUND (docs/BACKGROUND_ROUNDTABLE.md): the
    # Mentor's review — what the graduate is waiting for — is returned now, and the
    # discussion appears in the task thread as it is written. Best-effort, never
    # blocks or breaks the review that already succeeded above.
    orchestrator.start_roundtable(db, task, current_user, background_tasks)
    return review


@router.post("/hr/rollup", response_model=ReviewOut, status_code=201)
def hr_rollup(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    HR rolls up Mentor review history into an updated Employee File plus a
    standalone rollup Review. Cadence (after every task? weekly?) is still
    an open decision from docs/PROJECT_STATUS.md — this just runs it once,
    on demand.
    """
    try:
        return orchestrator.hr_rollup(db, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/career-coach/checkin", response_model=ReviewOut, status_code=201)
def career_coach_checkin(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    The Career Coach's one dedicated action beyond chat (docs/
    TEN_AGENTS.md): reads the Employee File and CV, writes a career
    check-in — real resume bullets and one thing to focus on next — as a
    standalone Review. Requires Career Coach to actually be on the
    graduate's roster (they added it during onboarding, or later).
    """
    if not meeting.is_on_users_team(db, current_user, AgentType.CAREER_COACH):
        raise HTTPException(status_code=403, detail="Career Coach isn't on your team yet.")
    try:
        return orchestrator.career_coach_checkin(db, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
