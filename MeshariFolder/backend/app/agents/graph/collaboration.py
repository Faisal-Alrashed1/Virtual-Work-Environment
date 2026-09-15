"""
The ask_agent collaboration primitive (docs/STAGE2_WEEKLY_CYCLE_FLOW.md):
lets another agent consult the Mentor directly mid-cascade instead of
only reading its stored review text — the concrete piece of "more
collaborative, not just assigning tasks."

Uses llm_client.call_with_tool, the same pattern the rest of
app/agents/ already uses, on purpose: this is a consult between two
existing agents, not a new model tier, so there's no reason to introduce
a different framework/model client for it. What moves to LangGraph is
the cascade's *sequencing* (weekly_cycle_graph.py) — not this call.
"""
from sqlalchemy.orm import Session

from app.agents import mentor
from app.agents.llm_client import call_with_tool
from app.models import ReviewKind, User, Week

CONSULT_TOOL = {
    "name": "reply_to_colleague",
    "description": (
        "Answer a colleague's question directly and briefly, from what "
        "you've actually observed this week. Not a formal review."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"reply": {"type": "string"}},
        "required": ["reply"],
    },
}


def ask_mentor(db: Session, user: User, week: Week, question: str) -> str:
    mentor_reviews = [r for r in week.reviews if r.kind == ReviewKind.TASK_REVIEW]
    reviews_text = "\n\n".join(
        f"Subtask {i + 1} (verdict: {(r.metrics_json or {}).get('verdict', '?')}): {r.content}"
        for i, r in enumerate(mentor_reviews)
    ) or "No reviews recorded this week."

    result = call_with_tool(
        system=(
            mentor.SYSTEM_PROMPT
            + "\n\nA colleague is consulting you directly, not asking for "
            "a formal review. Answer briefly and specifically, from what "
            "you've actually observed this week."
        ),
        messages=[
            {
                "role": "user",
                "content": f"This week's reviews so far:\n{reviews_text}\n\nQuestion: {question}",
            }
        ],
        tools=[CONSULT_TOOL],
        force_tool="reply_to_colleague",
    )
    return result["input"]["reply"]
