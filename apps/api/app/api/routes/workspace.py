from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import current_user
from app.models.domain import CareerProfile, Evaluation, Message, Task, TaskStatus, User, WeeklyReport, WorkCycle
from app.services.orchestrator import create_cycle_and_task, weekly_report

router = APIRouter()

@router.post("/project/join")
def join_project(user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id))
    if not profile or not profile.confirmed:
        raise HTTPException(409, "أكمل ملفك وتحديد المستوى أولًا")
    path = dict(profile.career_path or {})
    project = dict(path.get("project", {}))
    project.update({"status": "kickoff", "name": "Junior Web Workspace", "tasks_per_week": 5})
    path["project"] = project
    profile.career_path = path
    overview = """مرحبًا بك كـJunior Web Developer في مشروع Junior Web Workspace. هدف المشروع بناء تطبيق Web صغير ومنظم يعمل من الواجهة حتى قاعدة البيانات. البنية المتوقعة: Frontend واضح، Backend API، وقاعدة بيانات محلية آمنة. أسبوعك يتكون من خمس مهام صغيرة متتابعة؛ لا تظهر مهمة جديدة قبل مراجعة السابقة. Senior هو مشرفك المباشر طوال التنفيذ، ويقدم تلميحات ومراجعات دون تنفيذ الحل عنك. بعد المهمة الخامسة يرفع Senior تقريرًا تقنيًا إلى Manager، ثم يرسل Manager تقييمه إلى HR للتقييم السلوكي وتحديث مستواك. النتيجة المتوقعة: مشروع يعمل، كود منظم، اختبارات أساسية، أسرار محمية، وسجل أداء موثق."""
    db.add(Message(user_id=user.id, agent="manager", sender="agent", body=overview, kind="project_kickoff"))
    db.commit()
    return {"status": "kickoff", "overview": overview}

@router.post("/project/start")
def start_project(user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id))
    project = dict((profile.career_path or {}).get("project", {})) if profile else {}
    if project.get("status") != "kickoff":
        raise HTTPException(409, "انضم للمشروع واقرأ اجتماع التعريف أولًا")
    kickoff = db.scalar(select(Message).where(Message.user_id == user.id, Message.kind == "project_kickoff").order_by(Message.created_at.desc()))
    if kickoff:
        legacy_tasks = list(db.scalars(select(Task).where(Task.user_id == user.id, Task.status != TaskStatus.reviewed, Task.created_at < kickoff.created_at)))
        for legacy_task in legacy_tasks:
            legacy_task.status = TaskStatus.reviewed
            legacy_cycle = db.get(WorkCycle, legacy_task.cycle_id)
            if legacy_cycle:
                legacy_cycle.report_generated = True
    project["status"] = "active"
    path = dict(profile.career_path)
    path["project"] = project
    profile.career_path = path
    db.commit()
    task = create_cycle_and_task(db, user.id)
    return {"status": "active", "task_id": task.id}

@router.post("/project/next-week")
def start_next_week(user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id))
    project = dict((profile.career_path or {}).get("project", {})) if profile else {}
    if project.get("status") != "week_complete":
        raise HTTPException(409, "لم يكتمل تقرير الأسبوع الحالي")
    project["status"] = "active"
    path = dict(profile.career_path)
    path["project"] = project
    profile.career_path = path
    db.commit()
    task = create_cycle_and_task(db, user.id)
    return {"status": "active", "task_id": task.id}

@router.get("/workspace")
def workspace(user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id))
    tasks = list(db.scalars(select(Task).where(Task.user_id == user.id).order_by(Task.created_at.desc())))
    unread = list(db.scalars(select(Message).where(Message.user_id == user.id, Message.kind == "task_alert").order_by(Message.created_at.desc())))
    active_task = next((task for task in tasks if task.status != TaskStatus.reviewed), tasks[0] if tasks else None)
    evals = list(db.scalars(select(Evaluation).where(Evaluation.task_id == active_task.id))) if active_task else []
    cycle = db.get(WorkCycle, active_task.cycle_id) if active_task else None
    latest_report = db.scalar(select(WeeklyReport).where(WeeklyReport.user_id == user.id).order_by(WeeklyReport.created_at.desc()))
    kickoff = db.scalar(select(Message).where(Message.user_id == user.id, Message.kind == "project_kickoff").order_by(Message.created_at.desc()))
    completed_this_week = len([task for task in tasks if cycle and task.cycle_id == cycle.id and task.status == TaskStatus.reviewed])
    payload = {
        "profile": profile.extracted if profile else None,
        "career_path": profile.career_path if profile else None,
        "tasks": [{"id": t.id, "title": t.title, "brief": t.brief, "status": t.status, "criteria": t.acceptance_criteria, "difficulty": t.difficulty} for t in tasks],
        "agents": [
            {"id": "manager", "name": "Manager", "status": "لديه تحديث" if unread else "متاح"},
            {"id": "senior", "name": "Senior", "status": "متاح للمساعدة"},
            {"id": "hr", "name": "HR", "status": "يراقب التقدم"},
        ],
        "notifications": [{"id": m.id, "body": m.body, "created_at": m.created_at} for m in unread[:5]],
    }
    payload.update({
        "evaluations": [{"agent": item.agent, "scores": item.scores, "rationale": item.rationale, "confidence": item.confidence, "evidence": item.evidence} for item in evals],
        "cycle": {"starts_at": cycle.starts_at, "ends_at": cycle.ends_at} if cycle else None,
        "path_revisions": profile.revisions if profile else [],
        "project_status": ((profile.career_path or {}).get("project", {}).get("status", "ready") if profile else "ready"),
        "project_overview": kickoff.body if kickoff else None,
        "completed_this_week": completed_this_week,
        "performance_score": int((profile.career_path or {}).get("performance_score", 50)) if profile else 50,
        "weekly_report": latest_report.report if latest_report else None,
    })
    return payload

@router.post("/reports/run-due")
def run_reports(user: User = Depends(current_user), db: Session = Depends(get_db)):
    cycles = list(db.scalars(select(WorkCycle).where(WorkCycle.user_id == user.id, WorkCycle.report_generated == False, WorkCycle.ends_at <= datetime.now(timezone.utc))))
    return [weekly_report(db, c).report for c in cycles]

@router.get("/reports")
def reports(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [r.report for r in db.scalars(select(WeeklyReport).where(WeeklyReport.user_id == user.id).order_by(WeeklyReport.created_at.desc()))]
