from datetime import datetime, timedelta, timezone
import json
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.domain import CareerProfile, Evaluation, Message, Submission, Task, TaskStatus, WeeklyReport, WorkCycle
from app.services.ai import ai


def _skill_names(extracted: dict | None) -> list[str]:
    """Normalize the different valid shapes an AI may return for skills."""
    raw = (extracted or {}).get("skills", [])
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item.get("name", item)) if isinstance(item, dict) else str(item) for item in raw]
    if isinstance(raw, dict):
        names: list[str] = []
        for category, values in raw.items():
            if isinstance(values, list):
                names.extend(str(item.get("name", item)) if isinstance(item, dict) else str(item) for item in values)
            elif isinstance(values, str):
                names.append(values)
            elif values:
                names.append(str(category))
        return names
    return []


def _starting_difficulty(profile: CareerProfile | None) -> int:
    if not profile: return 1
    assessment = (profile.career_path or {}).get("assessment", {})
    if isinstance(assessment.get("starting_difficulty"), int):
        return max(1, min(5, assessment["starting_difficulty"]))
    try:
        answers = json.loads(profile.diagnostic_summary or "{}").get("answers", [])
        score = sum(int(item.get("score", 0)) for item in answers)
        return max(1, min(5, score // 2 + 1))
    except (json.JSONDecodeError, TypeError, ValueError):
        return 1


def _task_for_level(level: int, skills: list[str]) -> dict:
    focus = ", ".join(skills[:3])
    tasks = {
        1: {"title": "تشغيل أول برنامج Python منظم", "brief": "أنشئ برنامج Python صغيرًا يستقبل اسم المستخدم ويعيد رسالة مرتبة. الهدف هو تعلم بنية المشروع والتشغيل خطوة بخطوة، ويمكنك طلب مساعدة المرشد في كل مرحلة.", "criteria": ["تشغيل البرنامج بنجاح", "استخدام دالة واحدة على الأقل", "كتابة README بسيط", "رفع المشروع إلى GitHub"]},
        2: {"title": "بناء API بسيطة ومنظمة", "brief": "ابنِ API صغيرة تستقبل نصًا وتعيد نتيجة JSON واضحة، مع معالجة الإدخال غير الصحيح.", "criteria": ["مسار API يعمل", "التحقق من المدخلات", "معالجة خطأ واحد على الأقل", "توثيق طريقة التشغيل"]},
        3: {"title": "بناء مساعد ذكي آمن", "brief": f"ابنِ ميزة تستدعي نموذج AI وتعرض النتيجة بأمان، مستفيدًا من خبرتك في {focus}.", "criteria": ["فصل مفتاح API عن الكود", "معالجة الانتظار والفشل", "التحقق من مخرجات النموذج", "اختبار المسار الأساسي"]},
        4: {"title": "بناء AI Agent يستخدم أداة", "brief": "ابنِ وكيلًا ذكيًا يقرر متى يستدعي أداة واحدة، ثم يعيد نتيجة موثقة وقابلة للتحقق.", "criteria": ["تعريف أداة بمدخلات واضحة", "قرار استدعاء مضبوط", "منع التعليمات غير الموثوقة", "اختبارات نجاح وفشل"]},
        5: {"title": "تصميم AI Agent موثوق متعدد الخطوات", "brief": "صمم وكيلًا متعدد الخطوات مع أداة وذاكرة محدودة وسجل أدلة، ووضح قرارات الاعتمادية والأمان.", "criteria": ["حالات وأدوات واضحة", "حماية من prompt injection", "اختبارات وحدات وتكامل", "سجل تنفيذ ومراقبة أخطاء"]},
    }
    return tasks[level]


def _adaptive_difficulty(db: Session, user_id: str, profile: CareerProfile | None) -> tuple[int, str]:
    baseline = _starting_difficulty(profile)
    previous = db.scalar(select(Task).where(Task.user_id == user_id, Task.status == TaskStatus.reviewed).order_by(Task.created_at.desc()))
    if not previous: return baseline, "درجة التشخيص الأولي"
    evaluations = list(db.scalars(select(Evaluation).where(Evaluation.task_id == previous.id)))
    values = [float(score) for item in evaluations for score in (item.scores or {}).values() if isinstance(score, (int, float))]
    average = sum(values) / len(values) if values else 3
    if average >= 4: return min(5, previous.difficulty + 1), f"رفع الصعوبة بعد أداء {average:.1f}/5"
    if average < 2.5: return max(1, previous.difficulty - 1), f"خفض الصعوبة لدعم التعلم بعد أداء {average:.1f}/5"
    return previous.difficulty, f"تثبيت الصعوبة بعد أداء {average:.1f}/5"


def shared_agent_context(db: Session, user_id: str, active_agent: str, task_id: str | None = None) -> str:
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user_id))
    task = db.get(Task, task_id) if task_id else db.scalar(select(Task).where(Task.user_id == user_id, Task.status != TaskStatus.reviewed).order_by(Task.created_at.desc()))
    events = list(db.scalars(select(Message).where(Message.user_id == user_id).order_by(Message.created_at.desc()).limit(24)))
    transcript = "\n".join(f"{item.agent}/{item.sender}: {item.body}" for item in reversed(events))
    role_limits = {
        "manager": "استخدم ملخص مساعدة المرشد لفهم الاستقلالية، ولا تطلب من المرشد تنفيذ الحل.",
        "mentor": "استخدم متطلبات المدير وسياق المهمة، وقدّم تلميحات تدريجية دون تنفيذ المهمة بدل المستخدم.",
        "hr": "راقب نمط التواصل وطلبات المساعدة والتقدم، ولا تغيّر المتطلبات ولا تصدر حكمًا تقنيًا بلا دليل.",
    }
    return f"الملف والمسار: {profile.career_path if profile else {}}\nالمهمة الحالية: {task.title if task else 'لا توجد'} | {task.brief if task else ''} | الحالة: {task.status if task else ''}\nسجل الفريق المشترك:\n{transcript}\nحد الدور: {role_limits[active_agent]}"


def sync_agents(db: Session, user_id: str, source_agent: str, task_id: str | None, user_message: str) -> None:
    recipients = {"manager", "mentor", "hr"} - {source_agent}
    labels = {"manager": "المدير", "mentor": "المرشد", "hr": "الموارد البشرية"}
    summary = user_message.strip().replace("\n", " ")[:240]
    for recipient in recipients:
        body = f"تحديث مشترك من محادثة {labels[source_agent]}: ناقش المستخدم «{summary}». استخدم هذا كسياق ولا تعتبره تقييمًا نهائيًا."
        db.add(Message(user_id=user_id, task_id=task_id, agent=recipient, sender="system", body=body, kind="agent_sync"))


def create_cycle_and_task(db: Session, user_id: str, organization_id: str | None = None) -> Task:
    active = db.scalar(select(Task).where(Task.user_id == user_id, Task.status != TaskStatus.reviewed))
    if active: return active
    cycle = db.scalar(select(WorkCycle).where(WorkCycle.user_id == user_id, WorkCycle.ends_at > datetime.now(timezone.utc)).order_by(WorkCycle.ends_at.desc()))
    if not cycle:
        cycle = WorkCycle(user_id=user_id, organization_id=organization_id, ends_at=datetime.now(timezone.utc) + timedelta(days=7))
        db.add(cycle); db.flush()
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user_id))
    skills = _skill_names(profile.extracted if profile else None) or ["Python", "APIs", "AI Agents"]
    difficulty, difficulty_reason = _adaptive_difficulty(db, user_id, profile)
    fallback = _task_for_level(difficulty, skills)
    focus = (profile.career_path or {}).get("focus", "") if profile else ""
    gaps = (profile.career_path or {}).get("assessment", {}).get("gaps", []) if profile else []
    assignment = ai.structured(f"أنشئ مهمة عملية واحدة فقط لمتعلم AI Agents. المستوى {difficulty}/5. مهارات السيرة: {skills}. الفجوات المثبتة بالأسئلة: {gaps}. هدف المستخدم المفتوح: {focus}. لا تجعلها أصعب من المستوى. أعد JSON بالمفاتيح title وbrief وcriteria (قائمة من 4 عناصر). المثال الاحتياطي: {fallback}", fallback)
    if not isinstance(assignment.get("criteria"), list): assignment = fallback
    task = Task(user_id=user_id, organization_id=organization_id, cycle_id=cycle.id,
        title=assignment["title"], brief=assignment["brief"],
        acceptance_criteria=assignment["criteria"], difficulty=difficulty,
        status=TaskStatus.pending_approval if organization_id else TaskStatus.todo)
    db.add(task)
    if profile:
        revisions = list(profile.revisions or [])
        revisions.append({"at": datetime.now(timezone.utc).isoformat(), "difficulty": difficulty, "reason": difficulty_reason, "task": assignment["title"]})
        profile.revisions = revisions
    db.add(Message(user_id=user_id, task_id=task.id, agent="manager", sender="agent", kind="task_alert", body=f"أسندت لك المهمة الأولى بناءً على السيرة ونتيجة التشخيص وهدفك: {task.title}"))
    db.add(Message(user_id=user_id, task_id=task.id, agent="mentor", sender="system", kind="agent_sync", body=f"أحاطك المدير بالمهمة «{task.title}». ساعد المستخدم بتلميحات متدرجة دون تنفيذها عنه."))
    db.add(Message(user_id=user_id, task_id=task.id, agent="hr", sender="system", kind="agent_sync", body=f"بدأت دورة عمل جديدة بالمهمة «{task.title}» ومستوى صعوبة {difficulty}/5. راقب التواصل والتقدم وطلبات المساعدة."))
    db.commit(); db.refresh(task); return task


def evaluate_task(db: Session, task: Task) -> list[Evaluation]:
    submission = db.scalar(select(Submission).where(Submission.task_id == task.id).order_by(Submission.created_at.desc()))
    messages = list(db.scalars(select(Message).where(Message.task_id == task.id).order_by(Message.created_at)))
    transcript = "\n".join(f"{item.agent}/{item.sender}: {item.body}" for item in messages[-30:])
    fallback = {
        "manager": {"scores": {"فهم المتطلبات": 3, "التخطيط والالتزام": 3, "الاستقلالية": 3}, "rationale": "تقييم مبدئي يحتاج مناقشة التسليم لزيادة الثقة.", "confidence": 2},
        "mentor": {"scores": {"صحة الحل": 3, "جودة الكود": 3, "الأمان والاختبارات": 3}, "rationale": "تقييم مبدئي مبني على ملخص التسليم والـcommit المثبت.", "confidence": 2},
        "hr": {"scores": {"التواصل": 3, "المهنية": 3, "الاستجابة للملاحظات": 3}, "rationale": "تقييم مبدئي مبني على سجل التواصل المتاح.", "confidence": 2},
    }
    evidence = {"task": task.title, "criteria": task.acceptance_criteria, "commit_sha": submission.commit_sha if submission else None,
        "submission_summary": submission.summary if submission else "", "challenges": submission.challenges if submission else "", "conversation": transcript}
    assessed = ai.structured(f"قيّم هذا التسليم بثلاثة أدوار مستقلة: manager وmentor وhr. كل score عدد صحيح 1-5. المدير يقيم الفهم والتنفيذ والالتزام، المرشد يقيم صحة الحل وجودة الكود والأمان والاختبارات، وHR يقيم التواصل والمهنية والاستجابة. لا تخفِ اختلاف الآراء. أعد JSON بنفس بنية المثال: {fallback}. الأدلة: {evidence}", fallback)
    results = []
    for agent in ("manager", "mentor", "hr"):
        item = assessed.get(agent, fallback[agent]); raw_scores = item.get("scores", fallback[agent]["scores"])
        scores = {name: max(1, min(5, int(value))) for name, value in raw_scores.items() if isinstance(value, (int, float))}
        if not scores: scores = fallback[agent]["scores"]
        evaluation = Evaluation(task_id=task.id, agent=agent, scores=scores,
            rationale=str(item.get("rationale", fallback[agent]["rationale"])),
            evidence=[{"type": "commit", "sha": submission.commit_sha if submission else None}, {"type": "conversation", "message_ids": [message.id for message in messages[-10:]]}],
            confidence=max(1, min(5, int(item.get("confidence", 2)))))
        db.add(evaluation); results.append(evaluation)
    task.status = TaskStatus.discussion
    db.add(Message(user_id=task.user_id, task_id=task.id, agent="manager", sender="agent", kind="review_ready", body="اكتملت المراجعة الأولية. ناقشني الآن في فهم المتطلبات وقرارات التنفيذ."))
    db.add(Message(user_id=task.user_id, task_id=task.id, agent="mentor", sender="agent", kind="review_ready", body="راجعت أدلة التسليم والـcommit المثبت. ناقشني في بنية الحل والاختبارات والتحسينات."))
    db.add(Message(user_id=task.user_id, task_id=task.id, agent="hr", sender="agent", kind="review_ready", body="سجلت تقييم التواصل والمهنية. أكمل مناقشتي المدير والمرشد لإغلاق المهمة."))
    db.commit()
    return results


def weekly_report(db: Session, cycle: WorkCycle) -> WeeklyReport:
    tasks = list(db.scalars(select(Task).where(Task.cycle_id == cycle.id)))
    completed = [t for t in tasks if t.status == TaskStatus.reviewed]
    report = {"kind": "weekly" if completed else "activity", "completed_tasks": len(completed),
        "summary": "تقدم واضح خلال دورة العمل." if completed else "لم تكتمل مهمة هذا الأسبوع؛ يعرض التقرير النشاط والعوائق دون درجة تقنية.",
        "next_focus": ["تقليل الاعتماد على التلميحات", "توثيق قرارات التنفيذ"] if completed else ["تقسيم المهمة إلى خطوات أصغر"]}
    item = WeeklyReport(cycle_id=cycle.id, user_id=cycle.user_id, report=report)
    cycle.report_generated = True; db.add(item); db.commit(); db.refresh(item); return item
