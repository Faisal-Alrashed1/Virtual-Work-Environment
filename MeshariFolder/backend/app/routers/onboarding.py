"""
Stage 2 onboarding router — drives app/agents/graph/onboarding_graph.py
from the frontend: upload a CV file, answer (or skip) the agent-generated
Q&A, approve or override the suggested track, approve or edit the
suggested agent roster. See docs/STAGE2_ONBOARDING_FLOW.md for the design
and a LangGraph gotcha this code works around — never resume with a bare
empty dict (`Command(resume={})`); LangGraph treats that as "nothing to
resume" and replays the same interrupt instead of advancing. Every resume
below sends a dict with at least one key for that reason, even when the
value itself is None.

The compiled graph is a module-level singleton — see
build_onboarding_graph's docstring: its checkpointer is in-memory and
process-local, fine for dev, but a restart loses every graduate's
in-progress onboarding, and re-uploading a CV mid-flow isn't handled yet
(it restarts the graph on the same thread rather than resetting it
cleanly). Both are open items, not bugs introduced here.
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from langgraph.types import Command
from sqlalchemy.orm import Session

from app.agents.graph.catalog import catalog_as_dicts
from app.agents.graph.cv_parsing import extract_cv_text
from app.agents.graph.onboarding_graph import build_onboarding_graph
from app.auth import get_current_user
from app.database import get_db
from app.models import AgentCatalog, OnboardingStage, TrackEnum, User, UserAgent
from app.schemas import (
    AgentCatalogOut,
    OnboardingAgentsApprove,
    OnboardingAgentsOut,
    OnboardingCompleteOut,
    OnboardingQASubmit,
    OnboardingQuestionsOut,
    OnboardingStateOut,
    OnboardingTrackApprove,
    OnboardingTrackOut,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

_graph = build_onboarding_graph()


def _config(user: User) -> dict:
    return {"configurable": {"thread_id": user.id}}


def _interrupt_payload(result: dict) -> dict:
    interrupts = result.get("__interrupt__")
    if not interrupts:
        raise HTTPException(500, "Onboarding graph didn't pause where expected.")
    return interrupts[0].value


@router.get("/catalog", response_model=list[AgentCatalogOut])
def read_catalog(db: Session = Depends(get_db)):
    """The full optional-agent catalog — lets the frontend show every
    pickable agent, not just the ones suggested for the graduate's track,
    so the roster-approval step can be a real edit, not just a checkbox
    on the suggestion. No auth required: this is catalog metadata, not
    anything user-specific."""
    return db.query(AgentCatalog).all()


@router.post("/cv", response_model=OnboardingQuestionsOut)
def upload_cv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Starts onboarding: parses the file, stores the raw text (same
    has_cv semantics Stage 1 already exposes via UserOut), and runs the
    graph up to the first interrupt — the Q&A questions."""
    content = file.file.read()
    cv_text = extract_cv_text(file.filename or "cv.txt", content)
    if not cv_text.strip():
        raise HTTPException(400, "Couldn't extract any text from that file.")

    current_user.cv_raw_text = cv_text
    db.commit()

    initial_state = {
        "user_id": current_user.id,
        "cv_raw_text": cv_text,
        "catalog": catalog_as_dicts(db),
    }
    result = _graph.invoke(initial_state, config=_config(current_user))
    payload = _interrupt_payload(result)

    current_user.onboarding_stage = OnboardingStage.QA
    db.commit()
    return {"questions": payload["questions"]}


@router.post("/qa", response_model=OnboardingTrackOut)
def submit_qa(
    payload: OnboardingQASubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = _graph.invoke(
        Command(resume={"answers": payload.answers, "intro_text": payload.intro_text}),
        config=_config(current_user),
    )
    data = _interrupt_payload(result)

    current_user.intro_text = payload.intro_text
    current_user.onboarding_qa_json = result.get("questions", [])
    current_user.suggested_track = TrackEnum(result["suggested_track"])
    current_user.onboarding_stage = OnboardingStage.TRACK
    db.commit()
    return {"suggested_track": data["suggested_track"], "reasoning": data["reasoning"]}


@router.post("/track", response_model=OnboardingAgentsOut)
def approve_track(
    payload: OnboardingTrackApprove,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = _graph.invoke(
        Command(resume={"track": payload.track.value if payload.track else None}),
        config=_config(current_user),
    )
    data = _interrupt_payload(result)

    current_user.track = TrackEnum(result["approved_track"])
    current_user.track_confirmed = True
    current_user.onboarding_stage = OnboardingStage.AGENTS
    db.commit()

    suggested = (
        db.query(AgentCatalog)
        .filter(AgentCatalog.id.in_(data["suggested_agent_ids"]))
        .all()
    )
    return {"suggested_agents": suggested}


@router.post("/agents", response_model=OnboardingCompleteOut)
def approve_agents(
    payload: OnboardingAgentsApprove,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = _graph.invoke(
        Command(resume={"agent_ids": payload.agent_ids}),
        config=_config(current_user),
    )
    if "__interrupt__" in result:
        raise HTTPException(500, "Onboarding graph didn't complete as expected.")

    current_user.onboarding_qa_json = result.get("questions", [])
    current_user.onboarding_stage = OnboardingStage.COMPLETE
    db.commit()

    # Replace any previous selection with this final approved roster —
    # makes the endpoint idempotent if the graduate edits and resubmits.
    db.query(UserAgent).filter(UserAgent.user_id == current_user.id).delete()
    agents = db.query(AgentCatalog).filter(AgentCatalog.id.in_(payload.agent_ids)).all()
    for agent in agents:
        db.add(UserAgent(user_id=current_user.id, agent_catalog_id=agent.id))
    db.commit()

    return {"track": current_user.track, "agents": agents}


@router.get("/state", response_model=OnboardingStateOut)
def read_onboarding_state(current_user: User = Depends(get_current_user)):
    """Lets the frontend figure out where to resume without replaying the
    graph — e.g. show the Q&A screen again if stage is 'qa'."""
    return current_user
