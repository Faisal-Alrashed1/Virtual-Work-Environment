from pydantic import BaseModel, EmailStr, Field, HttpUrl, model_validator
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


class ManualCVIn(BaseModel):
    education: str = Field(min_length=2, max_length=1000)
    skills: list[str] = Field(min_length=1, max_length=30)
    projects: str = Field(default="", max_length=4000)
    experience: str = Field(default="", max_length=4000)
    target_role: str = Field(default="Web Developer", min_length=2, max_length=200)


class ProfileConfirm(BaseModel):
    corrections: str = ""


class LearningGoalIn(BaseModel):
    goal: str = Field(min_length=10, max_length=4000)


class ChatIn(BaseModel):
    body: str = Field(min_length=1, max_length=8000)
    task_id: str | None = None


class SubmissionIn(BaseModel):
    github_url: HttpUrl | None = None
    code: str | None = Field(default=None, max_length=50_000)
    language: str = Field(default="python", max_length=50)
    summary: str = Field(min_length=10)
    challenges: str = ""

    @model_validator(mode="after")
    def require_one_source(self):
        if not self.github_url and not (self.code and self.code.strip()):
            raise ValueError("اكتب الكود أو أضف رابط GitHub")
        if self.github_url and self.code and self.code.strip():
            raise ValueError("اختر طريقة تسليم واحدة فقط")
        return self


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
