import enum
import secrets
import uuid
from datetime import datetime, timedelta

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

# A roundtable normally takes 15-40 seconds. If it has been "running" this long, the process
# that was running it is gone (a restart or a crash): stop reporting it as running.
ROUNDTABLE_STALE_AFTER = timedelta(minutes=3)


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
    # The ten-agent pass (docs/TEN_AGENTS.md): three more optional agents,
    # rounding out a realistic team roster without overlapping Manager's
    # (big-picture) or Mentor's (code review) jobs. QA_ENGINEER and
    # UX_REVIEWER join the roundtable/task-chat technical specialists
    # (roundtable.py's ROUNDTABLE_AGENTS, task_chat.py's TASK_CHAT_AGENTS);
    # TECHNICAL_WRITER stays chat-only, like CAREER_COACH, since
    # documentation feedback isn't a "help me while I'm working" or
    # "review this submission" concern the way testing/design are.
    QA_ENGINEER = "qa_engineer"
    UX_REVIEWER = "ux_reviewer"
    TECHNICAL_WRITER = "technical_writer"


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
    """Distinguishes the five review shapes that now share the `reviews`
    table — see STAGE1_PRODUCT_FLOW.md's end-of-week cascade. Each kind's
    metrics_json contract is documented at its creation site."""
    TASK_REVIEW = "task_review"        # Mentor, per submitted subtask (existing)
    WEEK_PROGRESS = "week_progress"    # Manager, end-of-week progress review
    BEHAVIORAL = "behavioral"          # HR, end-of-week attendance/consistency eval
    SKILLS_ROLLUP = "skills_rollup"    # HR, periodic Employee File rollup (existing)
    CAREER_CHECKIN = "career_checkin"  # Career Coach, on-demand — see app/agents/career_coach.py


class AccountType(str, enum.Enum):
    """Stage 3 (docs/STAGE3_COMPANY_RAG.md): the login split the spec
    asked for. A STUDENT is everything this app already was; a COMPANY
    account belongs to an Organization and has a CompanyRole. Existing
    users are all STUDENT by default — this is purely additive."""
    STUDENT = "student"
    COMPANY = "company"


class CompanyRole(str, enum.Enum):
    """Only meaningful when User.account_type == COMPANY. Not yet used to
    gate any endpoint (every company role can create job titles and
    upload materials today) — stored and returned so the UI can label
    people correctly, and so per-role permissions are a small follow-up
    change rather than a schema change, if that's wanted later."""
    ADMIN = "admin"
    HR = "hr"
    TECH_LEAD = "tech_lead"


class InvitationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


# ---------------------------------------------------------------------------
# Organization — not used in Stage 1, exists now so Stage 3 (companies build
# their own Venvs) is additive instead of a schema rewrite. Every core table
# below carries a nullable organization_id for the same reason.
# ---------------------------------------------------------------------------

def gen_join_code() -> str:
    # Short and typeable (no 0/O/1/I ambiguity) — a rep shares this with
    # teammates to join their company's account instead of creating a new
    # Organization by accident. Not a security boundary (see
    # docs/STAGE3_COMPANY_RAG.md's "Decisions worth knowing about") —
    # good enough for who can join a bootcamp-demo company account.
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(7))


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # Free text ("field of business") — Stage 3's spec explicitly wants
    # this open to any industry, not just IT (see docs/STAGE3_COMPANY_RAG.md).
    field: Mapped[str | None] = mapped_column(String, nullable=True)
    join_code: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, default=gen_join_code
    )
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

    # Stage 3 (docs/STAGE3_COMPANY_RAG.md): STUDENT is everything this app
    # already was — the default, for every existing row. A COMPANY user
    # always has organization_id set and a company_role; a STUDENT's
    # organization_id stays None (Stage 1/2 had no use for it, kept
    # nullable from day one for exactly this later addition).
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType), default=AccountType.STUDENT, nullable=False
    )
    company_role: Mapped[CompanyRole | None] = mapped_column(Enum(CompanyRole), nullable=True)

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
    # What the graph produced at its last pause, saved so onboarding can be
    # resumed from the database alone (docs/ONBOARDING_RESUME.md). The graph's
    # own checkpointer is in-memory and per-process, so it can't be the source
    # of truth: a closed tab, a server restart or a second API worker would
    # otherwise strand the graduate mid-wizard.
    suggested_track_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_agent_ids_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

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
    team_messages: Mapped[list["TeamMessage"]] = relationship(
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
    # Which task-bank seed (agents/task_bank.py) the Manager based this project
    # on — NULL for a graduate's own project, or if the model named none. It
    # drives each week's place in the project's arc, and answers "why this task?".
    seed_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # For a graduate's own project (source=OWN) only: real material about it —
    # pasted notes and/or text extracted from uploaded files — so the Manager
    # can plan real subtasks instead of working from a one-line description.
    # Combined and capped at task_bank.MAX_MATERIALS_CHARS at write time; see
    # docs/STAGE2_OWN_PROJECT.md. Never set for a Manager-authored project.
    materials_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    @property
    def has_materials(self) -> bool:
        """Mirrors User.has_cv: lets the API say whether materials exist without
        shipping the (possibly large) text itself in every /projects/me response."""
        return bool(self.materials_text)

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
    # The agent roundtable (specialists + the Manager's synthesis) runs in the BACKGROUND
    # after the Mentor's review has been returned (docs/BACKGROUND_ROUNDTABLE.md). These two
    # timestamps are its state. They live in the database, not in memory, so any API worker
    # can answer "is it still going?" (see Task.roundtable_running).
    roundtable_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    roundtable_finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

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

    def _task_review_verdicts(self) -> list[str | None]:
        """The Mentor's verdict on each submission of this task, oldest first."""
        reviews = sorted(
            (r for r in self.reviews if r.kind == ReviewKind.TASK_REVIEW),
            key=lambda r: r.created_at,
        )
        return [(r.metrics_json or {}).get("verdict") for r in reviews]

    @property
    def needs_changes(self) -> bool:
        """True while the Mentor has bounced this task back for changes and the
        graduate hasn't resubmitted yet. A bounce sets status back to
        in_progress — the same status as "started, nothing submitted" — so the
        status alone can't tell the two apart; the latest verdict can. Derived
        (no column), so it can never disagree with the reviews themselves.
        Goes false again the moment the graduate resubmits (status leaves
        in_progress)."""
        if self.status != TaskStatus.IN_PROGRESS:
            return False
        verdicts = self._task_review_verdicts()
        return bool(verdicts) and verdicts[-1] == "needs_changes"

    @property
    def roundtable_running(self) -> bool:
        """True while the specialists' discussion for the latest review is still being
        written. Started and not yet finished — but only for ROUNDTABLE_STALE_AFTER: a
        server that died mid-discussion never records "finished", and a spinner that
        outlives its worker forever would be worse than no spinner."""
        if self.roundtable_started_at is None:
            return False
        if self.roundtable_finished_at is not None and self.roundtable_finished_at >= self.roundtable_started_at:
            return False
        return datetime.utcnow() - self.roundtable_started_at < ROUNDTABLE_STALE_AFTER

    @property
    def revision_count(self) -> int:
        """How many times the Mentor has asked for changes on this task
        (kept after approval: 2 means it took three attempts)."""
        return sum(1 for v in self._task_review_verdicts() if v == "needs_changes")

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


class TeamMessage(Base):
    """A message in the Team Room (the Meeting Room's shared mode,
    docs/TEAM_ROOM.md) — the whole team and the graduate in one running
    conversation, unlike ChatMessage's one-thread-per-agent Meeting Room.
    One thread per user: sender_type says who spoke, agent_type says
    which agent (None for the graduate's own messages). Only one agent
    replies per graduate message — meeting.route_team_message picks
    whichever team member fits best — but every agent's past replies
    stay visible in the same thread, so it reads as one room, not a
    grid of separate DMs."""

    __tablename__ = "team_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    sender_type: Mapped[SenderType] = mapped_column(Enum(SenderType), nullable=False)
    # None for the graduate's own messages.
    agent_type: Mapped[AgentType | None] = mapped_column(Enum(AgentType), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="team_messages")


# ---------------------------------------------------------------------------
# Stage 3 — company knowledge base + RAG (docs/STAGE3_COMPANY_RAG.md). A
# company's job titles are free text (JobTitle); each job title has its own
# knowledge base built from uploaded/pasted materials (KnowledgeMaterial —
# the raw source, one row per upload) chunked and embedded for retrieval
# (KnowledgeChunk — what app/rag.py actually searches over).
# ---------------------------------------------------------------------------


class JobTitle(Base):
    __tablename__ = "job_titles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    materials: Mapped[list["KnowledgeMaterial"]] = relationship(
        back_populates="job_title", cascade="all, delete-orphan"
    )

    @property
    def material_count(self) -> int:
        return len(self.materials)

    @property
    def chunk_count(self) -> int:
        return sum(m.chunk_count for m in self.materials)


class KnowledgeMaterial(Base):
    """One uploaded file or pasted block of text, before chunking — kept
    around so the company can see what they've uploaded and so a chunk can
    always be traced back to its source (filename is None for pasted text)."""

    __tablename__ = "knowledge_materials"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    job_title_id: Mapped[str] = mapped_column(ForeignKey("job_titles.id"), nullable=False)
    filename: Mapped[str | None] = mapped_column(String, nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job_title: Mapped["JobTitle"] = relationship(back_populates="materials")


class KnowledgeChunk(Base):
    """What app/rag.py actually retrieves over: one embedded piece of a
    KnowledgeMaterial. embedding_json is a plain list[float] — no vector
    extension, see docs/STAGE3_COMPANY_RAG.md for why — ranked by
    in-Python cosine similarity against a query embedding at retrieval
    time (app/rag.py's retrieve())."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    job_title_id: Mapped[str] = mapped_column(ForeignKey("job_titles.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(ForeignKey("knowledge_materials.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_json: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CompanyProject(Base):
    """A company's own REAL project (docs/STAGE3_COMPANY_RAG.md) — not a
    graduate's own project (Project, source=OWN). This one belongs to the
    company/job title, not to any one student yet: it's a template a
    student's actual Project gets created from once they accept an
    Invitation naming it (see Invitation.company_project_id and
    routers/invitations.py's accept()). Same materials_text shape and cap
    as Project's (task_bank.MAX_MATERIALS_CHARS) — it feeds plan_week the
    same way once copied over."""

    __tablename__ = "company_projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    job_title_id: Mapped[str] = mapped_column(ForeignKey("job_titles.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    materials_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def has_materials(self) -> bool:
        return bool(self.materials_text)


class Invitation(Base):
    """A company inviting a specific person, by email, to work under a
    given job title — with real company-authored tasks
    (company_project_id set) or the ordinary Manager-improvised platform
    track (company_project_id None). invited_email doesn't have to belong
    to an existing account yet; a student sees it once they register or
    log in with a matching email (routers/invitations.py's mine()).
    Accepting requires explicit consent (see INVITATION_DATA_NOTICE) —
    confirmed with Meshari as a requirement, not optional UX."""

    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    job_title_id: Mapped[str] = mapped_column(ForeignKey("job_titles.id"), nullable=False)
    company_project_id: Mapped[str | None] = mapped_column(
        ForeignKey("company_projects.id"), nullable=True
    )
    invited_email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    invited_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[InvitationStatus] = mapped_column(
        Enum(InvitationStatus), default=InvitationStatus.PENDING, nullable=False
    )
    # Whether app/email.py actually sent a real email for this invitation
    # — False whether SMTP just isn't configured or a real send failed;
    # either way the invitation itself still exists and is findable via
    # GET /invitations/mine, so this is informational for the company
    # (routers/company.py surfaces it), never something that blocks
    # anything.
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


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
