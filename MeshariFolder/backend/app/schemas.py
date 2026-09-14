from datetime import datetime

from pydantic import BaseModel, EmailStr, ConfigDict

from app.models import (
    AgentType,
    OnboardingStage,
    ProjectStatus,
    ProjectSource,
    ReviewKind,
    SenderType,
    TaskStatus,
    TrackEnum,
    WeekStatus,
)


# ---- Auth ----

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---- User ----

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    full_name: str
    track: TrackEnum
    is_active: bool
    created_at: datetime
    has_cv: bool


class CVIntake(BaseModel):
    cv_raw_text: str


# ---- Stage 2 onboarding (docs/STAGE2_ONBOARDING_FLOW.md) ----

class OnboardingQuestionsOut(BaseModel):
    questions: list[str]


class OnboardingQASubmit(BaseModel):
    # "0" -> answer text, keyed by question index as a string. Omit an
    # index (or send "") to skip that question.
    answers: dict[str, str] = {}
    intro_text: str | None = None


class OnboardingTrackOut(BaseModel):
    suggested_track: TrackEnum
    reasoning: str


class OnboardingTrackApprove(BaseModel):
    # None (or omitted) = approve the suggestion as-is. Set to override.
    track: TrackEnum | None = None


class AgentCatalogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str


class OnboardingAgentsOut(BaseModel):
    suggested_agents: list[AgentCatalogOut]


class OnboardingAgentsApprove(BaseModel):
    agent_ids: list[str] = []


class OnboardingCompleteOut(BaseModel):
    track: TrackEnum
    agents: list[AgentCatalogOut]


class OnboardingStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    onboarding_stage: OnboardingStage
    track: TrackEnum
    track_confirmed: bool
    suggested_track: TrackEnum | None = None


# ---- Task ----

class TaskCreate(BaseModel):
    title: str
    description: str
    user_id: str


class TaskStatusUpdate(BaseModel):
    status: TaskStatus
    github_link: str | None = None


class TaskMessageCreate(BaseModel):
    content: str
    # Only set when an agent posts; omitted/None means the human user posted.
    agent_type: AgentType | None = None


class TaskMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sender_type: SenderType
    agent_type: AgentType | None
    content: str
    created_at: datetime


class TaskAttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    status: TaskStatus
    github_link: str | None
    submission_text: str | None
    attachments: list[TaskAttachmentOut] = []
    created_by_agent: AgentType
    # week_id/deadline are None for tasks outside the weekly-cycle flow
    # (the original flat model, or ad hoc/admin-created tasks).
    week_id: str | None
    deadline: datetime | None
    submitted_at: datetime | None
    completed_at: datetime | None
    # None until both deadline and completed_at exist — see Task.is_late.
    is_late: bool | None
    created_at: datetime
    updated_at: datetime


class TaskDetailOut(TaskOut):
    messages: list[TaskMessageOut] = []


# ---- Project & Week (weekly-cycle flow — see docs/STAGE1_PRODUCT_FLOW.md).
# No creation endpoints yet; these exist so the shape is ready once the
# orchestration that populates them (start a week, release the next
# subtask, run the end-of-week cascade) lands. ----

class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    status: ProjectStatus
    source: ProjectSource
    created_at: datetime
    updated_at: datetime


class OwnProjectCreate(BaseModel):
    title: str
    description: str


class SubtaskPlanOut(BaseModel):
    """One entry from Week.subtasks_plan_json — the Manager's upfront plan
    for a subtask, before it becomes a real Task row. Field names match
    the JSON exactly (title/description/deadline) so this maps onto it
    automatically via from_attributes; see models.py's Week docstring."""

    title: str
    description: str
    deadline: datetime


class WeekOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    week_number: int
    status: WeekStatus
    big_task_title: str
    big_task_description: str
    next_subtask_index: int
    # Named to match the ORM column exactly (Week.subtasks_plan_json) so
    # Pydantic's from_attributes picks it up with no extra mapping code —
    # the frontend renames it to something friendlier on its side.
    subtasks_plan_json: list[SubtaskPlanOut]
    started_at: datetime
    target_end_at: datetime
    ended_at: datetime | None


class ProjectDetailOut(ProjectOut):
    weeks: list[WeekOut] = []


# ---- Review & Employee File (agent logic output — see app/agents/) ----

class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str | None
    week_id: str | None
    agent_type: AgentType
    kind: ReviewKind
    content: str
    # Mentor (TASK_REVIEW): {verdict, categories, comments} — see
    # agents/tools.py's SUBMIT_REVIEW_TOOL. HR SKILLS_ROLLUP:
    # {reviewed_task_count, average_score}. WEEK_PROGRESS/BEHAVIORAL:
    # contract not yet defined — lands with the end-of-week cascade.
    metrics_json: dict | None
    created_at: datetime


class EmployeeFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Each holds {} until HR's first rollup, then {"items": [...]} — see
    # agents/hr.py's storage note.
    skills_json: dict
    strengths_json: dict
    growth_areas_json: dict
    summary_text: str | None
    updated_at: datetime


class DashboardOut(BaseModel):
    """At-a-glance stats for the logged-in home dashboard — assembled
    server-side by app/dashboard.py so the frontend makes one call, not
    five. Rates/averages are None (not 0) when there's nothing to judge
    yet, so the UI can show '—' instead of a misleading 0%."""

    tasks_completed: int
    tasks_total: int
    on_time_rate: float | None
    average_score: float | None
    reviews_count: int
    weeks_completed: int
    weeks_total: int
    has_active_project: bool


# ---- Meeting Room (direct agent chat — see app/agents/meeting.py) ----

class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_type: AgentType
    sender_type: SenderType
    content: str
    created_at: datetime


class ChatSend(BaseModel):
    content: str
