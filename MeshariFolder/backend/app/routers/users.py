from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.agents.graph.cv_parsing import CVReadError, read_cv_upload, validate_is_cv
from app.auth import get_current_user, hash_password, verify_password
from app.database import get_db
from app.dashboard import build_dashboard
from app.models import AgentCatalog, OnboardingStage, Review, User, UserAgent
from app.schemas import AgentCatalogOut, CVIntake, DashboardOut, EmployeeFileOut, ReviewOut, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The settings page's profile form: rename yourself, change your
    password, or both in one call. A password change needs
    current_password to match what's on file — same as any ordinary
    settings page — and is refused (400) otherwise, without touching
    full_name even if that part of the payload was valid."""
    if payload.new_password is not None:
        if not payload.current_password or not verify_password(
            payload.current_password, current_user.hashed_password
        ):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")
        if len(payload.new_password) < 8:
            raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")
        current_user.hashed_password = hash_password(payload.new_password)

    if payload.full_name is not None:
        name = payload.full_name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name can't be empty.")
        current_user.full_name = name

    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/me/agents", response_model=list[AgentCatalogOut])
def list_my_agents(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Stage 2 (docs/STAGE2_TEAM_AND_ORIENTATION.md): the graduate's
    selected *optional* agents only — Manager/Mentor/HR are always on the
    team and aren't stored per-user, so they're not in this list. Powers
    the board's agents graph and the orientation screen, both of which
    otherwise only knew about the fixed default three."""
    return (
        db.query(AgentCatalog)
        .join(UserAgent, UserAgent.agent_catalog_id == AgentCatalog.id)
        .filter(UserAgent.user_id == current_user.id)
        .all()
    )


@router.get("/me/dashboard", response_model=DashboardOut)
def read_dashboard(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """At-a-glance stats for the logged-in home dashboard — one call
    instead of the frontend fetching tasks + reviews + project and doing
    the aggregation itself. See app/dashboard.py."""
    return build_dashboard(db, current_user)


@router.get("/me/employee-file", response_model=EmployeeFileOut)
def read_employee_file(current_user: User = Depends(get_current_user)):
    """The shared record HR maintains and Manager/Mentor read — powers the
    growth view's Employee File snapshot."""
    return current_user.employee_file


@router.get("/me/reviews", response_model=list[ReviewOut])
def list_my_reviews(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Powers the growth view's review timeline — both per-task Mentor
    reviews and HR's periodic rollups, oldest first."""
    return (
        db.query(Review)
        .filter(Review.user_id == current_user.id)
        .order_by(Review.created_at)
        .all()
    )


@router.post("/me/cv", response_model=UserOut)
def submit_cv(
    payload: CVIntake,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stores the raw CV text at intake. Structured parsing into
    employee_file.skills_json is owned by the AI/Agents track (Manager uses
    it to calibrate the first task's difficulty) — this endpoint just
    captures the raw input so that work can plug in without a schema change.
    """
    try:
        validate_is_cv(payload.cv_raw_text)
    except CVReadError as exc:
        raise HTTPException(exc.status_code, str(exc))
    current_user.cv_raw_text = payload.cv_raw_text
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/cv/file", response_model=UserOut)
def replace_cv_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Replace the CV with a new file (PDF / Word / text) at any time after
    onboarding — the graduate's own track, team, project and tasks are left
    exactly as they are. Only the stored CV text changes, which is what the
    Manager reads when it plans the *next* week. (POST /onboarding/cv is the
    other CV upload: that one starts onboarding over. See docs/ONBOARDING_RESUME.md.)

    Refused mid-onboarding: the wizard is holding questions and a track
    suggestion generated from the *old* CV, and swapping the text underneath it
    would leave the two disagreeing. Finish the wizard (or restart it) first."""
    if current_user.onboarding_stage in (
        OnboardingStage.QA,
        OnboardingStage.TRACK,
        OnboardingStage.AGENTS,
    ):
        raise HTTPException(
            409,
            "You're partway through onboarding — finish it (or start over) before replacing your CV.",
        )
    try:
        cv_text = read_cv_upload(file.filename, file.file.read())
        validate_is_cv(cv_text)
    except CVReadError as exc:
        raise HTTPException(exc.status_code, str(exc))
    current_user.cv_raw_text = cv_text
    db.commit()
    db.refresh(current_user)
    return current_user
