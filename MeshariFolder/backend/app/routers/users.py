from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.dashboard import build_dashboard
from app.models import AgentCatalog, Review, User, UserAgent
from app.schemas import AgentCatalogOut, CVIntake, DashboardOut, EmployeeFileOut, ReviewOut, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)):
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
    current_user.cv_raw_text = payload.cv_raw_text
    db.commit()
    db.refresh(current_user)
    return current_user
