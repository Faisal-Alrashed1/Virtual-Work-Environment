import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    learner = "learner"
    recruiter = "recruiter"
    candidate = "candidate"


class TaskStatus(str, enum.Enum):
    draft = "DRAFT"
    pending_approval = "PENDING_APPROVAL"
    todo = "TO_DO"
    in_progress = "IN_PROGRESS"
    submitted = "SUBMITTED"
    under_review = "UNDER_REVIEW"
    discussion = "DISCUSSION"
    reviewed = "REVIEWED"


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.learner)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CandidateInvitation(Base):
    __tablename__ = "candidate_invitations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    recruiter_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    code: Mapped[str] = mapped_column(String, unique=True, index=True)
    candidate_email: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="sent")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CareerProfile(Base):
    __tablename__ = "career_profiles"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    cv_path: Mapped[str | None] = mapped_column(String, nullable=True)
    extracted: Mapped[dict] = mapped_column(JSON, default=dict)
    diagnostic_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    career_path: Mapped[dict] = mapped_column(JSON, default=dict)
    revisions: Mapped[list] = mapped_column(JSON, default=list)


class WorkCycle(Base):
    __tablename__ = "work_cycles"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    report_generated: Mapped[bool] = mapped_column(Boolean, default=False)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    cycle_id: Mapped[str] = mapped_column(ForeignKey("work_cycles.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    brief: Mapped[str] = mapped_column(Text)
    acceptance_criteria: Mapped[list] = mapped_column(JSON, default=list)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.todo)
    source_evidence: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    github_url: Mapped[str] = mapped_column(String)
    commit_sha: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(Text)
    challenges: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SubmissionArtifact(Base):
    """The submitted code is stored separately so attempts remain immutable."""
    __tablename__ = "submission_artifacts"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String, default="inline_code")
    language: Mapped[str] = mapped_column(String, default="python")
    content: Mapped[str] = mapped_column(Text)


class Evaluation(Base):
    __tablename__ = "evaluations"
    __table_args__ = (UniqueConstraint("task_id", "agent", name="uq_eval_task_agent"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    agent: Mapped[str] = mapped_column(String)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    rationale: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(JSON, default=1.0)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), nullable=True, index=True)
    agent: Mapped[str] = mapped_column(String, default="career")
    sender: Mapped[str] = mapped_column(String, default="agent")
    kind: Mapped[str] = mapped_column(String, default="chat")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    attested_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class AssessmentCampaign(Base):
    __tablename__ = "assessment_campaigns"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    job_role: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RecruiterIntervention(Base):
    __tablename__ = "recruiter_interventions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    recruiter_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HiringDecision(Base):
    __tablename__ = "hiring_decisions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("assessment_campaigns.id"), index=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    recruiter_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    decision: Mapped[str] = mapped_column(String)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    cycle_id: Mapped[str] = mapped_column(ForeignKey("work_cycles.id"), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
