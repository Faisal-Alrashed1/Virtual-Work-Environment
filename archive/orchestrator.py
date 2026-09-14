import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.domain import CareerProfile, Evaluation, Message, Submission, SubmissionArtifact, Task, TaskStatus, WeeklyReport, WorkCycle
from app.services.ai import ai


def _skill_names(extracted: dict | None) -> list[str]:
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
    if not profile:
        return 1
    assessment = (profile.career_path or {}).get("assessment", {})
    if isinstance(assessment.get("starting_difficulty"), int):
        return max(1, min(5, assessment["starting_difficulty"]))
    try:
        answers = json.loads(profile.diagnostic_summary or "{}").get("answers", [])
        score = sum(int(item.get("score", 0)) for item in answers)
        return max(1, min(5, score // 2 + 1))
    except (json.JSONDecodeError, TypeError, ValueError):
        return 1


def _task_for_day(day: int) -> dict:
    tasks = {
        1: {"title": "اليوم 1 · تهيئة المشروع", "brief": "أنشئ هيكل مشروع Web بسيط وصفحة بداية تعمل. لا تضف قاعدة البيانات أو ميزات إضافية الآن.", "criteria": ["فصل frontend عن backend", "صفحة بداية تعمل", "ملف README قصير", "لا توجد أسرار داخل الكود"]},
        2: {"title": "اليوم 2 · نموذج البيانات", "brief": "أضف نموذج بيانات صغيرًا للمستخدم واربطه بقاعدة بيانات محلية. نفّذ هذه القطعة فقط.", "criteria": ["نموذج واضح", "حفظ واسترجاع ناجح", "التحقق من المدخلات", "دالة مستقلة للوصول للبيانات"]},
        3: {"title": "اليوم 3 · API واحدة", "brief": "أنشئ API صغيرة تقرأ البيانات وتعيد JSON واضحًا، مع حالة نجاح وحالة خطأ.", "criteria": ["Endpoint واحد واضح", "استجابة JSON صحيحة", "معالجة خطأ", "تقسيم المنطق إلى دوال صغيرة"]},
        4: {"title": "اليوم 4 · ربط الواجهة", "brief": "اربط صفحة الواجهة بالـAPI واعرض البيانات مع حالات التحميل والخطأ والنجاح.", "criteria": ["اتصال فعلي بالـAPI", "حالة تحميل ظاهرة", "رسالة خطأ مفهومة", "واجهة بسيطة وواضحة"]},
        5: {"title": "اليوم 5 · الجودة والتسليم", "brief": "راجع المشروع الصغير، أضف اختبارًا أساسيًا، وحسّن الأمان والتوثيق دون إضافة ميزة جديدة.", "criteria": ["اختبار أساسي ناجح", "الأسرار خارج الكود", "تنظيم الملفات", "README يشرح التشغيل"]},
    }
    return tasks[max(1, min(5, day))]


def _adaptive_difficulty(db: Session, user_id: str, profile: CareerProfile | None) -> tuple[int, str]:
    baseline = _starting_difficulty(profile)
    previous = db.scalar(select(Task).where(Task.user_id == user_id, Task.status == TaskStatus.reviewed).order_by(Task.created_at.desc()))
    if not previous:
        return baseline, "درجة التشخيص الأولي"
    evaluations = list(db.scalars(select(Evaluation).where(Evaluation.task_id == previous.id)))
    values = [float(score) for item in evaluations for score in (item.scores or {}).values() if isinstance(score, (int, float))]
    average = sum(values) / len(values) if values else 3
    if average >= 4:
        return min(5, previous.difficulty + 1), f"رفع الصعوبة بعد أداء {average:.1f}/5"
    if average < 2.5:
        return max(1, previous.difficulty - 1), f"خفض الصعوبة لدعم التعلم بعد أداء {average:.1f}/5"
    return previous.difficulty, f"تثبيت الصعوبة بعد أداء {average:.1f}/5"


def shared_agent_context(db: Session, user_id: str, active_agent: str, task_id: str | None = None) -> str:
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user_id))
    task = db.get(Task, task_id) if task_id else db.scalar(select(Task).where(Task.user_id == user_id, Task.status != TaskStatus.reviewed).order_by(Task.created_at.desc()))
    events = list(db.scalars(select(Message).where(Message.user_id == user_id).order_by(Message.created_at.desc()).limit(24)))
    transcript = "\n".join(f"{item.agent}/{item.sender}: {item.body}" for item in reversed(events))
    role_limits = {
        "manager": "استخدم ملخص مساعدة المرشد لفهم الاستقلالية، ولا تطلب من المرشد تنفيذ الحل.",
        "senior": "أنت المشرف المباشر. استخدم متطلبات المشروع، وقسّم العمل، وقدّم تلميحات تدريجية دون تنفيذ المهمة بدل المستخدم.",
        "hr": "راقب نمط التواصل وطلبات المساعدة والتقدم، ولا تغيّر المتطلبات ولا تصدر حكمًا تقنيًا بلا دليل.",
    }
    return f"الملف والمسار: {profile.career_path if profile else {}}\nالمهمة الحالية: {task.title if task else 'لا توجد'} | {task.brief if task else ''} | الحالة: {task.status if task else ''}\nسجل الفريق المشترك:\n{transcript}\nحد الدور: {role_limits[active_agent]}"


def sync_agents(db: Session, user_id: str, source_agent: str, task_id: str | None, user_message: str) -> None:
    recipients = {"manager", "senior", "hr"} - {source_agent}
    labels = {"manager": "المدير", "senior": "المرشد", "hr": "الموارد البشرية"}
    summary = user_message.strip().replace("\n", " ")[:240]
    for recipient in recipients:
        body = f"تحديث مشترك من محادثة {labels[source_agent]}: ناقش المستخدم «{summary}». استخدم هذا كسياق ولا تعتبره تقييمًا نهائيًا."
        db.add(Message(user_id=user_id, task_id=task_id, agent=recipient, sender="system", body=body, kind="agent_sync"))


def create_cycle_and_task(db: Session, user_id: str, organization_id: str | None = None) -> Task:
    active = db.scalar(select(Task).where(Task.user_id == user_id, Task.status != TaskStatus.reviewed))
    if active:
        return active
    cycle = db.scalar(select(WorkCycle).where(WorkCycle.user_id == user_id, WorkCycle.report_generated == False).order_by(WorkCycle.starts_at.desc()))
    if not cycle:
        cycle = WorkCycle(user_id=user_id, organization_id=organization_id, ends_at=datetime.now(timezone.utc) + timedelta(days=7))
        db.add(cycle)
        db.flush()
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user_id))
    skills = _skill_names(profile.extracted if profile else None) or ["Python", "APIs", "AI Agents"]
    difficulty, difficulty_reason = _adaptive_difficulty(db, user_id, profile)
    day = len(list(db.scalars(select(Task).where(Task.cycle_id == cycle.id)))) + 1
    fallback = _task_for_day(day)
    focus = (profile.career_path or {}).get("focus", "") if profile else ""
    gaps = (profile.career_path or {}).get("assessment", {}).get("gaps", []) if profile else []
    assignment = ai.structured(f"أنت Senior. أنشئ المهمة الصغيرة رقم {day} من 5 ضمن مشروع Web Developer واحد. اجعلها قابلة للإنجاز في يوم ولا تجمع أكثر من هدف. المستوى {difficulty}/5، المهارات {skills}، الفجوات {gaps}، الهدف {focus}. أعد JSON بالمفاتيح title وbrief وcriteria. المثال: {fallback}", fallback)
    if not isinstance(assignment.get("criteria"), list):
        assignment = fallback
    task = Task(
        user_id=user_id,
        organization_id=organization_id,
        cycle_id=cycle.id,
        title=assignment["title"],
        brief=assignment["brief"],
        acceptance_criteria=assignment["criteria"],
        difficulty=difficulty,
        status=TaskStatus.pending_approval if organization_id else TaskStatus.todo,
    )
    db.add(task)
    if profile:
        revisions = list(profile.revisions or [])
        revisions.append({"at": datetime.now(timezone.utc).isoformat(), "difficulty": difficulty, "reason": difficulty_reason, "task": assignment["title"]})
        profile.revisions = revisions
    db.add(Message(user_id=user_id, task_id=task.id, agent="senior", sender="agent", kind="task_alert", body=f"هذه مهمتك {day} من 5: «{task.title}». ركّز على هذه القطعة فقط. راجع المعايير ثم أخبرني بخطتك أو اسألني عن أي نقطة غير واضحة."))
    db.add(Message(user_id=user_id, task_id=task.id, agent="hr", sender="system", kind="agent_sync", body=f"بدأت دورة عمل جديدة بالمهمة «{task.title}» ومستوى صعوبة {difficulty}/5. راقب التواصل والتقدم وطلبات المساعدة."))
    db.commit()
    db.refresh(task)
    return task


def evaluate_task(db: Session, task: Task) -> list[Evaluation]:
    submission = db.scalar(select(Submission).where(Submission.task_id == task.id).order_by(Submission.created_at.desc()))
    artifact = db.scalar(select(SubmissionArtifact).where(SubmissionArtifact.submission_id == submission.id)) if submission else None
    messages = list(db.scalars(select(Message).where(Message.task_id == task.id).order_by(Message.created_at)))
    transcript = "\n".join(f"{item.agent}/{item.sender}: {item.body}" for item in messages[-30:])
    fallback = {
        "senior": {
            "outcome": "improve",
            "scores": {"تنفيذ المطلوب": 3, "جودة الكود": 3, "المنطق": 3, "الأمان والاختبارات": 3},
            "analysis": "تعذر الحصول على تحليل موثوق من المودل، لذلك لن تُعتمد المحاولة تلقائيًا. ناقش Senior وتحقق من معايير النجاح.",
            "improvements": ["شغّل الكود وتحقق من النتيجة", "راجع كل معيار نجاح", "تحقق من حالات الخطأ"],
            "rationale": "يلزم تحقق إضافي.",
            "confidence": 1,
        }
    }
    evidence = {
        "task": task.title,
        "criteria": task.acceptance_criteria,
        "commit_sha": submission.commit_sha if submission else None,
        "submission_summary": submission.summary if submission else "",
        "challenges": submission.challenges if submission else "",
        "submitted_content": artifact.content[:30000] if artifact else "",
        "submission_kind": artifact.kind if artifact else "unknown",
        "conversation": transcript,
    }
    assessed = ai.structured(f"أنت Senior المشرف المباشر. حلل المحاولة مقارنة بكل معيار نجاح. أعد outcome بقيمة excellent فقط إذا تحقق المطلوب بجودة جيدة ولا يوجد نقص مؤثر، وإلا improve. أعط درجات 1-5، analysis واضحًا، وقائمة improvements عملية قصيرة. لا تخترع ملفات أو نتائج تشغيل. أعد JSON بالمفتاح senior مثل المثال {fallback}. الأدلة: {evidence}", fallback)
    results = []
    for agent in ("senior",):
        item = assessed.get(agent, fallback[agent])
        raw_scores = item.get("scores", fallback[agent]["scores"])
        scores = {name: max(1, min(5, int(value))) for name, value in raw_scores.items() if isinstance(value, (int, float))}
        if not scores:
            scores = fallback[agent]["scores"]
        outcome = item.get("outcome") if item.get("outcome") in {"excellent", "improve"} else "improve"
        analysis = str(item.get("analysis", item.get("rationale", fallback[agent]["analysis"])))
        improvements = item.get("improvements", fallback[agent]["improvements"])
        evaluation = Evaluation(
            task_id=task.id,
            agent=agent,
            scores=scores,
            rationale=analysis,
            evidence=[
                {"type": "decision", "outcome": outcome, "improvements": improvements},
                {"type": "submission", "sha": submission.commit_sha if submission else None, "kind": artifact.kind if artifact else "unknown"},
                {"type": "conversation", "message_ids": [message.id for message in messages[-10:]]},
            ],
            confidence=max(1, min(5, int(item.get("confidence", 2)))),
        )
        db.add(evaluation)
        results.append(evaluation)
    task.status = TaskStatus.discussion
    decision = next(item for item in results[0].evidence if item["type"] == "decision")
    review_message = "عمل رائع. راجع تحليلي الكامل ثم انتقل للمهمة التالية." if decision["outcome"] == "excellent" else "المحاولة تحتاج تحسينًا. راجع التحليل وناقشني، ثم أرسل محاولة محسنة أو اعتمد المراجعة."
    db.add(Message(user_id=task.user_id, task_id=task.id, agent="senior", sender="agent", kind="review_ready", body=review_message))
    db.commit()
    return results


def weekly_report(db: Session, cycle: WorkCycle) -> WeeklyReport:
    tasks = list(db.scalars(select(Task).where(Task.cycle_id == cycle.id)))
    completed = [t for t in tasks if t.status == TaskStatus.reviewed]
    evaluations = list(db.scalars(select(Evaluation).where(Evaluation.task_id.in_([task.id for task in completed])))) if completed else []
    scores = [value for evaluation in evaluations for value in evaluation.scores.values() if isinstance(value, (int, float))]
    technical = round(sum(scores) / len(scores), 1) if scores else None
    senior_report = {"tasks_assigned": len(tasks), "tasks_completed": len(completed), "technical_average": technical, "summary": "أكمل Junior خمس مهام متدرجة مع مراجعة كل تسليم." if len(completed) >= 5 else "انتهى الأسبوع قبل إكمال المهام الخمس.", "evidence": [{"task": task.title, "status": task.status.value} for task in tasks]}
    manager_score = max(1, min(5, round(technical or 3)))
    messages = list(db.scalars(select(Message).where(Message.user_id == cycle.user_id, Message.created_at >= cycle.starts_at)))
    user_messages = len([message for message in messages if message.sender == "user"])
    hr_score = 4 if user_messages >= len(completed) else 3
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == cycle.user_id))
    old_score = int((profile.career_path or {}).get("performance_score", 50)) if profile else 50
    weekly_score = round(((technical or 3) / 5 * 70) + (hr_score / 5 * 30))
    performance_score = max(0, min(100, round(old_score * 0.35 + weekly_score * 0.65)))
    report = {
        "kind": "weekly",
        "completed_tasks": len(completed),
        "senior_report": senior_report,
        "manager_evaluation": {"technical_score": manager_score, "summary": "تقييم تقني مبني على تقرير Senior ومراجعات المهام."},
        "hr_evaluation": {"behavior_score": hr_score, "summary": "تقييم سلوكي مبني على الالتزام والتواصل والاستجابة للملاحظات."},
        "previous_performance_score": old_score,
        "performance_score": performance_score,
        "next_difficulty": min(5, tasks[-1].difficulty + 1) if manager_score >= 4 and tasks else max(1, tasks[-1].difficulty - 1) if manager_score <= 2 and tasks else (tasks[-1].difficulty if tasks else 1),
    }
    if profile:
        path = dict(profile.career_path or {})
        assessment = dict(path.get("assessment", {}))
        assessment["starting_difficulty"] = report["next_difficulty"]
        project = dict(path.get("project", {}))
        project["status"] = "week_complete"
        path["assessment"] = assessment
        path["performance_score"] = performance_score
        path["last_weekly_report"] = report
        path["project"] = project
        profile.career_path = path
    db.add(Message(user_id=cycle.user_id, agent="manager", sender="agent", kind="weekly_evaluation", body=f"استلمت تقرير Senior وقيّمت الأداء التقني بدرجة {manager_score}/5."))
    db.add(Message(user_id=cycle.user_id, agent="hr", sender="agent", kind="weekly_evaluation", body=f"اكتمل التقييم السلوكي بدرجة {hr_score}/5، وتحدث ملف الأداء إلى {performance_score}/100."))
    item = WeeklyReport(cycle_id=cycle.id, user_id=cycle.user_id, report=report)
    cycle.report_generated = True
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
