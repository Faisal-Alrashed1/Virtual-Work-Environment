import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TrackEnum(str, enum.Enum):
    JUNIOR_DEV = "junior_dev"  # Stage 1's only track — kept for existing users
    # Stage 2 — all majors within IT fields (STAGE2_ONBOARDING_FLOW.md).
    # CV-suggested, user-approved; see User.suggested_track/track_confirmed.
    SOFTWARE_ENGINEERING = "software_engineering"
    DATA_SCIENCE_AI = "data_science_ai"
    CYBERSECURITY = "cybersecurity"
    NETWORKS_INFRASTRUCTURE = "networks_infrastructure"
    INFORMATION_SYSTEMS = "information_systems"
    CLOUD_DEVOPS = "cloud_devops"


class AgentType(str, enum.Enum):
    MANAGER = "manager"
    MENTOR = "mentor"
    HR = "hr"
    # Stage 2 — optional agents a graduate can add to their roster
    # alongside the default three. See AgentCatalog / UserAgent below.
    SECURITY_REVIEWER = "security_reviewer"
    DATA_REVIEWER = "data_reviewer"
    CAREER_COACH = "career_coach"
    DEVOPS = "devops"


class OnboardingStage(str, enum.Enum):
    """Where a graduate is in the Stage 2 onboarding graph
    (app/agents/graph/onboarding_graph.py) — lets a resumed session pick
    up where it left off instead of restarting the whole flow."""
    CV = "cv"
    QA = "qa"
    TRACK = "track"
    AGENTS = "agents"
    COMPLETE = "complete"


class TaskStatus(str, enum.Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"


class SenderType(str, enum.Enum):
    USER = "user"
    AGENT = "agent"


class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"


class ProjectSource(str, enum.Enum):
    """Stage 2 (docs/STAGE2_OWN_PROJECT.md): whether the Manager
    improvised this project or the graduate brought their own. Doesn't
    change how plan_week works — it already only reads title/description,
    which read the same regardless of who wrote them."""
    MANAGER = "manager"
    OWN = "own"


class WeekStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"


class ReviewKind(str, enum.Enum):
    """Distinguishes the four review shapes that now share the `reviews`
    table — see STAGE1_PRODUCT_FLOW.md's end-of-week cascade. Each kind's
    metrics_json contract is documented at its creation site."""
    TASK_REVIEW = "task_review"        # Mentor, per submitted subtask (existing)
    WEEK_PROGRESS = "week_progress"    # Manager, end-of-week progress review
    BEHAVIORAL = "behavioral"          # HR, end-of-week attendance/consistency eval
    SKILLS_ROLLUP = "skills_rollup"    # HR, periodic Employee File rollup (existing)


# ---------------------------------------------------------------------------
# Organization — not used in Stage 1, exists now so Stage 3 (companies build
# their own Venvs) is additive instead of a schema rewrite. Every core table
# below carries a nullable organization_id for the same reason.
# ---------------------------------------------------------------------------

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )

    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)

    track: Mapped[TrackEnum] = mapped_column(
        Enum(TrackEnum), default=TrackEnum.JUNIOR_DEV, nullable=False
    )

    # Raw CV text stored at intake; structured parsing is owned by the
    # AI/Agents team and can populate employee_file.skills_json downstream.
    cv_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Stage 2 onboarding (docs/STAGE2_ONBOARDING_FLOW.md) ---
    onboarding_stage: Mapped[OnboardingStage] = mapped_column(
        Enum(OnboardingStage), default=OnboardingStage.CV, nullable=False
    )
    # The graph's CV-inferred suggestion, pending approval. `track` above
    # only changes once the graduate confirms or overrides it (track_confirmed
    # flips to True at that point) — until then it stays at its default.
    suggested_track: Mapped[TrackEnum | None] = mapped_column(Enum(TrackEnum), nullable=True)
    track_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    # Free text the graduate adds themselves, on top of the parsed CV.
    intro_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # One entry per agent-generated follow-up question:
    # [{"question": ..., "answer": ... | None}] — answer stays None if skipped.
    onboarding_qa_json: Mapped[list] = mapped_column(JSON, default=list)

    @property
    def has_cv(self) -> bool:
        """Whether cv_raw_text has been set — exposed via UserOut so the
        frontend can offer the CV step once without re-nagging on every
        login, and without shipping the raw text itself in /users/me."""
        return bool(self.cv_raw_text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    employee_file: Mapped["EmployeeFile"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    reviews: Mapped[list["Review"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    projects: Mapped[list["Project"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    weeks: Mapped[list["Week"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    selected_agents: Mapped[list["UserAgent"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class EmployeeFile(Base):
    """
    The persistent, shared record all three agents read from and write to.
    This is what makes the agents feel like one workplace rather than three
    isolated chatbots — Manager reads it to calibrate task difficulty, Mentor
    writes findings into it, HR summarizes it into reviews.
    """

    __tablename__ = "employee_files"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=False
    )

    skills_json: Mapped[dict] = mapped_column(JSON, default=dict)
    strengths_json: Mapped[dict] = mapped_column(JSON, default=dict)
    growth_areas_json: Mapped[dict] = mapped_column(JSON, default=dict)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship(back_populates="employee_file")


# ---------------------------------------------------------------------------
# Stage 2 — selectable agent roster (docs/STAGE2_ONBOARDING_FLOW.md). The
# default three (Manager/Mentor/HR) are always included and aren't stored
# here; this catalog is only the optional extras a graduate can add, so it
# can grow over time without touching the schema again.
# ---------------------------------------------------------------------------

class AgentCatalog(Base):
    __tablename__ = "agent_catalog"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # slug, e.g. "security_reviewer"
    agent_type: Mapped[AgentType] = mapped_column(Enum(AgentType), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # TrackEnum values this agent is suggested for during onboarding — the
    # graduate can still add/remove any catalog agent regardless of track.
    suggested_for_tracks_json: Mapped[list] = mapped_column(JSON, default=list)


class UserAgent(Base):
    """One optional agent a graduate has added to their roster."""

    __tablename__ = "user_agents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    agent_catalog_id: Mapped[str] = mapped_column(ForeignKey("agent_catalog.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="selected_agents")
    agent: Mapped["AgentCatalog"] = relationship()


# ---------------------------------------------------------------------------
# Project & Week — the weekly-cycle flow (docs/STAGE1_PRODUCT_FLOW.md).
# A Project is the "main project" introduced during orientation. A Week is
# one 5-workday cycle within it: the Manager defines that week's "big task"
# up front, plans it out into subtasks_plan_json (decided together, per the
# spec), then hands subtasks to the graduate one at a time by creating real
# Task rows from that plan as each prior one is approved — see
# next_subtask_index. Orchestration that actually populates these (starting
# a week, releasing the next subtask, running the end-of-week cascade) is
# the next body of work; this schema is what it will build on.
# ---------------------------------------------------------------------------

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.ACTIVE, nullable=False
    )
    # Stage 2 — who this project came from. Doesn't affect plan_week,
    # which only ever reads title/description either way.
    source: Mapped[ProjectSource] = mapped_column(
        Enum(ProjectSource), default=ProjectSource.MANAGER, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user: Mapped["User"] = relationship(back_populates="projects")
    weeks: Mapped[list["Week"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="Week.week_number"
    )


class Week(Base):
    __tablename__ = "weeks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    # Denormalized alongside project_id, matching Task/Review's existing
    # user_id pattern — keeps "give me this user's weeks" a plain filter.
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)

    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[WeekStatus] = mapped_column(
        Enum(WeekStatus), default=WeekStatus.ACTIVE, nullable=False
    )

    big_task_title: Mapped[str] = mapped_column(String, nullable=False)
    big_task_description: Mapped[str] = mapped_column(Text, nullable=False)
    # The 5 subtasks the Manager plans when setting the big task, e.g.
    # [{"title": ..., "description": ...}, ...] — not yet real Task rows.
    # Each becomes one as its turn comes, via next_subtask_index, so the
    # graduate only ever sees one at a time (STAGE1_PRODUCT_FLOW.md).
    subtasks_plan_json: Mapped[list] = mapped_column(JSON, default=list)
    next_subtask_index: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    target_end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Set when the end-of-week cascade actually runs — may differ from
    # target_end_at if the graduate finishes early or runs behind.
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="weeks")
    user: Mapped["User"] = relationship(back_populates="weeks")
    tasks: Mapped[list["Task"]] = relationship(back_populates="week")
    reviews: Mapped[list["Review"]] = relationship(back_populates="week")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Nullable: the original flat one-task-at-a-time model (and any ad hoc
    # /admin-created task via POST /tasks) has no week. Subtasks released by
    # the weekly-cycle flow set this.
    week_id: Mapped[str | None] = mapped_column(ForeignKey("weeks.id"), nullable=True)

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.TODO, nullable=False
    )
    github_link: Mapped[str | None] = mapped_column(String, nullable=True)
    # Stage 2 (docs/STAGE2_MEETING_AND_SUBMISSIONS.md): a submission can be
    # a GitHub link, free text, file/image attachments, or any mix — at
    # least one, not github_link specifically. See TaskAttachment below.
    submission_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_agent: Mapped[AgentType] = mapped_column(
        Enum(AgentType), default=AgentType.MANAGER, nullable=False
    )

    # None outside a week (backward compatible with the flat model).
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Distinct from updated_at (which changes on every edit — thread
    # replies, a needs_changes bounce back to in_progress, etc). Set each
    # time status moves to SUBMITTED; completed_at is set once, the first
    # time the Mentor approves.
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    @property
    def is_late(self) -> bool | None:
        """None until both a deadline and a completion exist — lateness
        isn't knowable before then. Judged against actual completion, not
        submission, since a submission can bounce back on needs_changes and
        get resubmitted later (STAGE1_PRODUCT_FLOW.md's Oct 1 / Oct 2
        example)."""
        if not self.deadline or not self.completed_at:
            return None
        return self.completed_at > self.deadline

    user: Mapped["User"] = relationship(back_populates="tasks")
    week: Mapped["Week"] = relationship(back_populates="tasks")
    messages: Mapped[list["TaskMessage"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="TaskMessage.created_at"
    )
    reviews: Mapped[list["Review"]] = relationship(back_populates="task")
    attachments: Mapped[list["TaskAttachment"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="TaskAttachment.uploaded_at"
    )


class TaskAttachment(Base):
    """A file or image attached to a submission (docs/
    STAGE2_MEETING_AND_SUBMISSIONS.md) — on local disk, not cloud storage;
    see app/storage.py. content_type starting with "image/" is what the
    Mentor treats as reviewable images (mentor.py), everything else is
    just listed by filename."""

    __tablename__ = "task_attachments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["Task"] = relationship(back_populates="attachments")


class TaskMessage(Base):
    """The threaded comment view under each task card."""

    __tablename__ = "task_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False)

    sender_type: Mapped[SenderType] = mapped_column(Enum(SenderType), nullable=False)
    agent_type: Mapped[AgentType | None] = mapped_column(Enum(AgentType), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["Task"] = relationship(back_populates="messages")


class ChatMessage(Base):
    """A message in the standalone Meeting Room (/meeting) — a direct chat
    with one agent, not tied to any task (unlike TaskMessage). One running
    conversation per (user, agent_type): the user talks to the Manager,
    Mentor, or HR about anything, and it persists across visits. sender_type
    says who spoke; agent_type is which agent the whole thread is with (set
    on both the user's and the agent's rows, so a single indexed filter
    pulls one agent's conversation)."""

    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Which agent this conversation is with — set on every row in the
    # thread, user and agent alike, so "give me my chat with the Mentor" is
    # one filter (user_id + agent_type) with no join.
    agent_type: Mapped[AgentType] = mapped_column(Enum(AgentType), nullable=False)
    sender_type: Mapped[SenderType] = mapped_column(Enum(SenderType), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="chat_messages")


class Review(Base):
    """
    Mentor reviews are tied to a task_id. HR reviews are periodic and roll up
    multiple tasks, so task_id is nullable for that case.
    """

    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    # Set for WEEK_PROGRESS (Manager) and BEHAVIORAL (HR) reviews from the
    # end-of-week cascade. None for TASK_REVIEW (tied to task_id instead)
    # and SKILLS_ROLLUP (periodic, tied to neither).
    week_id: Mapped[str | None] = mapped_column(ForeignKey("weeks.id"), nullable=True)

    agent_type: Mapped[AgentType] = mapped_column(Enum(AgentType), nullable=False)
    # metrics_json's contract differs per kind — see each agent module.
    kind: Mapped[ReviewKind] = mapped_column(
        Enum(ReviewKind), default=ReviewKind.TASK_REVIEW, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metrics_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="reviews")
    task: Mapped["Task"] = relationship(back_populates="reviews")
    week: Mapped["Week"] = relationship(back_populates="reviews")
