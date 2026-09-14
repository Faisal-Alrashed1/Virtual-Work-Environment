import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import recruiter_org
from app.core.db import get_db
from app.core.security import current_user
from app.models.domain import (
    AssessmentCampaign,
    CandidateInvitation,
    CareerProfile,
    Evaluation,
    HiringDecision,
    KnowledgeDocument,
    Message,
    Organization,
    RecruiterIntervention,
    Task,
    TaskStatus,
    User,
    UserRole,
    WeeklyReport,
    WorkCycle,
)
from app.schemas.api import CampaignIn, CampaignTaskIn, DecisionIn, InterventionIn, KnowledgeIn, OrganizationIn

router = APIRouter()


@router.post("/organizations")
def create_org(data: OrganizationIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != UserRole.recruiter:
        raise HTTPException(403, "هذه العملية لمسؤول التوظيف")
    org = Organization(name=data.name, owner_id=user.id)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.post("/organizations/{org_id}/knowledge")
def add_knowledge(org_id: str, data: KnowledgeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    org = db.get(Organization, org_id)
    if not org or org.owner_id != user.id:
        raise HTTPException(404, "الشركة غير موجودة")
    if not data.attested_synthetic:
        raise HTTPException(422, "يجب تأكيد أن البيانات وهمية أو منزوعة الهوية")
    doc = KnowledgeDocument(organization_id=org_id, name=data.name, content=data.content, attested_synthetic=True)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "status": "indexed", "source": doc.name}


@router.post("/organizations/{org_id}/invitations")
def create_invitation(org_id: str, candidate_email: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    recruiter_org(db, org_id, user)
    code = secrets.token_hex(6)
    inv = CandidateInvitation(organization_id=org_id, recruiter_id=user.id, code=code, candidate_email=candidate_email, status="sent")
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return {"id": inv.id, "code": code, "invite_url": f"/intake?invite={code}", "status": inv.status}


@router.get("/invitations/{code}")
def get_invitation(code: str, db: Session = Depends(get_db)):
    inv = db.scalar(select(CandidateInvitation).where(CandidateInvitation.code == code))
    if not inv:
        raise HTTPException(404, "رمز الدعوة غير صالح")
    org = db.get(Organization, inv.organization_id)
    return {"code": inv.code, "organization_name": org.name if org else "الشركة", "status": inv.status}


@router.post("/invitations/{code}/accept")
def accept_invitation(code: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    inv = db.scalar(select(CandidateInvitation).where(CandidateInvitation.code == code))
    if not inv:
        raise HTTPException(404, "رمز الدعوة غير صالح")
    inv.status = "accepted"
    user.role = UserRole.candidate
    org = db.get(Organization, inv.organization_id)
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id)) or CareerProfile(user_id=user.id)
    profile.confirmed = True
    profile.career_path = {
        "goal": f"مرشح وظيفي لدى {org.name if org else 'الشركة'}",
        "focus": "إنجاز مهام التقييم الخاصة ببيئة عمل الشركة",
        "project": {"status": "kickoff", "name": f"تقييم {org.name if org else 'الشركة'}", "tasks_per_week": 5},
    }
    db.add(profile)
    db.commit()
    return {"status": "accepted", "organization_id": inv.organization_id, "organization_name": org.name if org else ""}


@router.post("/campaigns")
def create_campaign(data: CampaignIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    recruiter_org(db, data.organization_id, user)
    campaign = AssessmentCampaign(organization_id=data.organization_id, title=data.title, job_role=data.job_role)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.post("/campaigns/{campaign_id}/tasks")
def draft_company_task(campaign_id: str, data: CampaignTaskIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    campaign = db.get(AssessmentCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "الحملة غير موجودة")
    recruiter_org(db, campaign.organization_id, user)
    candidate = db.get(User, data.candidate_user_id)
    if not candidate:
        raise HTTPException(404, "المرشح غير موجود")
    active = db.scalar(select(Task).where(Task.user_id == candidate.id, Task.status != TaskStatus.reviewed))
    if active:
        raise HTTPException(409, "لدى المرشح مهمة نشطة")
    cycle = WorkCycle(user_id=candidate.id, organization_id=campaign.organization_id, ends_at=datetime.now(timezone.utc) + timedelta(days=7))
    db.add(cycle)
    db.flush()
    docs = list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.organization_id == campaign.organization_id).limit(3)))
    task = Task(
        user_id=candidate.id,
        organization_id=campaign.organization_id,
        cycle_id=cycle.id,
        title=data.title,
        brief=data.brief,
        acceptance_criteria=data.acceptance_criteria,
        difficulty=data.difficulty,
        status=TaskStatus.pending_approval,
        source_evidence=[{"document_id": d.id, "name": d.name} for d in docs],
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.post("/campaigns/{campaign_id}/tasks/{task_id}/approve")
def approve_company_task(campaign_id: str, task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    campaign = db.get(AssessmentCampaign, campaign_id)
    task = db.get(Task, task_id)
    if not campaign or not task or task.organization_id != campaign.organization_id:
        raise HTTPException(404, "المهمة غير موجودة")
    recruiter_org(db, campaign.organization_id, user)
    if task.status != TaskStatus.pending_approval:
        raise HTTPException(409, "المهمة ليست بانتظار الاعتماد")
    task.status = TaskStatus.todo
    db.add(Message(user_id=task.user_id, task_id=task.id, agent="manager", sender="agent", kind="task_alert", body=f"اعتمدت الشركة مهمتك الجديدة: {task.title}"))
    db.commit()
    return {"status": task.status}


@router.post("/company/tasks/{task_id}/interventions")
def intervene(task_id: str, data: InterventionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task or not task.organization_id:
        raise HTTPException(404, "المهمة غير موجودة")
    recruiter_org(db, task.organization_id, user)
    if task.status not in {TaskStatus.submitted, TaskStatus.under_review, TaskStatus.discussion, TaskStatus.reviewed}:
        raise HTTPException(409, "لا يمكن التدخل قبل التسليم")
    item = RecruiterIntervention(task_id=task.id, recruiter_id=user.id, body=data.body)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/company/candidates/{candidate_id}/evaluation-dashboard")
def evaluation_dashboard(candidate_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    candidate = db.get(User, candidate_id)
    if not candidate:
        raise HTTPException(404, "المرشح غير موجود")
    tasks = list(db.scalars(select(Task).where(Task.user_id == candidate.id).order_by(Task.created_at.desc())))
    reports = list(db.scalars(select(WeeklyReport).where(WeeklyReport.user_id == candidate.id).order_by(WeeklyReport.created_at.desc())))
    decisions = list(db.scalars(select(HiringDecision).where(HiringDecision.candidate_id == candidate.id).order_by(HiringDecision.created_at.desc())))
    latest_report = reports[0].report if reports else {}
    return {
        "candidate": {"id": candidate.id, "name": candidate.name, "email": candidate.email},
        "tasks_summary": {"total": len(tasks), "reviewed": len([t for t in tasks if t.status == TaskStatus.reviewed])},
        "performance_score": latest_report.get("performance_score", 50),
        "technical_grade": latest_report.get("manager_evaluation", {}).get("technical_score", 3),
        "behavioral_grade": latest_report.get("hr_evaluation", {}).get("behavior_score", 3),
        "strengths": ["الالتزام بالمواعيد اليومية", "كتابة كود ببنئية واضحة", "التفاعل مع توجيهات Senior"],
        "weaknesses": ["يحتاج تعميق اختبارات الأمان والـ Boundary cases"],
        "decisions_history": [{"decision": d.decision, "notes": d.notes, "created_at": d.created_at} for d in decisions],
    }


@router.post("/campaigns/{campaign_id}/candidates/{candidate_id}/decision")
def record_decision(campaign_id: str, candidate_id: str, data: DecisionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    campaign = db.get(AssessmentCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "الحملة غير موجودة")
    recruiter_org(db, campaign.organization_id, user)
    if data.decision not in {"advance", "hold", "reject"}:
        raise HTTPException(422, "قرار غير صالح")
    item = HiringDecision(campaign_id=campaign.id, candidate_id=candidate_id, recruiter_id=user.id, decision=data.decision, notes=data.notes)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
