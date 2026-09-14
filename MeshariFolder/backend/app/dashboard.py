"""
Assembles the logged-in home dashboard's at-a-glance numbers server-side,
so the frontend makes one call instead of five and doesn't recompute
derived stats (averages, streaks, counts) itself. Read-only — pure
aggregation over Task/Review/Project/Week, no writes.

Kept out of routers/users.py so the endpoint stays a thin wrapper and this
logic is unit-testable on its own.
"""
from sqlalchemy.orm import Session

from app.models import (
    Project,
    ProjectStatus,
    Review,
    ReviewKind,
    Task,
    TaskStatus,
    User,
    Week,
    WeekStatus,
)


def _rubric_average(review: Review) -> float | None:
    """Mean of a Mentor task_review's rubric category scores, or None if it
    isn't a scored review. metrics_json shape: {verdict, categories:
    [{score}], comments} — see agents/tools.py's SUBMIT_REVIEW_TOOL."""
    if review.kind != ReviewKind.TASK_REVIEW:
        return None
    cats = (review.metrics_json or {}).get("categories") or []
    scores = [c["score"] for c in cats if "score" in c]
    return sum(scores) / len(scores) if scores else None


def build_dashboard(db: Session, user: User) -> dict:
    tasks: list[Task] = (
        db.query(Task).filter(Task.user_id == user.id).order_by(Task.created_at).all()
    )
    reviews: list[Review] = (
        db.query(Review).filter(Review.user_id == user.id).order_by(Review.created_at).all()
    )
    project: Project | None = (
        db.query(Project)
        .filter(Project.user_id == user.id, Project.status == ProjectStatus.ACTIVE)
        .order_by(Project.created_at.desc())
        .first()
    )

    reviewed = [t for t in tasks if t.status == TaskStatus.REVIEWED]
    # is_late is None until a task has both a deadline and a completion, so
    # "on time" means explicitly not-late among the ones we can actually
    # judge — a task with no deadline never counts against the rate.
    judged = [t for t in reviewed if t.is_late is not None]
    on_time = [t for t in judged if not t.is_late]

    task_scores = [avg for r in reviews if (avg := _rubric_average(r)) is not None]
    weeks_completed = 0
    weeks_total = 0
    if project:
        weeks_total = len(project.weeks)
        weeks_completed = sum(
            1 for w in project.weeks if w.status == WeekStatus.COMPLETED
        )

    return {
        "tasks_completed": len(reviewed),
        "tasks_total": len(tasks),
        # None (not 0) when there's nothing to judge yet, so the UI can show
        # "—" rather than a misleading 100% or 0%.
        "on_time_rate": (len(on_time) / len(judged)) if judged else None,
        "average_score": (sum(task_scores) / len(task_scores)) if task_scores else None,
        "reviews_count": len([r for r in reviews if r.kind == ReviewKind.TASK_REVIEW]),
        "weeks_completed": weeks_completed,
        "weeks_total": weeks_total,
        "has_active_project": project is not None,
    }
