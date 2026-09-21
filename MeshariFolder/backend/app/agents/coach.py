"""Career Coach Agent for Venv."""

from sqlalchemy.orm import Session


from app.agents.llm_client import call_agentic
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



def build_context(db: Session, user: User) -> str:
    """Build career-specific context for the Coach Agent."""

    parts: list[str] = []

    if user.track:
        parts.append(f"Confirmed track: {user.track.value}")
    else:
        parts.append("Confirmed track: not selected yet")

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

def build_career_profile(user: User) -> str:
    """Build a short career profile for the trainee."""

    parts: list[str] = []

    if user.track:
        parts.append(f"Career track: {user.track.value}")

    employee_file = user.employee_file

    if employee_file:
        if employee_file.skills_json:
            parts.append(f"Current skills: {employee_file.skills_json}")

        if employee_file.strengths_json:
            parts.append(f"Strengths: {employee_file.strengths_json}")

        if employee_file.growth_areas_json:
            parts.append(
                f"Skills to improve: {employee_file.growth_areas_json}"
            )

    if not parts:
        return "No career profile information is available yet."

    return "\n".join(parts)

def generate_reply(
    db: Session,
    user: User,
    messages: list[dict[str, str]],
) -> str:
    """Generate a personalized Career Coach response."""

    context = build_context(db, user)

    reply_obj = call_agentic(
        system=SYSTEM_PROMPT + "\n\n" + context,
        messages=messages,
        tools=[],
        max_tokens=1000,
    )

    return reply_obj.text or "Unable to generate a coaching response."

def generate_career_plan(
    db: Session,
    user: User,
) -> str:
    """Generate a practical career plan for the trainee."""

    context = build_context(db, user)

    messages = [
        {
            "role": "user",
            "content": (
                "Create a practical career plan for this trainee. "
                "Include: current position, top skill gaps, "
                "3 short-term goals, concrete actions, and next career step."
            ),
        }
    ]

    reply_obj = call_agentic(
        system=SYSTEM_PROMPT + "\n\n" + context,
        messages=messages,
        tools=[],
        max_tokens=1200,
    )

    return reply_obj.text or "Unable to generate a career plan."
