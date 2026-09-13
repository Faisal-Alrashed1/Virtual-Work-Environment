from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import current_user
from app.models.domain import CareerProfile, Message, User
from app.schemas.api import ChatIn
from app.services.ai import ai
from app.services.orchestrator import shared_agent_context, sync_agents

router = APIRouter()

@router.get("/agents/{agent}/messages")
def messages(agent: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if agent not in {"manager", "senior", "hr"}:
        raise HTTPException(404, "الوكيل غير موجود")
    rows = db.scalars(select(Message).where(Message.user_id == user.id, Message.agent == agent).order_by(Message.created_at))
    return [{"id": m.id, "sender": m.sender, "body": m.body, "kind": m.kind, "created_at": m.created_at} for m in rows]

@router.post("/agents/{agent}/messages")
def send_message(agent: str, data: ChatIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if agent not in {"manager", "senior", "hr"}:
        raise HTTPException(404, "الوكيل غير موجود")
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user.id))
    if ((profile.career_path or {}).get("project", {}).get("status") == "active") and agent != "senior":
        raise HTTPException(403, "أثناء تنفيذ الأسبوع يكون تواصلك المباشر مع Senior فقط")
    db.add(Message(user_id=user.id, task_id=data.task_id, agent=agent, sender="user", body=data.body))
    db.flush()
    context = shared_agent_context(db, user.id, agent, data.task_id)
    reply = ai.chat(agent, data.body, context)
    db.add(Message(user_id=user.id, task_id=data.task_id, agent=agent, sender="agent", body=reply))
    sync_agents(db, user.id, agent, data.task_id, data.body)
    db.commit()
    return {"reply": reply}
