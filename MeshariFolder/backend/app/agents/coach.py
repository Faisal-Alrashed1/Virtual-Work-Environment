"""Career Coach Agent for Venv."""

from sqlalchemy.orm import Session
from app.agents.tools import CAREER_COACH_TOOLS

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

    if user.cv_raw_text:
        parts.append(
          f"CV content: {user.cv_raw_text[:2000]}"
      )

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
        tools=CAREER_COACH_TOOLS,
        max_tokens=1000,
    )

    if reply_obj.tool_calls:
        tool_call = reply_obj.tool_calls[0]
        data = tool_call.input

        if tool_call.name == "create_career_plan":
            return (
                f"Current position: {data['current_position']}\n\n"
                f"Skill gaps: {', '.join(data['skill_gaps'])}\n\n"
                f"Short-term goals:\n- "
                + "\n- ".join(data["short_term_goals"])
                + "\n\nActions:\n- "
                + "\n- ".join(data["actions"])
                + f"\n\nNext step: {data['next_step']}"
            )

        if tool_call.name == "analyze_skill_gaps":
            return (
                "Strengths:\n- "
                + "\n- ".join(data["strengths"])
                + "\n\nSkill gaps:\n- "
                + "\n- ".join(data["gaps"])
                + "\n\nPriorities:\n- "
                + "\n- ".join(data["priorities"])
                + f"\n\nRecommendation: {data['recommendation']}"
            )

        if tool_call.name == "prepare_interview":
            return (
                "Interview focus areas:\n- "
                + "\n- ".join(data["focus_areas"])
                + "\n\nPractice questions:\n- "
                + "\n- ".join(data["practice_questions"])
                + "\n\nPreparation tips:\n- "
                + "\n- ".join(data["preparation_tips"])
            )

        if tool_call.name == "review_resume":
            return (
                "Resume strengths:\n- "
                + "\n- ".join(data["strengths"])
                + "\n\nWeak sections:\n- "
                + "\n- ".join(data["weak_sections"])
                + "\n\nMissing skills:\n- "
                + "\n- ".join(data["missing_skills"])
                + "\n\nRecommended improvements:\n- "
                + "\n- ".join(data["improvements"])
                + f"\n\nSuggested professional summary:\n{data['suggested_summary']}"
            )

        if tool_call.name == "build_portfolio_plan":
            return (
                "Projects to showcase:\n- "
                + "\n- ".join(data["projects_to_showcase"])
                + "\n\nSkills to highlight:\n- "
                + "\n- ".join(data["skills_to_highlight"])
                + "\n\nMissing project types:\n- "
                + "\n- ".join(data["missing_project_types"])
                + "\n\nPortfolio actions:\n- "
                + "\n- ".join(data["portfolio_actions"])
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
