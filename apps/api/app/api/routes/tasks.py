import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.api.dependencies import owned_task
from app.core.db import get_db
from app.core.security import current_user
from app.models.domain import Evaluation, Message, Submission, SubmissionArtifact, Task, TaskStatus, User, WorkCycle
from app.schemas.api import StatusIn, SubmissionIn
from app.services.github import pin_repository
from app.services.orchestrator import create_cycle_and_task, evaluate_task, weekly_report

router = APIRouter()

@router.patch("/tasks/{task_id}/status")
def change_status(task_id: str, data: StatusIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = owned_task(db, task_id, user)
    allowed = {TaskStatus.todo: {TaskStatus.in_progress}, TaskStatus.in_progress: {TaskStatus.submitted}}
    if data.status not in allowed.get(task.status, set()):
        raise HTTPException(409, "انتقال حالة غير مسموح")
    task.status = data.status
    if data.status == TaskStatus.in_progress:
        db.add(Message(user_id=user.id, task_id=task.id, agent="manager", sender="system", kind="agent_sync", body="بدأ Junior المهمة. سيشرف Senior على التنفيذ ويرفع تقريره الفني."))
        db.add(Message(user_id=user.id, task_id=task.id, agent="senior", sender="agent", kind="status_update", body="بدأنا التنفيذ. قسّم المهمة إلى خطوة صغيرة، واشرح لي خطتك قبل كتابة الحل. سأعطيك تلميحًا إذا احتجت."))
        db.add(Message(user_id=user.id, task_id=task.id, agent="hr", sender="system", kind="agent_sync", body="بدأ المستخدم المهمة. راقب الاستمرارية والتواصل والاستجابة للملاحظات."))
    db.commit()
    return {"status": task.status}

@router.post("/tasks/{task_id}/submit")
def submit(task_id: str, data: SubmissionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = owned_task(db, task_id, user)
    if task.status not in {TaskStatus.in_progress, TaskStatus.todo, TaskStatus.discussion}:
        raise HTTPException(409, "المهمة ليست جاهزة للتسليم")
    if data.github_url:
        try:
            pinned = pin_repository(str(data.github_url))
        except ValueError as e:
            raise HTTPException(422, str(e))
        source_url, sha, kind, content = str(data.github_url), pinned["sha"], "github", pinned["url"]
    else:
        content = (data.code or "").strip()
        source_url, sha, kind = "internal://code", hashlib.sha256(content.encode()).hexdigest(), "inline_code"
    submission = Submission(task_id=task.id, github_url=source_url, commit_sha=sha, summary=data.summary, challenges=data.challenges)
    db.add(submission)
    db.flush()
    db.add(SubmissionArtifact(submission_id=submission.id, kind=kind, language=data.language, content=content))
    db.execute(delete(Evaluation).where(Evaluation.task_id == task.id))
    task.status = TaskStatus.under_review
    db.commit()
    evaluations = evaluate_task(db, task)
    decision = next((item for item in evaluations[0].evidence if item.get("type") == "decision"), {"outcome": "improve"})
    return {"submission_id": submission.id, "commit_sha": sha, "status": task.status, "outcome": decision["outcome"]}

@router.post("/tasks/{task_id}/complete-discussion")
def complete_discussion(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = owned_task(db, task_id, user)
    agents = set(db.scalars(select(Evaluation.agent).where(Evaluation.task_id == task.id)))
    if agents != {"senior"}:
        raise HTTPException(409, "لم تكتمل مراجعة Senior")
    submission = db.scalar(select(Submission).where(Submission.task_id == task.id).order_by(Submission.created_at.desc()))
    if not submission:
        raise HTTPException(409, "لا يوجد تسليم مثبت")
    evaluation = db.scalar(select(Evaluation).where(Evaluation.task_id == task.id, Evaluation.agent == "senior"))
    decision = next((item.get("outcome") for item in (evaluation.evidence or []) if item.get("type") == "decision"), "improve") if evaluation else "improve"
    discussed = set(db.scalars(select(Message.agent).where(Message.task_id == task.id, Message.sender == "user", Message.created_at >= submission.created_at, Message.agent == "senior")))
    if decision == "improve" and "senior" not in discussed:
        raise HTTPException(409, "ناقش مراجعة التسليم مع Senior قبل إغلاق المهمة")
    task.status = TaskStatus.reviewed
    db.commit()
    cycle = db.get(WorkCycle, task.cycle_id)
    completed = len(list(db.scalars(select(Task).where(Task.cycle_id == cycle.id, Task.status == TaskStatus.reviewed))))
    cycle_now = datetime.now(cycle.ends_at.tzinfo) if cycle.ends_at.tzinfo else datetime.now()
    if completed >= 5 or cycle.ends_at <= cycle_now:
        report = weekly_report(db, cycle)
        return {"status": task.status, "next_task_id": None, "weekly_report": report.report}
    next_task = create_cycle_and_task(db, user.id, task.organization_id)
    return {"status": task.status, "next_task_id": next_task.id, "completed_this_week": completed}

@router.get("/tasks/{task_id}/evaluations")
def evaluations(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_task(db, task_id, user)
    return [{"agent": e.agent, "scores": e.scores, "rationale": e.rationale, "evidence": e.evidence, "confidence": e.confidence} for e in db.scalars(select(Evaluation).where(Evaluation.task_id == task_id))]
