"""
Career Coach agent — the one dedicated action beyond chat
(docs/TEN_AGENTS.md). Resume feedback, interview prep, and general
career questions already work fine as ordinary Meeting Room / Team Room
conversation (see meeting.py's PERSONA) — nothing needed there. What was
missing was anything the Career Coach *writes down*, the way HR's
run_rollup updates the Employee File and Mentor's review_task creates a
Review: a career check-in that reads the graduate's actual Employee
File and CV and produces something genuinely usable — real resume
bullets and one thing to focus on next — not just another chat reply
that evaporates once the conversation scrolls past it.
"""
from sqlalchemy.orm import Session

from app.agents.llm_client import call_with_tool
from app.agents.tools import CAREER_CHECKIN_TOOL
from app.models import AgentType, Review, ReviewKind, User

SYSTEM_PROMPT = (
    "You are the Career Coach at Venv, writing a graduate's career "
    "check-in. Ground everything in their actual Employee File and CV — "
    "specific skills, specific reviewed work — never generic career "
    "advice. Resume bullets should read like real resume bullets (action "
    "verb, what was built, why it mattered), not restated task titles."
)


def run_checkin(db: Session, user: User) -> Review:
    """Requires at least a summarized Employee File — mirrors hr.
    run_rollup's own precondition (nothing to work from otherwise),
    though in practice HR's rollup typically runs first anyway."""
    ef = user.employee_file
    if not ef or not ef.summary_text:
        raise ValueError("No employee file yet — nothing for the Career Coach to work from.")

    prompt = (
        "Employee File:\n"
        f"  Skills: {ef.skills_json}\n"
        f"  Strengths: {ef.strengths_json}\n"
        f"  Growth areas: {ef.growth_areas_json}\n"
        f"  Summary: {ef.summary_text}\n\n"
        f"CV on file:\n{user.cv_raw_text or '(none provided)'}\n\n"
        "Write this graduate's career check-in now via the submit_career_checkin tool."
    )
    result = call_with_tool(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        tools=[CAREER_CHECKIN_TOOL],
        force_tool="submit_career_checkin",
        max_tokens=900,
    )
    data = result["input"]

    review = Review(
        user_id=user.id,
        task_id=None,
        agent_type=AgentType.CAREER_COACH,
        kind=ReviewKind.CAREER_CHECKIN,
        content=data["summary"],
        metrics_json={
            "resume_highlights": data["resume_highlights"],
            "suggested_focus": data["suggested_focus"],
        },
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review
