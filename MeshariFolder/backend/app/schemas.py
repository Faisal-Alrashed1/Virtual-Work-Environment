from datetime import datetime

from pydantic import BaseModel, EmailStr, ConfigDict

from app.models import (
    AccountType,
    AgentType,
    CompanyRole,
    InvitationStatus,
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
    # Stage 3: always present, "student" for every pre-Stage-3 user and
    # every ordinary graduate going forward. See docs/STAGE3_COMPANY_RAG.md.
    account_type: AccountType
    company_role: CompanyRole | None
    organization_id: str | None


class UserUpdate(BaseModel):
    """PATCH /users/me — the settings page's profile form. Every field is
    optional so the same endpoint covers "just rename me" and "just
    change my password"; a password change needs current_password to
    match what's on file (see routers/users.py), same as any ordinary
    settings page."""

    full_name: str | None = None
    current_password: str | None = None
    new_password: str | None = None


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


class OnboardingResumeOut(BaseModel):
    """Everything the wizard needs to re-draw the step a graduate stopped on,
    read from the database (no LLM calls). See docs/ONBOARDING_RESUME.md."""

    onboarding_stage: OnboardingStage
    # False -> the wizard should start again from the CV step (nothing to
    # restore: the graduate is at the CV step, has finished, or was mid-wizard
    # before resume state existed).
    resumable: bool
    questions: list[str] = []  # stage "qa"
    intro_text: str | None = None
    suggested_track: TrackEnum | None = None  # stage "track"
    reasoning: str | None = None
    suggested_agents: list[AgentCatalogOut] = []  # stage "agents"


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


class TaskChatRequest(BaseModel):
    """Which agent the graduate is addressing in a task's thread — see
    agents/task_chat.py. Defaults to the Mentor, the day-to-day agent for
    task work; POST /agents/task/{id}/reply 403s if this agent isn't
    available for task chat (not in task_chat.TASK_CHAT_AGENTS) or is an
    optional agent the graduate hasn't added to their roster."""

    agent_type: AgentType = AgentType.MENTOR


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
    # The Mentor bounced this back for changes and it hasn't been resubmitted
    # yet (status alone can't say — see Task.needs_changes), and how many
    # times it has been bounced in total.
    needs_changes: bool = False
    revision_count: int = 0
    # The specialists' discussion of the latest review is still being written, in the
    # background — the thread will keep growing (Task.roundtable_running).
    roundtable_running: bool = False
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
    # The task-bank seed this project was based on (None for your own project).
    seed_id: str | None = None
    # Whether real project materials were provided (own project only) — see
    # app.models.Project.has_materials. Never the text itself.
    has_materials: bool = False
    created_at: datetime
    updated_at: datetime


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


class TeamMessageOut(BaseModel):
    """One turn in the Team Room (app/agents/meeting.py's shared mode) —
    agent_type is None for the graduate's own messages, set to whichever
    teammate replied otherwise."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_type: AgentType | None
    sender_type: SenderType
    content: str
    created_at: datetime


# ---- Stage 3: company accounts + RAG knowledge base ----
# See docs/STAGE3_COMPANY_RAG.md.


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    field: str | None
    join_code: str


class CompanyRegister(BaseModel):
    """POST /company/register. Two shapes in one schema: found a new
    company (company_name required, becomes the org's first ADMIN), or
    join an existing one via its join_code (role required — see
    routers/company.py for which fields are needed for which shape)."""

    email: EmailStr
    password: str
    full_name: str

    # Founding a new company:
    company_name: str | None = None
    field: str | None = None

    # Joining an existing one:
    join_code: str | None = None
    role: CompanyRole | None = None


class CompanyRegisterOut(BaseModel):
    user: UserOut
    organization: OrganizationOut


class JobTitleCreate(BaseModel):
    title: str
    description: str | None = None


class JobTitleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str | None
    created_at: datetime
    material_count: int
    chunk_count: int


class KnowledgeMaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_title_id: str
    filename: str | None
    chunk_count: int
    created_at: datetime
    # A preview, not the whole document — company-facing list views don't
    # need the full text, and a large upload's full text is a lot to ship
    # on every list call.
    preview: str

    @staticmethod
    def from_material(material) -> "KnowledgeMaterialOut":
        text = material.extracted_text
        preview = text if len(text) <= 400 else text[:400] + "..."
        return KnowledgeMaterialOut(
            id=material.id,
            job_title_id=material.job_title_id,
            filename=material.filename,
            chunk_count=material.chunk_count,
            created_at=material.created_at,
            preview=preview,
        )


class RAGQueryRequest(BaseModel):
    query: str
    k: int = 5


class RAGChunkOut(BaseModel):
    id: str
    material_id: str
    content: str
    score: float


class RAGQueryResult(BaseModel):
    query: str
    chunks: list[RAGChunkOut]


class CompanyProjectOut(BaseModel):
    """A company's own real project template (distinct from a graduate's
    own project) — see models.CompanyProject."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    job_title_id: str
    title: str
    description: str
    has_materials: bool
    created_at: datetime


class InvitationCreate(BaseModel):
    invited_email: EmailStr
    # None -> the ordinary Manager-improvised platform track once
    # accepted; set -> the student's Project is created straight from
    # this CompanyProject instead.
    company_project_id: str | None = None


class InvitationOut(BaseModel):
    """The company's own view of an invitation it sent."""

    id: str
    job_title_id: str
    job_title: str
    company_project_id: str | None
    company_project_title: str | None
    invited_email: str
    status: InvitationStatus
    # Whether app/email.py actually sent a real email — False if SMTP
    # isn't configured or a real send failed. Either way the invitation
    # itself exists regardless; this is informational only.
    email_sent: bool
    created_at: datetime
    responded_at: datetime | None


# Shown to the student before they can accept — confirmed with Meshari as
# a requirement (docs/STAGE3_COMPANY_RAG.md), not optional UX polish.
# Plain and specific on purpose: exactly what's shared, and, just as
# important, what stays private.
INVITATION_DATA_NOTICE = (
    "If you accept, {company} will be able to see your task submissions "
    "and progress on this project, and your Mentor's reviews and feedback "
    "for it. They will not see your CV, any other project or task you "
    "work on, your other agents, or your conversations with them."
)


class InvitationDetailOut(BaseModel):
    """The student's own view of one invitation — everything they need to
    give informed consent before accepting. See routers/invitations.py."""

    id: str
    organization_name: str
    job_title: str
    company_project_title: str | None
    status: InvitationStatus
    created_at: datetime
    responded_at: datetime | None
    data_shared_notice: str


class InvitationAccept(BaseModel):
    # Required, not just present — see routers/invitations.py's accept():
    # false or omitted is refused with a 400, the same way a password
    # change requires current_password rather than assuming consent from
    # the act of calling the endpoint.
    consent: bool = False


class CompanyStudentOut(BaseModel):
    """A company's roster view of one accepted invitation — exactly what
    INVITATION_DATA_NOTICE promised (task submissions/progress and Mentor
    reviews for this project), nothing about the student beyond that plus
    their name/email (already known — the company addressed the original
    invite to this person)."""

    invitation_id: str
    student_name: str
    student_email: str
    job_title: str
    company_project_title: str | None
    project_title: str | None
    project_status: ProjectStatus | None
    current_week_number: int | None
    task_counts: dict[str, int]


class CompanyStudentWeekOut(BaseModel):
    """One week of the student's project — the Manager's WEEK_PROGRESS
    review and HR's BEHAVIORAL review here, if either has been written
    yet, ARE the 'end-of-week report': the same reviews the weekly cycle
    already produces, just surfaced to the company that invited this
    student instead of building a second reporting pipeline."""

    week_number: int
    status: WeekStatus
    started_at: datetime
    target_end_at: datetime
    ended_at: datetime | None
    tasks: list[TaskOut]
    reviews: list[ReviewOut]


class CompanyStudentDetailOut(CompanyStudentOut):
    weeks: list[CompanyStudentWeekOut]
