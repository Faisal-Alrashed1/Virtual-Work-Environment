from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Project, ProjectSource, ProjectStatus, User
from app.schemas import OwnProjectCreate, ProjectDetailOut, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/me", response_model=ProjectDetailOut)
def get_my_project(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    The graduate's active Project with all its Weeks — powers the
    node-based home board (Project-Summary.md). 404 until the first call
    to POST /agents/manager/assign-task bootstraps one (or until
    POST /projects/own is used instead — see below).
    """
    project = (
        db.query(Project)
        .filter(Project.user_id == current_user.id, Project.status == ProjectStatus.ACTIVE)
        .order_by(Project.created_at.desc())
        .first()
    )
    if not project:
        raise HTTPException(
            status_code=404,
            detail="No project yet — call POST /agents/manager/assign-task first.",
        )
    return project


@router.post("/own", response_model=ProjectOut, status_code=201)
def create_own_project(
    payload: OwnProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Stage 2 (docs/STAGE2_OWN_PROJECT.md): lets the graduate bring their
    own project instead of the Manager improvising one — confirmed with
    Meshari as an optional alternative, not the default. Must be called
    before the first POST /agents/manager/assign-task: weekly_cycle.py's
    bootstrap step only ever improvises a project when the graduate
    doesn't already have an active one, so creating one here first makes
    the very next assign-task call plan straight into it instead.

    No changes needed in manager.plan_week to make this work — it already
    only reads project.title/description, which read the same whether the
    Manager or the graduate wrote them.
    """
    existing = (
        db.query(Project)
        .filter(Project.user_id == current_user.id, Project.status == ProjectStatus.ACTIVE)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="You already have an active project — this only works before your first task.",
        )

    project = Project(
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        source=ProjectSource.OWN,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project
