from pydantic import BaseModel, EmailStr, HttpUrl
from app.models.domain import TaskStatus, UserRole


class Register(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.learner


class Login(BaseModel):
    email: EmailStr
    password: str


class ManualCVIn(BaseModel):
    education: str
    skills: list[str]
    projects: str = ""
    experience: str = ""
    target_role: str = "Web Developer"


class ChatIn(BaseModel):
    body: str
    task_id: str | None = None


class LearningGoalIn(BaseModel):
    goal: str


class ProfileConfirm(BaseModel):
    corrections: str = ""


class StatusIn(BaseModel):
    status: TaskStatus


class SubmissionIn(BaseModel):
    github_url: HttpUrl | None = None
    code: str | None = None
    language: str = "python"
    summary: str
    challenges: str = ""


class OrganizationIn(BaseModel):
    name: str


class KnowledgeIn(BaseModel):
    name: str
    content: str
    attested_synthetic: bool = False


class CampaignIn(BaseModel):
    organization_id: str
    title: str
    job_role: str


class CampaignTaskIn(BaseModel):
    candidate_user_id: str
    title: str
    brief: str
    acceptance_criteria: list[str]
    difficulty: int = 1


class InterventionIn(BaseModel):
    body: str


class DecisionIn(BaseModel):
    decision: str
    notes: str = ""
