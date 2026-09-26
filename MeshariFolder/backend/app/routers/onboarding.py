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

The compiled graph is a module-level singleton whose checkpointer is
in-memory and per-process — so it is NOT trusted as the record of where a
graduate is. Every pause's output is saved on the User row, and each step
below first makes sure the graph thread is paused at the right place,
rebuilding it from the database if it isn't (a restart, another worker, a
stale thread). That is what makes onboarding resumable — see
docs/ONBOARDING_RESUME.md and app/agents/graph/onboarding_resume.py.
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from langgraph.types import Command
from sqlalchemy.orm import Session

from app.agents.graph.catalog import catalog_as_dicts
from app.agents.graph.cv_parsing import CVReadError, read_cv_upload, validate_is_cv
from app.agents.graph.onboarding_graph import build_onboarding_graph
from app.agents.graph.onboarding_resume import NotResumable, can_resume, drop_thread, ensure_paused_at
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
    OnboardingResumeOut,
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


def _require_stage(user: User, *allowed: OnboardingStage) -> None:
    """Steps must happen in order. Without this a double-clicked "continue"
    would resume the graph at the *next* pause with the previous step's
    payload — e.g. a second Q&A submit silently approving the suggested track."""
    if user.onboarding_stage not in allowed:
        raise HTTPException(
            409,
            f"Onboarding isn't at that step (you're at '{user.onboarding_stage.value}'). "
            "Reload the page to continue where you left off.",
        )


def _prepare_thread(user: User, db: Session, stage: OnboardingStage) -> None:
    """Make sure the graph is paused at `stage`'s human step — rebuilt from
    the database if the in-memory thread is missing or stale."""
    try:
        ensure_paused_at(_graph, user, catalog_as_dicts(db), stage)
    except NotResumable:
        raise HTTPException(
            409,
            "We couldn't restore your earlier progress — please upload your CV again to restart onboarding.",
        )


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
    try:
        cv_text = read_cv_upload(file.filename, content)
        validate_is_cv(cv_text)
    except CVReadError as exc:
        raise HTTPException(exc.status_code, str(exc))

    # A fresh upload always starts a clean run: forget any stale graph thread
    # and any half-finished wizard output from a previous attempt.
    drop_thread(_graph, current_user)
    current_user.cv_raw_text = cv_text
    current_user.intro_text = None
    current_user.suggested_track = None
    current_user.suggested_track_reasoning = None
    current_user.suggested_agent_ids_json = None
    db.commit()

    initial_state = {
        "user_id": current_user.id,
        "cv_raw_text": cv_text,
        "catalog": catalog_as_dicts(db),
    }
    result = _graph.invoke(initial_state, config=_config(current_user))
    payload = _interrupt_payload(result)

    # Saved (answers still empty) so a closed tab can bring the same
    # questions back instead of asking the agent for new ones.
    current_user.onboarding_qa_json = [{"question": q, "answer": None} for q in payload["questions"]]
    current_user.onboarding_stage = OnboardingStage.QA
    db.commit()
    return {"questions": payload["questions"]}


@router.post("/qa", response_model=OnboardingTrackOut)
def submit_qa(
    payload: OnboardingQASubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_stage(current_user, OnboardingStage.QA)
    _prepare_thread(current_user, db, OnboardingStage.QA)
    result = _graph.invoke(
        Command(resume={"answers": payload.answers, "intro_text": payload.intro_text}),
        config=_config(current_user),
    )
    data = _interrupt_payload(result)

    current_user.intro_text = payload.intro_text
    current_user.onboarding_qa_json = result.get("questions", [])
    current_user.suggested_track = TrackEnum(result["suggested_track"])
    current_user.suggested_track_reasoning = data["reasoning"]
    current_user.onboarding_stage = OnboardingStage.TRACK
    db.commit()
    return {"suggested_track": data["suggested_track"], "reasoning": data["reasoning"]}


@router.post("/track", response_model=OnboardingAgentsOut)
def approve_track(
    payload: OnboardingTrackApprove,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_stage(current_user, OnboardingStage.TRACK)
    _prepare_thread(current_user, db, OnboardingStage.TRACK)
    result = _graph.invoke(
        Command(resume={"track": payload.track.value if payload.track else None}),
        config=_config(current_user),
    )
    data = _interrupt_payload(result)

    current_user.track = TrackEnum(result["approved_track"])
    current_user.track_confirmed = True
    current_user.suggested_agent_ids_json = list(data["suggested_agent_ids"])
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
    # COMPLETE is allowed too: re-submitting is how a graduate edits their
    # roster after finishing (the idempotent replace below).
    _require_stage(current_user, OnboardingStage.AGENTS, OnboardingStage.COMPLETE)
    _prepare_thread(current_user, db, OnboardingStage.AGENTS)
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


@router.get("/resume", response_model=OnboardingResumeOut)
def resume_onboarding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """What the wizard needs to re-draw the step the graduate stopped on —
    read purely from what was saved at each pause, so it costs no LLM call and
    works after a closed tab, a server restart or a deploy. `resumable: false`
    means "nothing to restore, start at the CV step"."""
    stage = current_user.onboarding_stage
    out: dict = {"onboarding_stage": stage, "resumable": can_resume(current_user, stage)}
    if not out["resumable"]:
        return out
    if stage == OnboardingStage.QA:
        out["questions"] = [item["question"] for item in current_user.onboarding_qa_json]
        out["intro_text"] = current_user.intro_text
    elif stage == OnboardingStage.TRACK:
        out["suggested_track"] = current_user.suggested_track
        out["reasoning"] = current_user.suggested_track_reasoning
    elif stage == OnboardingStage.AGENTS:
        ids = current_user.suggested_agent_ids_json or []
        out["suggested_agents"] = db.query(AgentCatalog).filter(AgentCatalog.id.in_(ids)).all() if ids else []
    return out


@router.post("/reset", response_model=OnboardingStateOut)
def reset_onboarding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send the graduate back to the start of onboarding so they can run
    it again — clears the wizard's own state (stage, the pending track
    suggestion, the Q&A log, the confirmation flag) but deliberately
    leaves their CV, their selected agents, and any project/tasks alone:
    redoing onboarding is for re-answering the intake, not wiping the
    account. Also the safe fix for pre-Stage-2 users whose stage was
    never properly initialized and who'd otherwise be stuck on the
    'already done' screen forever."""
    drop_thread(_graph, current_user)
    current_user.onboarding_stage = OnboardingStage.CV
    current_user.track_confirmed = False
    current_user.suggested_track = None
    current_user.suggested_track_reasoning = None
    current_user.suggested_agent_ids_json = None
    current_user.onboarding_qa_json = []
    db.commit()
    db.refresh(current_user)
    return current_user
