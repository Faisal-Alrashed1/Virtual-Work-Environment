from pydantic import BaseModel, EmailStr, Field, HttpUrl
from app.models.domain import UserRole, TaskStatus


class Register(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8)
    role: UserRole = UserRole.learner


class Login(BaseModel):
    email: EmailStr
    password: str


class DiagnosticMessage(BaseModel):
    message: str = Field(min_length=2, max_length=4000)


class ProfileConfirm(BaseModel):
    corrections: str = ""


class LearningGoalIn(BaseModel):
    goal: str = Field(min_length=10, max_length=4000)


class ChatIn(BaseModel):
    body: str = Field(min_length=1, max_length=8000)
    task_id: str | None = None


class SubmissionIn(BaseModel):
    github_url: HttpUrl
    summary: str = Field(min_length=10)
    challenges: str = ""


class StatusIn(BaseModel):
    status: TaskStatus


class OrganizationIn(BaseModel):
    name: str = Field(min_length=2)


class KnowledgeIn(BaseModel):
    name: str
    content: str = Field(min_length=50)
    attested_synthetic: bool


class CampaignTaskIn(BaseModel):
    candidate_user_id: str
    title: str
    brief: str
    acceptance_criteria: list[str]
    difficulty: int = Field(ge=1, le=5)


class CampaignIn(BaseModel):
    organization_id: str
    title: str = Field(min_length=3)
    job_role: str = Field(min_length=2)


class InterventionIn(BaseModel):
    body: str = Field(min_length=2, max_length=4000)


class DecisionIn(BaseModel):
    decision: str
    notes: str
