"""
The end-of-week cascade, ported to a small LangGraph StateGraph
(docs/STAGE2_WEEKLY_CYCLE_FLOW.md) so the Manager and HR steps actually
consult the Mentor (collaboration.ask_mentor) before writing their own
reviews, instead of only reading its stored review text.

Only the cascade is modeled as a graph — the rest of weekly_cycle.py's
state machine (idempotent open-task checks, releasing the next planned
subtask) is a plain lookup with no LLM call either way, so forcing it
into a graph wouldn't add anything. The cascade is the one part that's
genuinely a multi-step sequence with real dependencies (consult, then
write; consult, then write), which is exactly what a graph is for.

run_end_of_week_cascade(db, user, week) is a drop-in replacement for the
two flat calls weekly_cycle.py used to make directly — same side effects
(two new Review rows), same signature shape, same call site.
"""
from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents import hr, manager
from app.agents.graph.collaboration import ask_mentor
from app.models import Review, User, Week


class CascadeState(TypedDict, total=False):
    db: Session
    user: User
    week: Week
    manager_consult: str
    hr_consult: str
    manager_review: Review
    hr_review: Review


def _consult_for_manager(state: CascadeState) -> dict:
    answer = ask_mentor(
        state["db"],
        state["user"],
        state["week"],
        "How did the graduate do this week overall? Any patterns across "
        "the subtasks worth flagging in the progress review?",
    )
    return {"manager_consult": answer}


def _manager_writes(state: CascadeState) -> dict:
    review = manager.submit_week_progress(
        state["db"], state["user"], state["week"], mentor_consult=state["manager_consult"]
    )
    return {"manager_review": review}


def _consult_for_hr(state: CascadeState) -> dict:
    answer = ask_mentor(
        state["db"],
        state["user"],
        state["week"],
        "Any concerns about consistency or engagement this week, beyond "
        "the raw attendance numbers?",
    )
    return {"hr_consult": answer}


def _hr_writes(state: CascadeState) -> dict:
    review = hr.run_behavioral_review(
        state["db"], state["user"], state["week"], mentor_consult=state["hr_consult"]
    )
    return {"hr_review": review}


def _build_cascade_graph():
    graph = StateGraph(CascadeState)
    graph.add_node("consult_for_manager", _consult_for_manager)
    graph.add_node("manager_writes", _manager_writes)
    graph.add_node("consult_for_hr", _consult_for_hr)
    graph.add_node("hr_writes", _hr_writes)

    graph.set_entry_point("consult_for_manager")
    graph.add_edge("consult_for_manager", "manager_writes")
    graph.add_edge("manager_writes", "consult_for_hr")
    graph.add_edge("consult_for_hr", "hr_writes")
    graph.add_edge("hr_writes", END)
    return graph.compile()


_cascade_graph = _build_cascade_graph()


def run_end_of_week_cascade(db: Session, user: User, week: Week) -> tuple[Review, Review]:
    """No checkpointer/thread_id needed here, unlike the onboarding graph
    — this runs start to finish in one invoke, no human-in-the-loop pause."""
    result = _cascade_graph.invoke({"db": db, "user": user, "week": week})
    return result["manager_review"], result["hr_review"]
