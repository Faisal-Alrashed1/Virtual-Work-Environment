import json
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.db import get_db
from app.core.security import current_user
from app.models.domain import CareerProfile, Message, User
from app.schemas.api import ChatIn, LearningGoalIn, ManualCVIn, ProfileConfirm
from app.services.ai import ai
from app.services.documents import ALLOWED, extract_text, safe_save
from app.services.onboarding import DIAGNOSTIC_QUESTIONS, answer_score, diagnostic_state

router = APIRouter()

@router.get("/intake/state")
def intake_state(user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id))
    if not profile:
        return {"profile_exists": False, "confirmed": False, "progress": 0, "total": 10, "messages": []}
    state = diagnostic_state(profile)
    progress = min(len(state["answers"]), 10)
    rows = list(db.scalars(select(Message).where(Message.user_id == user.id, Message.agent == "career").order_by(Message.created_at.desc()).limit(30)))
    messages = [{"id": item.id, "sender": item.sender, "body": item.body} for item in reversed(rows) if item.kind in {"diagnostic_question", "diagnostic_answer", "diagnostic_result", "learning_goal"}]
    score = sum(int(item.get("score", 0)) for item in state["answers"][:10])
    return {
        "profile_exists": True,
        "confirmed": profile.confirmed,
        "progress": progress,
        "total": 10,
        "score": score if progress == 10 else None,
        "questions_complete": progress == 10,
        "open_goal": state.get("open_goal", ""),
        "messages": messages,
    }

@router.post("/intake/cv")
async def upload_cv(file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    if file.content_type not in ALLOWED:
        raise HTTPException(415, "يدعم النظام PDF وDOCX فقط")
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, "حجم الملف يتجاوز 8MB")
    try:
        text = extract_text(data, file.content_type or "")
    except Exception:
        raise HTTPException(422, "تعذر قراءة السيرة الذاتية")
    if len(text.strip()) < 80:
        raise HTTPException(422, "لا يوجد نص كافٍ في السيرة الذاتية")
    fallback = {
        "skills": [x for x in ["React", "Python", "FastAPI", "Git"] if x.lower() in text.lower()] or ["Web Development"],
        "projects": [],
        "experience_level": "junior",
        "strengths": ["التعلم العملي"],
        "gaps": ["اختبار الأنظمة", "تكاملات AI الآمنة"],
    }
    parsed = ai.structured("استخرج ملف مهني JSON من السيرة التالية: " + text[:12000], fallback)
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id)) or CareerProfile(user_id=user.id)
    profile.cv_path = safe_save(settings.upload_dir, user.id, file.filename or "cv", data)
    profile.extracted = parsed
    profile.diagnostic_summary = json.dumps({"answers": []}, ensure_ascii=False)
    profile.confirmed = False
    db.add(profile)
    db.commit()
    db.refresh(profile)
    opening = f"سنحدد نقطة البداية بعشرة أسئلة قصيرة. لا توجد إجابة سيئة، ويمكن أن تبدأ من الصفر. السؤال 1 من 10: {DIAGNOSTIC_QUESTIONS[0]} أجب بنعم أو لا، ويمكنك إضافة توضيح قصير."
    db.add(Message(user_id=user.id, agent="career", sender="agent", body=opening, kind="diagnostic_question"))
    db.commit()
    return {"profile": parsed, "assistant": opening, "confirmed": False, "progress": 0, "total": 10}

@router.post("/intake/manual-cv")
def create_manual_cv(data: ManualCVIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    extracted = {
        "education": data.education,
        "skills": [skill.strip() for skill in data.skills if skill.strip()],
        "projects": data.projects,
        "experience": data.experience,
        "target_role": data.target_role,
        "experience_level": "junior",
    }
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id)) or CareerProfile(user_id=user.id)
    profile.cv_path = None
    profile.extracted = extracted
    profile.diagnostic_summary = json.dumps({"answers": []}, ensure_ascii=False)
    profile.confirmed = False
    db.add(profile)
    opening = f"تم إنشاء ملفك المهني. سنحدد نقطة البداية بعشرة أسئلة قصيرة. السؤال 1 من 10: {DIAGNOSTIC_QUESTIONS[0]}"
    db.add(Message(user_id=user.id, agent="career", sender="agent", body=opening, kind="diagnostic_question"))
    db.commit()
    return {"profile": extracted, "assistant": opening, "confirmed": False, "progress": 0, "total": 10}

@router.post("/intake/chat")
def intake_chat(data: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id))
    if not profile:
        raise HTTPException(409, "ارفع السيرة الذاتية أولًا")
    state = diagnostic_state(profile)
    index = len(state["answers"])
    if index >= len(DIAGNOSTIC_QUESTIONS):
        score = sum(item["score"] for item in state["answers"])
        return {
            "reply": f"اكتمل التشخيص. نتيجتك {score} من 10. اكتب الآن بصراحة ما الذي تريد تعلمه وما الذي تشعر أنه ينقصك عن سوق العمل.",
            "ready": bool(state.get("open_goal")),
            "questions_complete": True,
            "progress": 10,
            "total": 10,
            "score": score,
        }
    point = answer_score(data.body)
    state["answers"].append({"question": DIAGNOSTIC_QUESTIONS[index], "answer": data.body, "score": point})
    profile.diagnostic_summary = json.dumps(state, ensure_ascii=False)
    db.add(Message(user_id=user.id, agent="career", sender="user", body=data.body, kind="diagnostic_answer"))
    progress = len(state["answers"])
    score = sum(item["score"] for item in state["answers"])
    if progress < len(DIAGNOSTIC_QUESTIONS):
        answer = f"تم. السؤال {progress + 1} من 10: {DIAGNOSTIC_QUESTIONS[progress]} أجب بنعم أو لا."
        ready = False
    else:
        level = "مبتدئ من الصفر" if score <= 2 else "مبتدئ" if score <= 4 else "متوسط" if score <= 7 else "متقدم"
        answer = f"اكتملت الأسئلة. نتيجتك {score} من 10، ونقطة البداية المناسبة: {level}. الآن اكتب بصراحة وبأسلوبك: ماذا تريد أن تتعلم؟ وما الذي تشعر أنه ينقصك عن سوق العمل؟ هذه الإجابة ستكون محور المسار."
        ready = False
    db.add(Message(user_id=user.id, agent="career", sender="agent", body=answer, kind="diagnostic_result" if progress == 10 else "diagnostic_question"))
    db.commit()
    return {"reply": answer, "ready": ready, "questions_complete": progress == 10, "progress": progress, "total": 10, "score": score if progress == 10 else None}

@router.post("/intake/goal")
def save_learning_goal(data: LearningGoalIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id))
    if not profile:
        raise HTTPException(409, "ارفع السيرة الذاتية أولًا")
    state = diagnostic_state(profile)
    if len(state["answers"]) < 10:
        raise HTTPException(409, "أكمل أسئلة تحديد المستوى أولًا")
    state["open_goal"] = data.goal.strip()
    profile.diagnostic_summary = json.dumps(state, ensure_ascii=False)
    db.add(Message(user_id=user.id, agent="career", sender="user", body=data.goal.strip(), kind="learning_goal"))
    db.commit()
    return {"saved": True, "message": "تم حفظ هدفك وسيكون محور المسار والمهام."}

@router.post("/intake/confirm")
def confirm_profile(data: ProfileConfirm, user: User = Depends(current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id))
    if not profile:
        raise HTTPException(409, "ارفع السيرة الذاتية أولًا")
    state = diagnostic_state(profile)
    if len(state["answers"]) < 10:
        raise HTTPException(409, f"أكمل الأسئلة العشرة أولًا ({len(state['answers'])}/10)")
    open_goal = state.get("open_goal", "").strip()
    if len(open_goal) < 10:
        raise HTTPException(409, "اكتب ما تريد تعلمه وما ينقصك عن سوق العمل أولًا")
    score = sum(item["score"] for item in state["answers"])
    difficulty = min(5, score // 2 + 1)
    gaps = [item["question"] for item in state["answers"] if item["score"] == 0]
    fallback_path = {
        "goal": "Web Developer",
        "focus": open_goal,
        "assessment": {"score": score, "out_of": 10, "starting_difficulty": difficulty, "gaps": gaps},
        "stages": [
            {"name": "أساسيات Web", "status": "current", "skills": ["HTML", "CSS", "JavaScript", "Git"]},
            {"name": "تطبيق متكامل", "status": "next", "skills": ["Frontend", "Backend", "API", "Database"]},
            {"name": "جودة المشروع", "status": "future", "skills": ["Testing", "Security", "Deployment"]},
        ],
    }
    path_prompt = f"ابنِ مسار Web Developer عام من ثلاث مراحل فقط. اربط السيرة بالتقييم العام في frontend وbackend وAPI وقواعد البيانات، ولا تفترض إتقان مهارة لمجرد وجودها في السيرة. أعد JSON بنفس بنية المثال. السيرة: {profile.extracted}. النتيجة: {score}/10. الفجوات: {gaps}. هدف المستخدم: {open_goal}. المثال: {fallback_path}"
    career_path = ai.structured(path_prompt, fallback_path)
    career_path["assessment"] = fallback_path["assessment"]
    career_path["focus"] = open_goal
    career_path["performance_score"] = score * 10
    career_path["project"] = {"status": "ready", "name": "Junior Web Workspace", "tasks_per_week": 5}
    profile.confirmed = True
    profile.career_path = career_path
    db.commit()
    return {"career_path": profile.career_path, "next": "project_kickoff"}
