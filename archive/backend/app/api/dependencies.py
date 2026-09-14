from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.domain import Organization, Task, User


def owned_task(db: Session, task_id: str, user: User) -> Task:
    task = db.get(Task, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(404, "المهمة غير موجودة")
    return task


def recruiter_org(db: Session, organization_id: str, user: User) -> Organization:
    organization = db.get(Organization, organization_id)
    if not organization or organization.owner_id != user.id:
        raise HTTPException(404, "الشركة غير موجودة")
    return organization
