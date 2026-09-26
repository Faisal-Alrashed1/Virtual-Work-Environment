"""
Student-facing side of Stage 3's invitations (docs/STAGE3_COMPANY_RAG.md):
seeing what's been sent to your email, giving informed consent, and
accepting (which affiliates you with the company and, if a real company
project was named, creates your actual Project from it) or declining.
The company-facing half — creating an invitation in the first place —
lives in routers/company.py.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.company_roster import student_detail
from app.database import get_db
from app.models import (
    AccountType,
    CompanyProject,
    Invitation,
    InvitationStatus,
    JobTitle,
    Organization,
    Project,
    ProjectSource,
    ProjectStatus,
    User,
)
from app.schemas import (
    INVITATION_DATA_NOTICE,
    CompanyStudentDetailOut,
    InvitationAccept,
    InvitationDetailOut,
)

router = APIRouter(prefix="/invitations", tags=["invitations"])


def _get_my_invitation(db: Session, user: User, invitation_id: str) -> Invitation:
    invitation = db.get(Invitation, invitation_id)
    if not invitation or invitation.invited_email.lower() != user.email.lower():
        raise HTTPException(status_code=404, detail="Invitation not found.")
    return invitation


def _detail(db: Session, invitation: Invitation) -> InvitationDetailOut:
    org = db.get(Organization, invitation.organization_id)
    job_title = db.get(JobTitle, invitation.job_title_id)
    company_project = (
        db.get(CompanyProject, invitation.company_project_id)
        if invitation.company_project_id
        else None
    )
    org_name = org.name if org else "This company"
    return InvitationDetailOut(
        id=invitation.id,
        organization_name=org_name,
        job_title=job_title.title if job_title else "",
        company_project_title=company_project.title if company_project else None,
        status=invitation.status,
        created_at=invitation.created_at,
        responded_at=invitation.responded_at,
        data_shared_notice=INVITATION_DATA_NOTICE.format(company=org_name),
    )


@router.get("/mine", response_model=list[InvitationDetailOut])
def my_invitations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Every invitation sent to this account's email — pending, accepted,
    or declined, oldest responded ones included so a student can see
    their own history."""
    rows = (
        db.query(Invitation)
        .filter(Invitation.invited_email == current_user.email.lower())
        .order_by(Invitation.created_at.desc())
        .all()
    )
    return [_detail(db, inv) for inv in rows]


@router.post("/{invitation_id}/accept", response_model=InvitationDetailOut)
def accept_invitation(
    invitation_id: str,
    payload: InvitationAccept,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Requires explicit consent (payload.consent must be true) — the
    student has to actually agree to what INVITATION_DATA_NOTICE says the
    company will be able to see, not just click a single 'Join' button.
    Confirmed with Meshari as a requirement, not optional UX.

    Affiliates the student with the company (User.organization_id) and,
    if the invitation named a real company project, creates the
    student's actual Project from it (title/description/materials_text
    copied over, source stays OWN — see models.Invitation's docstring for
    why this doesn't need a new ProjectSource value). That Project is
    picked up automatically the next time the graduate calls
    POST /agents/manager/assign-task, exactly the way a graduate's own
    project already is — no change to weekly_cycle.py was needed."""
    if current_user.account_type != AccountType.STUDENT:
        raise HTTPException(status_code=403, detail="Only a student account can accept an invitation.")

    invitation = _get_my_invitation(db, current_user, invitation_id)
    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(status_code=400, detail="This invitation has already been responded to.")
    if not payload.consent:
        raise HTTPException(status_code=400, detail="You must consent to continue.")

    if invitation.company_project_id:
        existing = (
            db.query(Project)
            .filter(Project.user_id == current_user.id, Project.status == ProjectStatus.ACTIVE)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail=(
                    "You already have an active project — finish or leave it before "
                    "accepting a company project."
                ),
            )
        company_project = db.get(CompanyProject, invitation.company_project_id)
        db.add(
            Project(
                user_id=current_user.id,
                organization_id=invitation.organization_id,
                title=company_project.title,
                description=company_project.description,
                materials_text=company_project.materials_text,
                source=ProjectSource.OWN,
            )
        )

    current_user.organization_id = invitation.organization_id
    invitation.status = InvitationStatus.ACCEPTED
    invitation.responded_at = datetime.utcnow()
    db.commit()
    db.refresh(invitation)
    return _detail(db, invitation)


@router.post("/{invitation_id}/decline", response_model=InvitationDetailOut)
def decline_invitation(
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.account_type != AccountType.STUDENT:
        raise HTTPException(status_code=403, detail="Only a student account can decline an invitation.")

    invitation = _get_my_invitation(db, current_user, invitation_id)
    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(status_code=400, detail="This invitation has already been responded to.")

    invitation.status = InvitationStatus.DECLINED
    invitation.responded_at = datetime.utcnow()
    db.commit()
    db.refresh(invitation)
    return _detail(db, invitation)


@router.get("/{invitation_id}/visibility", response_model=CompanyStudentDetailOut)
def my_company_visibility(
    invitation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Exactly what the company that sent this invitation can currently
    see about you — not a description of it, the actual data, built by
    the literal same function (app/company_roster.py's student_detail)
    that answers the company's own GET /company/students/{id}. The
    upfront consent notice says what will be shared before you accept;
    this is the ongoing answer to 'is that still true right now' —
    checkable at any time, not just taken on faith once."""
    invitation = _get_my_invitation(db, current_user, invitation_id)
    if invitation.status != InvitationStatus.ACCEPTED:
        raise HTTPException(
            status_code=404, detail="This invitation hasn't been accepted, so nothing has been shared yet."
        )
    return student_detail(db, invitation, current_user)
