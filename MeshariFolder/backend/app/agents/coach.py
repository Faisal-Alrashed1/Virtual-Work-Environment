"""Career Coach Agent for Venv."""

from sqlalchemy.orm import Session

from app.models import Review, User


SYSTEM_PROMPT = (
    "You are the Coach Agent at Venv. "
    "You help a recent graduate turn their current skills, project experience, "
    "and review history into practical career progress. "
    "Focus on resume improvement, portfolio development, interview preparation, "
    "skill gaps, and short-term career goals. "
    "Give specific and practical advice based on the trainee's actual progress. "
    "Do not take over the Manager's task-planning role or the Mentor's "
    "technical-review role."
)

from sqlalchemy.orm import Session

from app.models import Review, User

SYSTEM_PROMPT = (...)

def build_context(db: Session, user: User) -> str:
    """Build career-specific context for the Coach Agent."""

    parts: list[str] = [
        f"Confirmed track: {user.track.value}"
    ]

    employee_file = user.employee_file

    if employee_file:
        parts.append(f"Skills: {employee_file.skills_json}")
        parts.append(f"Strengths: {employee_file.strengths_json}")
        parts.append(f"Growth areas: {employee_file.growth_areas_json}")

        if employee_file.summary_text:
            parts.append(
                f"Employee File summary: {employee_file.summary_text}"
            )

    recent_reviews = (
        db.query(Review)
        .filter(Review.user_id == user.id)
        .order_by(Review.created_at.desc())
        .limit(5)
        .all()
    )

    if recent_reviews:
        review_lines = [
            f"- {review.agent_type.value}/{review.kind.value}: "
            f"{review.content[:500]}"
            for review in recent_reviews
        ]

        parts.append(
            "Recent performance evidence:\n"
            + "\n".join(review_lines)
        )

    return "Career coaching context:\n" + "\n".join(parts)