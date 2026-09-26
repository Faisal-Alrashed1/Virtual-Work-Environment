"""
Builds "what a company can see about a student" — one set of functions,
two callers: the company's own roster view (routers/company.py) and the
student's own transparency view (routers/invitations.py's visibility
endpoint). Living here, shared, is the point: a student checking "what
do they actually see" gets the literal same data the company's own
endpoint returns, not a separately-maintained approximation that could
quietly drift out of sync with it. See docs/STAGE3_COMPANY_RAG.md.
"""
from sqlalchemy.orm import Session

from app.models import (
    CompanyProject,
    Invitation,
    JobTitle,
    Project,
    ProjectStatus,
    Review,
    ReviewKind,
    User,
    WeekStatus,
)
from app.schemas import CompanyStudentDetailOut, CompanyStudentOut, CompanyStudentWeekOut


def student_project(db: Session, student: User) -> Project | None:
    return (
        db.query(Project)
        .filter(Project.user_id == student.id, Project.status == ProjectStatus.ACTIVE)
        .order_by(Project.created_at.desc())
        .first()
    )


def task_counts(project: Project | None) -> dict[str, int]:
    counts = {"todo": 0, "in_progress": 0, "submitted": 0, "reviewed": 0}
    if not project:
        return counts
    for week in project.weeks:
        for task in week.tasks:
            counts[task.status.value] += 1
    return counts


def current_week_number(project: Project | None) -> int | None:
    if not project or not project.weeks:
        return None
    active = next((w for w in project.weeks if w.status == WeekStatus.ACTIVE), None)
    if active:
        return active.week_number
    return max(w.week_number for w in project.weeks)


def student_summary(db: Session, invitation: Invitation, student: User) -> CompanyStudentOut:
    job_title = db.get(JobTitle, invitation.job_title_id)
    company_project = (
        db.get(CompanyProject, invitation.company_project_id)
        if invitation.company_project_id
        else None
    )
    project = student_project(db, student)
    return CompanyStudentOut(
        invitation_id=invitation.id,
        student_name=student.full_name,
        student_email=student.email,
        job_title=job_title.title if job_title else "",
        company_project_title=company_project.title if company_project else None,
        project_title=project.title if project else None,
        project_status=project.status if project else None,
        current_week_number=current_week_number(project),
        task_counts=task_counts(project),
    )


def student_detail(db: Session, invitation: Invitation, student: User) -> CompanyStudentDetailOut:
    """summary fields plus each week's tasks and whichever end-of-week
    reviews (Manager's WEEK_PROGRESS, HR's BEHAVIORAL) exist for it so
    far — the same shape GET /company/students/{id} returns."""
    summary = student_summary(db, invitation, student)
    project = student_project(db, student)
    weeks_out: list[CompanyStudentWeekOut] = []
    if project:
        for week in sorted(project.weeks, key=lambda w: w.week_number):
            week_reviews = (
                db.query(Review)
                .filter(
                    Review.week_id == week.id,
                    Review.kind.in_([ReviewKind.WEEK_PROGRESS, ReviewKind.BEHAVIORAL]),
                )
                .order_by(Review.created_at)
                .all()
            )
            weeks_out.append(
                CompanyStudentWeekOut(
                    week_number=week.week_number,
                    status=week.status,
                    started_at=week.started_at,
                    target_end_at=week.target_end_at,
                    ended_at=week.ended_at,
                    tasks=week.tasks,
                    reviews=week_reviews,
                )
            )
    return CompanyStudentDetailOut(**summary.model_dump(), weeks=weeks_out)
