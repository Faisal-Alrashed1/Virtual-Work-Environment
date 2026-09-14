"""
Stage 2 onboarding graph (docs/STAGE2_ONBOARDING_FLOW.md):

  CV uploaded -> agent-generated, skippable Q&A -> track suggested and
  approved -> agent roster suggested and approved -> onboarding complete.

Three human-in-the-loop points use LangGraph's interrupt(): the graph
pauses and control returns to the caller between each one. Resuming means
invoking again with Command(resume=payload) against the same thread_id
(the graduate's user_id) — state persists in the checkpointer in between,
so a graduate can close the tab mid-onboarding and pick up where they
left off. The router endpoints that drive this from the frontend are the
next branch; this module only owns the graph itself.
"""
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from app.agents.graph.models import small_model
from app.agents.graph.state import OnboardingState
from app.models import TrackEnum

QUESTIONS_TOOL = {
    "name": "generate_questions",
    "description": (
        "Propose 2-4 short follow-up questions about whatever this CV "
        "doesn't cover well — skill depth, project experience, gaps. "
        "Each should be answerable in a sentence or two. If the CV is "
        "already thorough, propose fewer, more targeted questions rather "
        "than padding to 4."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "minItems": 1,
                "maxItems": 4,
                "items": {"type": "string"},
            }
        },
        "required": ["questions"],
    },
}

_TRACK_VALUES = [t.value for t in TrackEnum if t != TrackEnum.JUNIOR_DEV]

TRACK_TOOL = {
    "name": "suggest_track",
    "description": "Suggest the IT major/track that best fits this graduate.",
    "input_schema": {
        "type": "object",
        "properties": {
            "track": {"type": "string", "enum": _TRACK_VALUES},
            "reasoning": {
                "type": "string",
                "description": "One or two sentences, shown to the graduate alongside the suggestion.",
            },
        },
        "required": ["track", "reasoning"],
    },
}

AGENTS_TOOL = {
    "name": "suggest_agents",
    "description": (
        "Suggest which optional agents (by id, from the given catalog) fit "
        "this graduate's track. It's fine to suggest none if nothing is a "
        "clear fit — don't pad the list."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "agent_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["agent_ids"],
    },
}


def _forced_tool_call(model: ChatAnthropic, tool: dict, messages: list) -> dict:
    """Binds a single tool with tool_choice forced to it, invokes, and
    returns that tool call's args. Mirrors llm_client.call_with_tool's
    contract, translated to LangChain's tool-call shape."""
    bound = model.bind_tools([tool], tool_choice=tool["name"])
    response = bound.invoke(messages)
    for call in response.tool_calls:
        if call["name"] == tool["name"]:
            return call["args"]
    raise RuntimeError(f"Model did not call '{tool['name']}' as expected.")


# --- Nodes -----------------------------------------------------------------

def generate_questions(state: OnboardingState) -> dict:
    args = _forced_tool_call(
        small_model(),
        QUESTIONS_TOOL,
        [
            SystemMessage(
                "You are Venv's onboarding agent. Look at this graduate's "
                "CV and propose a short, skippable set of follow-up "
                "questions about whatever it doesn't cover well."
            ),
            HumanMessage(f"CV:\n{state.get('cv_raw_text') or '(no CV provided)'}"),
        ],
    )
    questions = [{"question": q, "answer": None} for q in args["questions"]]
    return {"questions": questions, "stage": "qa"}


def await_answers(state: OnboardingState) -> dict:
    """Pauses for the graduate's answers — each question is independently
    skippable — plus any free text they want to add themselves."""
    payload = interrupt(
        {
            "type": "qa",
            "questions": [q["question"] for q in state["questions"]],
        }
    )
    answers = payload.get("answers", {})
    questions = [
        {**q, "answer": answers.get(str(i))}
        for i, q in enumerate(state["questions"])
    ]
    return {
        "questions": questions,
        "intro_text": payload.get("intro_text"),
        "stage": "track",
    }


def suggest_track(state: OnboardingState) -> dict:
    answered = (
        "\n".join(
            f"Q: {q['question']}\nA: {q['answer']}"
            for q in state["questions"]
            if q["answer"]
        )
        or "(no follow-up answers given — that's fine, work from the CV)"
    )
    args = _forced_tool_call(
        small_model(),
        TRACK_TOOL,
        [
            SystemMessage(
                "Suggest which IT track best fits this graduate, using "
                "their CV, follow-up answers, and anything they added "
                "about themselves."
            ),
            HumanMessage(
                f"CV:\n{state.get('cv_raw_text') or '(none)'}\n\n"
                f"Follow-up Q&A:\n{answered}\n\n"
                f"Self-description:\n{state.get('intro_text') or '(none)'}"
            ),
        ],
    )
    return {
        "suggested_track": args["track"],
        "track_reasoning": args["reasoning"],
        "stage": "track",
    }


def await_track_approval(state: OnboardingState) -> dict:
    payload = interrupt(
        {
            "type": "track_approval",
            "suggested_track": state["suggested_track"],
            "reasoning": state["track_reasoning"],
        }
    )
    return {
        "approved_track": payload.get("track") or state["suggested_track"],
        "stage": "agents",
    }


def suggest_agents(state: OnboardingState) -> dict:
    catalog = state.get("catalog", [])
    if not catalog:
        return {"suggested_agent_ids": [], "stage": "agents"}
    catalog_text = "\n".join(
        f"- {c['id']}: {c['name']} — {c['description']}" for c in catalog
    )
    args = _forced_tool_call(
        small_model(),
        AGENTS_TOOL,
        [
            SystemMessage(
                "Suggest which optional agents fit this graduate's track, "
                "from the catalog given."
            ),
            HumanMessage(f"Track: {state['approved_track']}\n\nCatalog:\n{catalog_text}"),
        ],
    )
    valid_ids = {c["id"] for c in catalog}
    suggested = [a for a in args["agent_ids"] if a in valid_ids]
    return {"suggested_agent_ids": suggested, "stage": "agents"}


def await_agent_approval(state: OnboardingState) -> dict:
    payload = interrupt(
        {
            "type": "agent_approval",
            "suggested_agent_ids": state["suggested_agent_ids"],
        }
    )
    return {
        "approved_agent_ids": payload.get("agent_ids", state["suggested_agent_ids"]),
        "stage": "complete",
    }


def finalize(state: OnboardingState) -> dict:
    return {"stage": "complete"}


# --- Graph -------------------------------------------------------------

def build_onboarding_graph(checkpointer=None):
    """checkpointer defaults to an in-memory saver — fine for dev/tests,
    but process-local. Swap in a persistent one (e.g. a Postgres saver)
    before this goes to production, or a restart loses every graduate's
    in-progress onboarding."""
    graph = StateGraph(OnboardingState)

    for name, node in [
        ("generate_questions", generate_questions),
        ("await_answers", await_answers),
        ("suggest_track", suggest_track),
        ("await_track_approval", await_track_approval),
        ("suggest_agents", suggest_agents),
        ("await_agent_approval", await_agent_approval),
        ("finalize", finalize),
    ]:
        graph.add_node(name, node)

    graph.set_entry_point("generate_questions")
    graph.add_edge("generate_questions", "await_answers")
    graph.add_edge("await_answers", "suggest_track")
    graph.add_edge("suggest_track", "await_track_approval")
    graph.add_edge("await_track_approval", "suggest_agents")
    graph.add_edge("suggest_agents", "await_agent_approval")
    graph.add_edge("await_agent_approval", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=checkpointer or InMemorySaver())
