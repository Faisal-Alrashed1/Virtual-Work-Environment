import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.db import get_db
from app.core.security import current_user, hash_password, token, verify_password
from app.models.domain import AssessmentCampaign, CareerProfile, Evaluation, HiringDecision, KnowledgeDocument, Message, Organization, RecruiterIntervention, Submission, Task, TaskStatus, User, UserRole, WeeklyReport, WorkCycle
from app.schemas.api import CampaignIn, CampaignTaskIn, ChatIn, DecisionIn, InterventionIn, KnowledgeIn, LearningGoalIn, Login, OrganizationIn, ProfileConfirm, Register, StatusIn, SubmissionIn
from app.services.ai import ai
from app.services.documents import ALLOWED, extract_text, safe_save
from app.services.github import pin_repository
from app.services.orchestrator import create_cycle_and_task, evaluate_task, shared_agent_context, sync_agents, weekly_report

router = APIRouter(prefix="/api")

DIAGNOSTIC_QUESTIONS = [
    "هل تعرف أساسيات البرمجة مثل المتغيرات والشروط والدوال؟",
    "هل سبق أن كتبت برنامجًا بسيطًا بلغة Python بنفسك؟",
    "هل تعرف أساسيات الواجهة الأمامية مثل HTML وCSS وJavaScript؟",
    "هل تعرف ما هو الـBackend أو سبق أن بنيت API؟",
    "هل تعاملت مع قاعدة بيانات أو كتبت أوامر SQL؟",
    "هل استخدمت Git وGitHub لحفظ مشروع ورفع التعديلات؟",
    "هل تستطيع تتبع خطأ في الكود وكتابة اختبار بسيط؟",
    "هل سبق أن ربطت تطبيقًا بنموذج ذكاء اصطناعي عبر API؟",
    "هل تعرف فكرة AI Agents واستخدام الأدوات أو RAG؟",
    "هل تعرف أساسيات حماية المفاتيح وتشغيل التطبيق أو نشره؟",
]


def _diagnostic_state(profile: CareerProfile) -> dict:
    try:
        state = json.loads(profile.diagnostic_summary or "{}")
    except (json.JSONDecodeError, TypeError):
        state = {}
    answers = state.get("answers", [])
    state["answers"] = answers if isinstance(answers, list) else []
    return state


def _answer_score(answer: str) -> int:
    normalized = answer.strip().lower()
    negative = ("لا", "ما أعرف", "ماعندي", "لم أجرب", "من الصفر", "0")
    positive = ("نعم", "اعرف", "أعرف", "جربت", "سبق", "عندي", "1")
    if normalized == "0" or any(token in normalized for token in negative): return 0
    if normalized == "1" or any(token in normalized for token in positive): return 1
    return 0


def owned_task(db: Session, task_id: str, user: User) -> Task:
    task = db.get(Task, task_id)
    if not task or task.user_id != user.id: raise HTTPException(404, "المهمة غير موجودة")
    return task


@router.post("/auth/register")
def register(data: Register, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == data.email)): raise HTTPException(409, "البريد مستخدم")
    user = User(name=data.name, email=data.email, password_hash=hash_password(data.password), role=data.role)
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token": token(user), "user": {"id": user.id, "name": user.name, "role": user.role}}


@router.post("/auth/login")
def login(data: Login, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email))
    if not user or not verify_password(data.password, user.password_hash): raise HTTPException(401, "بيانات الدخول غير صحيحة")
    return {"access_token": token(user), "user": {"id": user.id, "name": user.name, "role": user.role}}


@router.get("/me")
def me(user: User = Depends(current_user)): return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}


@router.get("/intake/state")
def intake_state(user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id))
    if not profile: return {"profile_exists": False, "confirmed": False, "progress": 0, "total": 10, "messages": []}
    state = _diagnostic_state(profile); progress = min(len(state["answers"]), 10)
    rows = list(db.scalars(select(Message).where(Message.user_id == user.id, Message.agent == "career").order_by(Message.created_at.desc()).limit(30)))
    messages = [{"id": item.id, "sender": item.sender, "body": item.body} for item in reversed(rows) if item.kind in {"diagnostic_question", "diagnostic_answer", "diagnostic_result", "learning_goal"}]
    score = sum(int(item.get("score", 0)) for item in state["answers"][:10])
    return {"profile_exists": True, "confirmed": profile.confirmed, "progress": progress, "total": 10, "score": score if progress == 10 else None,
        "questions_complete": progress == 10, "open_goal": state.get("open_goal", ""), "messages": messages}


@router.post("/intake/cv")
async def upload_cv(file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    if file.content_type not in ALLOWED: raise HTTPException(415, "يدعم النظام PDF وDOCX فقط")
    data = await file.read()
    if len(data) > 8_000_000: raise HTTPException(413, "حجم الملف يتجاوز 8MB")
    try: text = extract_text(data, file.content_type or "")
    except Exception: raise HTTPException(422, "تعذر قراءة السيرة الذاتية")
    if len(text.strip()) < 80: raise HTTPException(422, "لا يوجد نص كافٍ في السيرة الذاتية")
    fallback = {"skills": [x for x in ["React", "Python", "FastAPI", "Git"] if x.lower() in text.lower()] or ["Web Development"], "projects": [], "experience_level": "junior", "strengths": ["التعلم العملي"], "gaps": ["اختبار الأنظمة", "تكاملات AI الآمنة"]}
    parsed = ai.structured("استخرج ملف مهني JSON من السيرة التالية: " + text[:12000], fallback)
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id)) or CareerProfile(user_id=user.id)
    profile.cv_path = safe_save(settings.upload_dir, user.id, file.filename or "cv", data); profile.extracted = parsed
    profile.diagnostic_summary = json.dumps({"answers": []}, ensure_ascii=False); profile.confirmed = False
    db.add(profile); db.commit(); db.refresh(profile)
    opening = f"سنحدد نقطة البداية بعشرة أسئلة قصيرة. لا توجد إجابة سيئة، ويمكن أن تبدأ من الصفر. السؤال 1 من 10: {DIAGNOSTIC_QUESTIONS[0]} أجب بنعم أو لا، ويمكنك إضافة توضيح قصير."
    db.add(Message(user_id=user.id, agent="career", sender="agent", body=opening, kind="diagnostic_question")); db.commit()
    return {"profile": parsed, "assistant": opening, "confirmed": False, "progress": 0, "total": 10}


@router.post("/intake/chat")
def intake_chat(data: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id))
    if not profile: raise HTTPException(409, "ارفع السيرة الذاتية أولًا")
    state = _diagnostic_state(profile)
    index = len(state["answers"])
    if index >= len(DIAGNOSTIC_QUESTIONS):
        score = sum(item["score"] for item in state["answers"])
        return {"reply": f"اكتمل التشخيص. نتيجتك {score} من 10. اكتب الآن بصراحة ما الذي تريد تعلمه وما الذي تشعر أنه ينقصك عن سوق العمل.", "ready": bool(state.get("open_goal")), "questions_complete": True, "progress": 10, "total": 10, "score": score}
    point = _answer_score(data.body)
    state["answers"].append({"question": DIAGNOSTIC_QUESTIONS[index], "answer": data.body, "score": point})
    profile.diagnostic_summary = json.dumps(state, ensure_ascii=False)
    db.add(Message(user_id=user.id, agent="career", sender="user", body=data.body, kind="diagnostic_answer"))
    progress = len(state["answers"]); score = sum(item["score"] for item in state["answers"])
    if progress < len(DIAGNOSTIC_QUESTIONS):
        answer = f"تم. السؤال {progress + 1} من 10: {DIAGNOSTIC_QUESTIONS[progress]} أجب بنعم أو لا."
        ready = False
    else:
        level = "مبتدئ من الصفر" if score <= 2 else "مبتدئ" if score <= 4 else "متوسط" if score <= 7 else "متقدم"
        answer = f"اكتملت الأسئلة. نتيجتك {score} من 10، ونقطة البداية المناسبة: {level}. الآن اكتب بصراحة وبأسلوبك: ماذا تريد أن تتعلم؟ وما الذي تشعر أنه ينقصك عن سوق العمل؟ هذه الإجابة ستكون محور المسار."
        ready = False
    db.add(Message(user_id=user.id, agent="career", sender="agent", body=answer, kind="diagnostic_result" if progress == 10 else "diagnostic_question")); db.commit()
    return {"reply": answer, "ready": ready, "questions_complete": progress == 10, "progress": progress, "total": 10, "score": score if progress == 10 else None}


@router.post("/intake/goal")
def save_learning_goal(data: LearningGoalIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id))
    if not profile: raise HTTPException(409, "ارفع السيرة الذاتية أولًا")
    state = _diagnostic_state(profile)
    if len(state["answers"]) < 10: raise HTTPException(409, "أكمل أسئلة تحديد المستوى أولًا")
    state["open_goal"] = data.goal.strip()
    profile.diagnostic_summary = json.dumps(state, ensure_ascii=False)
    db.add(Message(user_id=user.id, agent="career", sender="user", body=data.goal.strip(), kind="learning_goal")); db.commit()
    return {"saved": True, "message": "تم حفظ هدفك وسيكون محور المسار والمهام."}


@router.post("/intake/confirm")
def confirm_profile(data: ProfileConfirm, user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id))
    if not profile: raise HTTPException(409, "ارفع السيرة الذاتية أولًا")
    state = _diagnostic_state(profile)
    if len(state["answers"]) < 10: raise HTTPException(409, f"أكمل الأسئلة العشرة أولًا ({len(state['answers'])}/10)")
    open_goal = state.get("open_goal", "").strip()
    if len(open_goal) < 10: raise HTTPException(409, "اكتب ما تريد تعلمه وما ينقصك عن سوق العمل أولًا")
    score = sum(item["score"] for item in state["answers"]); difficulty = min(5, score // 2 + 1)
    gaps = [item["question"] for item in state["answers"] if item["score"] == 0]
    fallback_path = {"goal": "AI Agent Engineer", "focus": open_goal, "assessment": {"score": score, "out_of": 10, "starting_difficulty": difficulty, "gaps": gaps}, "stages": [{"name": "تثبيت الأساس المطلوب", "status": "current", "skills": ["Python", "Git", "Web basics"]}, {"name": "تطبيقات الذكاء الاصطناعي", "status": "next", "skills": ["APIs", "Prompting", "Testing"]}, {"name": "هندسة AI Agents", "status": "future", "skills": ["Tools", "RAG", "Security", "Observability"]}]}
    path_prompt = f"ابنِ مسار AI Agent Engineer من ثلاث مراحل فقط. اربط السيرة بالتقييم ولا تفترض إتقان مهارة لمجرد وجودها في السيرة. أعد JSON بنفس بنية المثال. السيرة المستخرجة: {profile.extracted}. نتيجة الأسئلة: {score}/10. الفجوات: {gaps}. ما يريد المستخدم تعلمه وما يراه ناقصًا: {open_goal}. المثال: {fallback_path}"
    career_path = ai.structured(path_prompt, fallback_path)
    career_path["assessment"] = fallback_path["assessment"]; career_path["focus"] = open_goal
    profile.confirmed = True
    profile.career_path = career_path
    db.commit(); task = create_cycle_and_task(db, user.id)
    return {"career_path": profile.career_path, "task_id": task.id}


@router.get("/workspace")
def workspace(user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id))
    tasks = list(db.scalars(select(Task).where(Task.user_id == user.id).order_by(Task.created_at.desc())))
    unread = list(db.scalars(select(Message).where(Message.user_id == user.id, Message.kind == "task_alert").order_by(Message.created_at.desc())))
    active_task = next((task for task in tasks if task.status != TaskStatus.reviewed), tasks[0] if tasks else None)
    evals = list(db.scalars(select(Evaluation).where(Evaluation.task_id == active_task.id))) if active_task else []
    cycle = db.get(WorkCycle, active_task.cycle_id) if active_task else None
    payload = {"profile": profile.extracted if profile else None, "career_path": profile.career_path if profile else None,
        "tasks": [{"id": t.id, "title": t.title, "brief": t.brief, "status": t.status, "criteria": t.acceptance_criteria, "difficulty": t.difficulty} for t in tasks],
        "agents": [{"id": "manager", "name": "Manager", "status": "لديه تحديث" if unread else "متاح"}, {"id": "mentor", "name": "Mentor", "status": "متاح للمساعدة"}, {"id": "hr", "name": "HR", "status": "يراقب التقدم"}], "notifications": [{"id": m.id, "body": m.body, "created_at": m.created_at} for m in unread[:5]]}
    payload.update({"evaluations": [{"agent": item.agent, "scores": item.scores, "rationale": item.rationale, "confidence": item.confidence} for item in evals],
        "cycle": {"starts_at": cycle.starts_at, "ends_at": cycle.ends_at} if cycle else None, "path_revisions": profile.revisions if profile else []})
    return payload


@router.get("/agents/{agent}/messages")
def messages(agent: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if agent not in {"manager", "mentor", "hr"}: raise HTTPException(404, "الوكيل غير موجود")
    rows = db.scalars(select(Message).where(Message.user_id == user.id, Message.agent == agent).order_by(Message.created_at))
    return [{"id": m.id, "sender": m.sender, "body": m.body, "kind": m.kind, "created_at": m.created_at} for m in rows]


@router.post("/agents/{agent}/messages")
def send_message(agent: str, data: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if agent not in {"manager", "mentor", "hr"}: raise HTTPException(404, "الوكيل غير موجود")
    db.add(Message(user_id=user.id, task_id=data.task_id, agent=agent, sender="user", body=data.body))
    db.flush()
    context = shared_agent_context(db, user.id, agent, data.task_id)
    reply = ai.chat(agent, data.body, context)
    db.add(Message(user_id=user.id, task_id=data.task_id, agent=agent, sender="agent", body=reply))
    sync_agents(db, user.id, agent, data.task_id, data.body)
    db.commit()
    return {"reply": reply}


@router.patch("/tasks/{task_id}/status")
def change_status(task_id: str, data: StatusIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = owned_task(db, task_id, user)
    allowed = {TaskStatus.todo: {TaskStatus.in_progress}, TaskStatus.in_progress: {TaskStatus.submitted}}
    if data.status not in allowed.get(task.status, set()): raise HTTPException(409, "انتقال حالة غير مسموح")
    task.status = data.status
    if data.status == TaskStatus.in_progress:
        db.add(Message(user_id=user.id, task_id=task.id, agent="manager", sender="agent", kind="status_update", body="بدأت المهمة. قبل التنفيذ تأكد أنك تستطيع شرح المطلوب ومعايير النجاح، واسألني عن أي غموض في النطاق."))
        db.add(Message(user_id=user.id, task_id=task.id, agent="mentor", sender="system", kind="agent_sync", body="بدأ المستخدم تنفيذ المهمة. قدّم تلميحات متدرجة وسجّل نوع المساعدة دون تنفيذ الحل عنه."))
        db.add(Message(user_id=user.id, task_id=task.id, agent="hr", sender="system", kind="agent_sync", body="بدأ المستخدم المهمة. راقب الاستمرارية والتواصل والاستجابة للملاحظات."))
    db.commit(); return {"status": task.status}


@router.post("/tasks/{task_id}/submit")
def submit(task_id: str, data: SubmissionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = owned_task(db, task_id, user)
    if task.status not in {TaskStatus.in_progress, TaskStatus.todo}: raise HTTPException(409, "المهمة ليست جاهزة للتسليم")
    try: pinned = pin_repository(str(data.github_url))
    except ValueError as e: raise HTTPException(422, str(e))
    submission = Submission(task_id=task.id, github_url=str(data.github_url), commit_sha=pinned["sha"], summary=data.summary, challenges=data.challenges)
    task.status = TaskStatus.under_review; db.add(submission); db.commit(); evaluate_task(db, task)
    return {"submission_id": submission.id, "commit_sha": pinned["sha"], "status": task.status}


@router.post("/tasks/{task_id}/complete-discussion")
def complete_discussion(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = owned_task(db, task_id, user)
    agents = set(db.scalars(select(Evaluation.agent).where(Evaluation.task_id == task.id)))
    if agents != {"manager", "mentor", "hr"}: raise HTTPException(409, "لم تكتمل التقييمات")
    submission = db.scalar(select(Submission).where(Submission.task_id == task.id).order_by(Submission.created_at.desc()))
    if not submission: raise HTTPException(409, "لا يوجد تسليم مثبت")
    discussed = set(db.scalars(select(Message.agent).where(Message.task_id == task.id, Message.sender == "user", Message.created_at >= submission.created_at, Message.agent.in_(["manager", "mentor"]))))
    missing = {"manager", "mentor"} - discussed
    if missing: raise HTTPException(409, "ناقش التسليم مع المدير والمرشد قبل إغلاق المهمة")
    task.status = TaskStatus.reviewed; db.commit()
    next_task = create_cycle_and_task(db, user.id, task.organization_id)
    return {"status": task.status, "next_task_id": next_task.id}


@router.get("/tasks/{task_id}/evaluations")
def evaluations(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_task(db, task_id, user)
    return [{"agent": e.agent, "scores": e.scores, "rationale": e.rationale, "evidence": e.evidence, "confidence": e.confidence} for e in db.scalars(select(Evaluation).where(Evaluation.task_id == task_id))]


@router.post("/reports/run-due")
def run_reports(user: User = Depends(current_user), db: Session = Depends(get_db)):
    cycles = list(db.scalars(select(WorkCycle).where(WorkCycle.user_id == user.id, WorkCycle.report_generated == False, WorkCycle.ends_at <= datetime.now(timezone.utc))))
    return [weekly_report(db, c).report for c in cycles]


@router.get("/reports")
def reports(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [r.report for r in db.scalars(select(WeeklyReport).where(WeeklyReport.user_id == user.id).order_by(WeeklyReport.created_at.desc()))]


@router.post("/organizations")
def create_org(data: OrganizationIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != UserRole.recruiter: raise HTTPException(403, "هذه العملية لمسؤول التوظيف")
    org = Organization(name=data.name, owner_id=user.id); db.add(org); db.commit(); db.refresh(org); return org


@router.post("/organizations/{org_id}/knowledge")
def add_knowledge(org_id: str, data: KnowledgeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    org = db.get(Organization, org_id)
    if not org or org.owner_id != user.id: raise HTTPException(404, "الشركة غير موجودة")
    if not data.attested_synthetic: raise HTTPException(422, "يجب تأكيد أن البيانات وهمية أو منزوعة الهوية")
    doc = KnowledgeDocument(organization_id=org_id, name=data.name, content=data.content, attested_synthetic=True)
    db.add(doc); db.commit(); db.refresh(doc); return {"id": doc.id, "status": "indexed", "source": doc.name}


def recruiter_org(db: Session, org_id: str, user: User) -> Organization:
    org = db.get(Organization, org_id)
    if not org or org.owner_id != user.id: raise HTTPException(404, "الشركة غير موجودة")
    return org


@router.post("/campaigns")
def create_campaign(data: CampaignIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    recruiter_org(db, data.organization_id, user)
    campaign = AssessmentCampaign(organization_id=data.organization_id, title=data.title, job_role=data.job_role)
    db.add(campaign); db.commit(); db.refresh(campaign); return campaign


@router.post("/campaigns/{campaign_id}/tasks")
def draft_company_task(campaign_id: str, data: CampaignTaskIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    campaign = db.get(AssessmentCampaign, campaign_id)
    if not campaign: raise HTTPException(404, "الحملة غير موجودة")
    recruiter_org(db, campaign.organization_id, user)
    candidate = db.get(User, data.candidate_user_id)
    if not candidate: raise HTTPException(404, "المرشح غير موجود")
    active = db.scalar(select(Task).where(Task.user_id == candidate.id, Task.status != TaskStatus.reviewed))
    if active: raise HTTPException(409, "لدى المرشح مهمة نشطة")
    cycle = WorkCycle(user_id=candidate.id, organization_id=campaign.organization_id, ends_at=datetime.now(timezone.utc) + timedelta(days=7))
    db.add(cycle); db.flush()
    docs = list(db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.organization_id == campaign.organization_id).limit(3)))
    task = Task(user_id=candidate.id, organization_id=campaign.organization_id, cycle_id=cycle.id, title=data.title, brief=data.brief,
        acceptance_criteria=data.acceptance_criteria, difficulty=data.difficulty, status=TaskStatus.pending_approval,
        source_evidence=[{"document_id": d.id, "name": d.name} for d in docs])
    db.add(task); db.commit(); db.refresh(task); return task


@router.post("/campaigns/{campaign_id}/tasks/{task_id}/approve")
def approve_company_task(campaign_id: str, task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    campaign = db.get(AssessmentCampaign, campaign_id); task = db.get(Task, task_id)
    if not campaign or not task or task.organization_id != campaign.organization_id: raise HTTPException(404, "المهمة غير موجودة")
    recruiter_org(db, campaign.organization_id, user)
    if task.status != TaskStatus.pending_approval: raise HTTPException(409, "المهمة ليست بانتظار الاعتماد")
    task.status = TaskStatus.todo
    db.add(Message(user_id=task.user_id, task_id=task.id, agent="manager", sender="agent", kind="task_alert", body=f"اعتمدت الشركة مهمتك الجديدة: {task.title}"))
    db.commit(); return {"status": task.status}


@router.post("/company/tasks/{task_id}/interventions")
def intervene(task_id: str, data: InterventionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task or not task.organization_id: raise HTTPException(404, "المهمة غير موجودة")
    recruiter_org(db, task.organization_id, user)
    if task.status not in {TaskStatus.submitted, TaskStatus.under_review, TaskStatus.discussion, TaskStatus.reviewed}: raise HTTPException(409, "لا يمكن التدخل قبل التسليم")
    item = RecruiterIntervention(task_id=task.id, recruiter_id=user.id, body=data.body)
    db.add(item); db.commit(); db.refresh(item); return item


@router.get("/company/tasks/{task_id}/report")
def candidate_task_report(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task or not task.organization_id: raise HTTPException(404, "المهمة غير موجودة")
    recruiter_org(db, task.organization_id, user)
    evals = list(db.scalars(select(Evaluation).where(Evaluation.task_id == task.id)))
    interventions = list(db.scalars(select(RecruiterIntervention).where(RecruiterIntervention.task_id == task.id)))
    return {"task": {"title": task.title, "status": task.status, "source_evidence": task.source_evidence},
        "agent_reports": [{"agent": e.agent, "scores": e.scores, "rationale": e.rationale, "evidence": e.evidence, "confidence": e.confidence} for e in evals],
        "recruiter_interventions": [{"body": i.body, "created_at": i.created_at} for i in interventions], "automated_hiring_decision": None}


@router.post("/campaigns/{campaign_id}/candidates/{candidate_id}/decision")
def record_decision(campaign_id: str, candidate_id: str, data: DecisionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    campaign = db.get(AssessmentCampaign, campaign_id)
    if not campaign: raise HTTPException(404, "الحملة غير موجودة")
    recruiter_org(db, campaign.organization_id, user)
    if data.decision not in {"advance", "hold", "reject"}: raise HTTPException(422, "قرار غير صالح")
    item = HiringDecision(campaign_id=campaign.id, candidate_id=candidate_id, recruiter_id=user.id, decision=data.decision, notes=data.notes)
    db.add(item); db.commit(); db.refresh(item); return item
