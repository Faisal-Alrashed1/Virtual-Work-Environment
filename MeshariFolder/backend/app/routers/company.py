"""
Stage 3's company side (docs/STAGE3_COMPANY_RAG.md): a company account
registers or joins via a shared org join_code, defines free-text job
titles, uploads materials per job title, and can query that job title's
knowledge base — the RAG system app/rag.py builds. Reuses the exact same
auth system as everything else: a company rep is a User row like any
other (account_type=COMPANY), logs in through the same POST /auth/login,
carries the same bearer token. Nothing here is a parallel auth stack.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
import smtplib

from app.agents.graph.cv_parsing import CVReadError, read_cv_upload
from app.auth import get_current_user, hash_password
from app.database import get_db
from app.email import EmailNotConfigured, send_invitation_email
from app.materials import MAX_MATERIALS_FILES, combine_materials
from app.company_roster import student_detail, student_summary
from app.models import (
    AccountType,
    CompanyProject,
    CompanyRole,
    Invitation,
    InvitationStatus,
    JobTitle,
    KnowledgeMaterial,
    Organization,
    User,
)
from app.rag import ingest_material, retrieve
from app.schemas import (
    CompanyProjectOut,
    CompanyRegister,
    CompanyRegisterOut,
    CompanyStudentDetailOut,
    CompanyStudentOut,
    CompanyStudentWeekOut,
    InvitationCreate,
    InvitationOut,
    JobTitleCreate,
    JobTitleOut,
    KnowledgeMaterialOut,
    OrganizationOut,
    RAGChunkOut,
    RAGQueryRequest,
    RAGQueryResult,
    UserOut,
)

router = APIRouter(prefix="/company", tags=["company"])

MAX_MATERIAL_FILES = 5
# Generous — unlike own-project's materials cap (task_bank.MAX_MATERIALS_CHARS,
# 6000 chars, meant to fit inside one prompt), this gets chunked and
# embedded rather than pasted whole into a prompt, so there's no prompt-
# budget reason to cap it tightly. Still capped, for sane upload/embedding
# cost on a single call.
MAX_MATERIAL_CHARS = 200_000


def get_current_company_user(current_user: User = Depends(get_current_user)) -> User:
    """Gate for every endpoint below except register itself. A student
    account hitting any of these gets a clean 403, not a confusing
    empty result."""
    if current_user.account_type != AccountType.COMPANY:
        raise HTTPException(status_code=403, detail="This is a company-account endpoint.")
    return current_user


def require_company_role(*roles: CompanyRole):
    """Gate for the handful of company actions that carry real
    organizational weight — everything else in this router stays open to
    any company role (see get_current_company_user) since over-
    restricting a small company's day-to-day use adds friction without
    much real benefit. Two things are scoped: sending an invitation
    (ADMIN/HR — a hiring decision) and defining a real company project
    (ADMIN/TECH_LEAD — a technical/scope decision). Factory, not a plain
    dependency, so one function covers both role sets:
    Depends(require_company_role(CompanyRole.ADMIN, CompanyRole.HR))."""

    def dependency(current_user: User = Depends(get_current_company_user)) -> User:
        if current_user.company_role not in roles:
            allowed = ", ".join(r.value for r in roles)
            raise HTTPException(
                status_code=403,
                detail=f"This action is limited to these roles: {allowed}.",
            )
        return current_user

    return dependency


def _get_org_job_title(db: Session, user: User, job_title_id: str) -> JobTitle:
    job_title = db.get(JobTitle, job_title_id)
    if not job_title or job_title.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Job title not found.")
    return job_title


@router.post("/register", response_model=CompanyRegisterOut, status_code=201)
def register_company(payload: CompanyRegister, db: Session = Depends(get_db)):
    """Two shapes: found a new company (company_name required — becomes
    its first ADMIN) or join an existing one by join_code (role
    required). No email/invite system exists in this app, so "join" is
    self-serve: anyone with the code picks their own role. That's a
    deliberate MVP simplification for a bootcamp demo, not a security
    boundary — see docs/STAGE3_COMPANY_RAG.md."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    if payload.join_code:
        org = db.query(Organization).filter(Organization.join_code == payload.join_code).first()
        if not org:
            raise HTTPException(status_code=404, detail="No company found for that join code.")
        if not payload.role:
            raise HTTPException(status_code=400, detail="role is required when joining with a join_code.")
        role = payload.role
    else:
        if not payload.company_name or not payload.company_name.strip():
            raise HTTPException(
                status_code=400, detail="company_name is required to register a new company."
            )
        org = Organization(name=payload.company_name.strip(), field=(payload.field or "").strip() or None)
        db.add(org)
        db.flush()  # org.id, before the user references it
        role = CompanyRole.ADMIN

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        account_type=AccountType.COMPANY,
        organization_id=org.id,
        company_role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(org)
    return CompanyRegisterOut(user=UserOut.model_validate(user), organization=org)


@router.get("/me", response_model=OrganizationOut)
def read_my_company(current_user: User = Depends(get_current_company_user), db: Session = Depends(get_db)):
    org = db.get(Organization, current_user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Company not found.")
    return org


@router.post("/job-titles", response_model=JobTitleOut, status_code=201)
def create_job_title(
    payload: JobTitleCreate,
    current_user: User = Depends(get_current_company_user),
    db: Session = Depends(get_db),
):
    """Free text, on purpose — any company in any field can use this, not
    just IT (see the Q&A behind docs/STAGE3_COMPANY_RAG.md). Any company
    role can create one today; not yet gated to admin/HR specifically."""
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title can't be empty.")
    job_title = JobTitle(
        organization_id=current_user.organization_id,
        title=title,
        description=payload.description,
        created_by_user_id=current_user.id,
    )
    db.add(job_title)
    db.commit()
    db.refresh(job_title)
    return job_title


@router.get("/job-titles", response_model=list[JobTitleOut])
def list_job_titles(
    current_user: User = Depends(get_current_company_user), db: Session = Depends(get_db)
):
    return (
        db.query(JobTitle)
        .filter(JobTitle.organization_id == current_user.organization_id)
        .order_by(JobTitle.created_at.desc())
        .all()
    )


@router.get("/job-titles/{job_title_id}", response_model=JobTitleOut)
def get_job_title(
    job_title_id: str,
    current_user: User = Depends(get_current_company_user),
    db: Session = Depends(get_db),
):
    return _get_org_job_title(db, current_user, job_title_id)


@router.post("/job-titles/{job_title_id}/materials", response_model=KnowledgeMaterialOut, status_code=201)
def upload_material(
    job_title_id: str,
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    current_user: User = Depends(get_current_company_user),
    db: Session = Depends(get_db),
):
    """Pasted text or one uploaded file (PDF/Word/plain text — reuses the
    same extraction helper as CV intake and own-project uploads, despite
    its module name; see read_cv_upload). Chunked and embedded
    immediately (app/rag.py.ingest_material) so it's searchable as soon
    as this call returns."""
    job_title = _get_org_job_title(db, current_user, job_title_id)

    if file and file.filename:
        try:
            extracted = read_cv_upload(file.filename, file.file.read())
        except CVReadError as exc:
            raise HTTPException(exc.status_code, f"{file.filename}: {exc}")
        filename = file.filename
    elif text and text.strip():
        extracted = text.strip()
        filename = None
    else:
        raise HTTPException(status_code=400, detail="Provide pasted text or a file.")

    if len(extracted) > MAX_MATERIAL_CHARS:
        raise HTTPException(
            status_code=413, detail=f"Material too large — {MAX_MATERIAL_CHARS} characters max."
        )

    material = ingest_material(
        db,
        organization_id=job_title.organization_id,
        job_title_id=job_title.id,
        uploaded_by_user_id=current_user.id,
        filename=filename,
        extracted_text=extracted,
    )
    return KnowledgeMaterialOut.from_material(material)


@router.get("/job-titles/{job_title_id}/materials", response_model=list[KnowledgeMaterialOut])
def list_materials(
    job_title_id: str,
    current_user: User = Depends(get_current_company_user),
    db: Session = Depends(get_db),
):
    job_title = _get_org_job_title(db, current_user, job_title_id)
    materials = (
        db.query(KnowledgeMaterial)
        .filter(KnowledgeMaterial.job_title_id == job_title.id)
        .order_by(KnowledgeMaterial.created_at.desc())
        .all()
    )
    return [KnowledgeMaterialOut.from_material(m) for m in materials]


@router.post("/job-titles/{job_title_id}/query", response_model=RAGQueryResult)
def query_knowledge_base(
    job_title_id: str,
    payload: RAGQueryRequest,
    current_user: User = Depends(get_current_company_user),
    db: Session = Depends(get_db),
):
    """Runs the actual RAG retrieval for this job title — lets a company
    rep sanity-check what the knowledge base would surface for a given
    question before it's relied on elsewhere (e.g. the Manager planning
    company-sourced tasks, a later piece of Stage 3)."""
    job_title = _get_org_job_title(db, current_user, job_title_id)
    scored = retrieve(db, job_title.id, payload.query, k=payload.k)
    return RAGQueryResult(
        query=payload.query,
        chunks=[
            RAGChunkOut(id=c.id, material_id=c.material_id, content=c.content, score=score)
            for score, c in scored
        ],
    )


# ---------------------------------------------------------------------------
# Company projects — a company's own REAL project, distinct from a
# graduate's own project (Project, source=OWN). This is a template, not
# yet any one student's working project: see routers/invitations.py's
# accept(), which copies title/description/materials_text into an actual
# Project the moment a student accepts an invitation naming it.
# ---------------------------------------------------------------------------


def _get_org_company_project(db: Session, user: User, project_id: str) -> CompanyProject:
    project = db.get(CompanyProject, project_id)
    if not project or project.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.post(
    "/job-titles/{job_title_id}/projects", response_model=CompanyProjectOut, status_code=201
)
def create_company_project(
    job_title_id: str,
    title: str = Form(...),
    description: str = Form(...),
    materials_text: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
    current_user: User = Depends(require_company_role(CompanyRole.ADMIN, CompanyRole.TECH_LEAD)),
    db: Session = Depends(get_db),
):
    """A real project this company actually uses for this role — pasted
    notes and/or uploaded files (same combine_materials helper and cap as
    a graduate's own project, since this becomes a Project's
    materials_text verbatim once a student accepts an invitation naming
    it, and that field feeds plan_week's prompt directly). Limited to
    ADMIN/TECH_LEAD — defining the real work a student will be graded
    against is a technical/scope call, not a hiring one."""
    job_title = _get_org_job_title(db, current_user, job_title_id)
    materials = combine_materials(materials_text, files)
    project = CompanyProject(
        organization_id=job_title.organization_id,
        job_title_id=job_title.id,
        title=title,
        description=description,
        materials_text=materials,
        created_by_user_id=current_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/job-titles/{job_title_id}/projects", response_model=list[CompanyProjectOut])
def list_company_projects(
    job_title_id: str,
    current_user: User = Depends(get_current_company_user),
    db: Session = Depends(get_db),
):
    job_title = _get_org_job_title(db, current_user, job_title_id)
    return (
        db.query(CompanyProject)
        .filter(CompanyProject.job_title_id == job_title.id)
        .order_by(CompanyProject.created_at.desc())
        .all()
    )


@router.get(
    "/job-titles/{job_title_id}/projects/{project_id}", response_model=CompanyProjectOut
)
def get_company_project(
    job_title_id: str,
    project_id: str,
    current_user: User = Depends(get_current_company_user),
    db: Session = Depends(get_db),
):
    project = _get_org_company_project(db, current_user, project_id)
    if project.job_title_id != job_title_id:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


# ---------------------------------------------------------------------------
# Invitations — a company inviting a specific email to a job title, with a
# real company project (company_project_id set) or the ordinary
# Manager-improvised platform track (left None). The student-facing half
# (seeing, consenting to, accepting/declining) lives in routers/invitations.py.
# ---------------------------------------------------------------------------


@router.post(
    "/job-titles/{job_title_id}/invitations", response_model=InvitationOut, status_code=201
)
def create_invitation(
    job_title_id: str,
    payload: InvitationCreate,
    current_user: User = Depends(require_company_role(CompanyRole.ADMIN, CompanyRole.HR)),
    db: Session = Depends(get_db),
):
    """Invite invited_email to work under this job title. Sends a real
    email if SMTP is configured (app/email.py); if it isn't, or the send
    fails for any reason, the invitation is still created — the student
    can always find it via GET /invitations/mine regardless, and
    response.email_sent tells the company honestly whether it went out.
    Limited to ADMIN/HR — who to bring on is a hiring decision, not a
    technical one."""
    job_title = _get_org_job_title(db, current_user, job_title_id)
    company_project = None
    if payload.company_project_id:
        company_project = _get_org_company_project(db, current_user, payload.company_project_id)
        if company_project.job_title_id != job_title.id:
            raise HTTPException(
                status_code=400, detail="That project belongs to a different job title."
            )
    invitation = Invitation(
        organization_id=job_title.organization_id,
        job_title_id=job_title.id,
        company_project_id=company_project.id if company_project else None,
        invited_email=payload.invited_email.lower(),
        invited_by_user_id=current_user.id,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    org = db.get(Organization, job_title.organization_id)
    try:
        send_invitation_email(
            to_email=invitation.invited_email,
            company_name=org.name if org else "A company",
            job_title=job_title.title,
            project_title=company_project.title if company_project else None,
        )
        invitation.email_sent = True
        db.commit()
        db.refresh(invitation)
    except EmailNotConfigured:
        pass  # no SMTP set up — the invitation itself still exists
    except (smtplib.SMTPException, OSError, TimeoutError):
        pass  # a real send failure never blocks the invitation itself

    return InvitationOut(
        id=invitation.id,
        job_title_id=job_title.id,
        job_title=job_title.title,
        company_project_id=company_project.id if company_project else None,
        company_project_title=company_project.title if company_project else None,
        invited_email=invitation.invited_email,
        status=invitation.status,
        email_sent=invitation.email_sent,
        created_at=invitation.created_at,
        responded_at=invitation.responded_at,
    )


@router.get("/invitations", response_model=list[InvitationOut])
def list_invitations(
    current_user: User = Depends(get_current_company_user), db: Session = Depends(get_db)
):
    """Every invitation this company has sent, across all job titles, with
    its current status — pending, accepted, or declined."""
    rows = (
        db.query(Invitation)
        .filter(Invitation.organization_id == current_user.organization_id)
        .order_by(Invitation.created_at.desc())
        .all()
    )
    job_titles = {
        jt.id: jt.title
        for jt in db.query(JobTitle).filter(JobTitle.organization_id == current_user.organization_id)
    }
    projects = {
        cp.id: cp.title
        for cp in db.query(CompanyProject).filter(
            CompanyProject.organization_id == current_user.organization_id
        )
    }
    return [
        InvitationOut(
            id=inv.id,
            job_title_id=inv.job_title_id,
            job_title=job_titles.get(inv.job_title_id, ""),
            company_project_id=inv.company_project_id,
            company_project_title=projects.get(inv.company_project_id) if inv.company_project_id else None,
            invited_email=inv.invited_email,
            status=inv.status,
            email_sent=inv.email_sent,
            created_at=inv.created_at,
            responded_at=inv.responded_at,
        )
        for inv in rows
    ]


# ---------------------------------------------------------------------------
# The company's view into a student they've hired: a live roster
# (GET /students) and, per student, the same week-by-week reviews the
# Manager/HR weekly cycle already produces (GET /students/{id}) — this IS
# the "end-of-week report", not a second reporting pipeline. Reached via
# accepted invitations: an invited student's account (User.organization_id,
# set in routers/invitations.py's accept()) is the join key, not
# Project.organization_id — a platform-track invitation (no named company
# project) still produces a real Project once the student calls
# assign-task, and that path has no reason to know about organizations.
# Scope is exactly what INVITATION_DATA_NOTICE promised: this project's
# tasks/submissions and reviews, nothing about the student beyond that.
#
# The actual data-building lives in app/company_roster.py, shared with
# the student's own transparency view (routers/invitations.py) — see
# that module's docstring for why.
# ---------------------------------------------------------------------------


@router.get("/students", response_model=list[CompanyStudentOut])
def list_students(
    current_user: User = Depends(get_current_company_user), db: Session = Depends(get_db)
):
    """Everyone who has actually accepted an invitation from this
    company — a pending or declined invitation isn't a student yet."""
    invitations = (
        db.query(Invitation)
        .filter(
            Invitation.organization_id == current_user.organization_id,
            Invitation.status == InvitationStatus.ACCEPTED,
        )
        .order_by(Invitation.responded_at.desc())
        .all()
    )
    out = []
    for invitation in invitations:
        student = db.query(User).filter(User.email == invitation.invited_email).first()
        if student:
            out.append(student_summary(db, invitation, student))
    return out


@router.get("/students/{invitation_id}", response_model=CompanyStudentDetailOut)
def get_student_detail(
    invitation_id: str,
    current_user: User = Depends(get_current_company_user),
    db: Session = Depends(get_db),
):
    """The week-by-week detail behind one roster entry — each week's tasks
    and whichever end-of-week reviews (Manager's WEEK_PROGRESS, HR's
    BEHAVIORAL) exist for it so far."""
    invitation = db.get(Invitation, invitation_id)
    if not invitation or invitation.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Student not found.")
    if invitation.status != InvitationStatus.ACCEPTED:
        raise HTTPException(status_code=404, detail="This invitation hasn't been accepted yet.")
    student = db.query(User).filter(User.email == invitation.invited_email).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    return student_detail(db, invitation, student)
