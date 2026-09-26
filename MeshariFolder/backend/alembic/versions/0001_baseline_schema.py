"""baseline schema

The schema as it stood when Alembic was adopted — every table the app had
been creating with Base.metadata.create_all(). Databases created that way
before this migration existed are adopted (verified, then stamped 0001) by
app/migrations.py instead of re-running this; fresh databases run it.

Revision ID: 0001
Revises:
Create Date: 2026-09-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Postgres keeps enum types as separate objects: dropping the tables that use
# them does NOT drop them, and a later upgrade would then fail with
# "type already exists". SQLite has no such objects.
_PG_ENUM_TYPES = (
    "agenttype", "onboardingstage", "projectsource", "projectstatus",
    "reviewkind", "sendertype", "taskstatus", "trackenum", "weekstatus",
)


def upgrade() -> None:
    op.create_table('agent_catalog',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('agent_type', sa.Enum('MANAGER', 'MENTOR', 'HR', 'SECURITY_REVIEWER', 'DATA_REVIEWER', 'CAREER_COACH', 'DEVOPS', name='agenttype'), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('suggested_for_tracks_json', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('agent_type')
    )
    op.create_table('organizations',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('organization_id', sa.String(), nullable=True),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('hashed_password', sa.String(), nullable=False),
    sa.Column('full_name', sa.String(), nullable=False),
    sa.Column('track', sa.Enum('JUNIOR_DEV', 'SOFTWARE_ENGINEERING', 'DATA_SCIENCE_AI', 'CYBERSECURITY', 'NETWORKS_INFRASTRUCTURE', 'INFORMATION_SYSTEMS', 'CLOUD_DEVOPS', name='trackenum'), nullable=False),
    sa.Column('cv_raw_text', sa.Text(), nullable=True),
    sa.Column('onboarding_stage', sa.Enum('CV', 'QA', 'TRACK', 'AGENTS', 'COMPLETE', name='onboardingstage'), nullable=False),
    sa.Column('suggested_track', sa.Enum('JUNIOR_DEV', 'SOFTWARE_ENGINEERING', 'DATA_SCIENCE_AI', 'CYBERSECURITY', 'NETWORKS_INFRASTRUCTURE', 'INFORMATION_SYSTEMS', 'CLOUD_DEVOPS', name='trackenum'), nullable=True),
    sa.Column('track_confirmed', sa.Boolean(), nullable=False),
    sa.Column('intro_text', sa.Text(), nullable=True),
    sa.Column('onboarding_qa_json', sa.JSON(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    op.create_table('chat_messages',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('agent_type', sa.Enum('MANAGER', 'MENTOR', 'HR', 'SECURITY_REVIEWER', 'DATA_REVIEWER', 'CAREER_COACH', 'DEVOPS', name='agenttype'), nullable=False),
    sa.Column('sender_type', sa.Enum('USER', 'AGENT', name='sendertype'), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('employee_files',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('organization_id', sa.String(), nullable=True),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('skills_json', sa.JSON(), nullable=False),
    sa.Column('strengths_json', sa.JSON(), nullable=False),
    sa.Column('growth_areas_json', sa.JSON(), nullable=False),
    sa.Column('summary_text', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_table('projects',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('organization_id', sa.String(), nullable=True),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('ACTIVE', 'COMPLETED', name='projectstatus'), nullable=False),
    sa.Column('source', sa.Enum('MANAGER', 'OWN', name='projectsource'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user_agents',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('agent_catalog_id', sa.String(), nullable=False),
    sa.Column('added_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['agent_catalog_id'], ['agent_catalog.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('weeks',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('organization_id', sa.String(), nullable=True),
    sa.Column('project_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('week_number', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('ACTIVE', 'COMPLETED', name='weekstatus'), nullable=False),
    sa.Column('big_task_title', sa.String(), nullable=False),
    sa.Column('big_task_description', sa.Text(), nullable=False),
    sa.Column('subtasks_plan_json', sa.JSON(), nullable=False),
    sa.Column('next_subtask_index', sa.Integer(), nullable=False),
    sa.Column('started_at', sa.DateTime(), nullable=False),
    sa.Column('target_end_at', sa.DateTime(), nullable=False),
    sa.Column('ended_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tasks',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('organization_id', sa.String(), nullable=True),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('week_id', sa.String(), nullable=True),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('TODO', 'IN_PROGRESS', 'SUBMITTED', 'REVIEWED', name='taskstatus'), nullable=False),
    sa.Column('github_link', sa.String(), nullable=True),
    sa.Column('submission_text', sa.Text(), nullable=True),
    sa.Column('created_by_agent', sa.Enum('MANAGER', 'MENTOR', 'HR', 'SECURITY_REVIEWER', 'DATA_REVIEWER', 'CAREER_COACH', 'DEVOPS', name='agenttype'), nullable=False),
    sa.Column('deadline', sa.DateTime(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['week_id'], ['weeks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('reviews',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('organization_id', sa.String(), nullable=True),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('task_id', sa.String(), nullable=True),
    sa.Column('week_id', sa.String(), nullable=True),
    sa.Column('agent_type', sa.Enum('MANAGER', 'MENTOR', 'HR', 'SECURITY_REVIEWER', 'DATA_REVIEWER', 'CAREER_COACH', 'DEVOPS', name='agenttype'), nullable=False),
    sa.Column('kind', sa.Enum('TASK_REVIEW', 'WEEK_PROGRESS', 'BEHAVIORAL', 'SKILLS_ROLLUP', name='reviewkind'), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('metrics_json', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['week_id'], ['weeks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('task_attachments',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('task_id', sa.String(), nullable=False),
    sa.Column('filename', sa.String(), nullable=False),
    sa.Column('content_type', sa.String(), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('storage_path', sa.String(), nullable=False),
    sa.Column('uploaded_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('task_messages',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('task_id', sa.String(), nullable=False),
    sa.Column('sender_type', sa.Enum('USER', 'AGENT', name='sendertype'), nullable=False),
    sa.Column('agent_type', sa.Enum('MANAGER', 'MENTOR', 'HR', 'SECURITY_REVIEWER', 'DATA_REVIEWER', 'CAREER_COACH', 'DEVOPS', name='agenttype'), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('task_messages')
    op.drop_table('task_attachments')
    op.drop_table('reviews')
    op.drop_table('tasks')
    op.drop_table('weeks')
    op.drop_table('user_agents')
    op.drop_table('projects')
    op.drop_table('employee_files')
    op.drop_table('chat_messages')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_email'))

    op.drop_table('users')
    op.drop_table('organizations')
    op.drop_table('agent_catalog')

    if op.get_bind().dialect.name == "postgresql":
        for enum_name in _PG_ENUM_TYPES:
            op.execute(f"DROP TYPE IF EXISTS {enum_name}")
