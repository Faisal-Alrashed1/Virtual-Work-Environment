from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.domain import CareerProfile, Evaluation, Message, Submission, Task, WorkCycle


class AgentGateway:
    """Central gateway providing decoupled read/write access for AI Agents."""

    @staticmethod
    def get_task_context(db: Session, task_id: str) -> dict | None:
        task = db.get(Task, task_id)
        if not task:
            return None
        submission = db.scalar(select(Submission).where(Submission.task_id == task.id).order_by(Submission.created_at.desc()))
        messages = list(db.scalars(select(Message).where(Message.task_id == task.id).order_by(Message.created_at.desc()).limit(15)))
        return {
            "task": {"id": task.id, "title": task.title, "brief": task.brief, "criteria": task.acceptance_criteria, "difficulty": task.difficulty, "status": task.status},
            "submission": {"summary": submission.summary, "commit_sha": submission.commit_sha} if submission else None,
            "recent_messages": [{"sender": m.sender, "agent": m.agent, "body": m.body} for m in reversed(messages)],
        }

    @staticmethod
    def get_trainee_profile(db: Session, user_id: str) -> dict | None:
        profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user_id))
        return profile.extracted if profile else None

    @staticmethod
    def record_agent_evaluation(db: Session, task_id: str, agent_id: str, scores: dict, rationale: str, evidence: list, confidence: float = 1.0) -> Evaluation:
        eval_item = Evaluation(task_id=task_id, agent=agent_id, scores=scores, rationale=rationale, evidence=evidence, confidence=confidence)
        db.add(eval_item)
        db.commit()
        db.refresh(eval_item)
        return eval_item


agent_gateway = AgentGateway()
