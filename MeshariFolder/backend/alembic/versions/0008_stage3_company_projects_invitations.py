"""stage 3: company projects + invitations

Two new tables, both brand new enum-free/enum-fresh additions — no
existing enum type is touched (ProjectSource stays exactly as it was;
see docs/STAGE3_COMPANY_RAG.md's "Decisions worth knowing about" for why
a company-sourced Project is distinguished by organization_id being set
rather than a new ProjectSource value — ALTER TYPE ADD VALUE on an
existing Postgres enum has real transactional footguns that aren't worth
the risk to verify blind in this environment).

company_projects: a company's own real project template, per job title —
distinct from a graduate's own project (Project, source=OWN).
invitations: a company inviting a specific email to a job title, with a
real company_project (optional) or the ordinary platform track.
invitationstatus is a brand new enum type (PENDING/ACCEPTED/DECLINED) —
safe, ordinary CREATE TYPE, same as 0007's accounttype/companyrole.

See docs/STAGE3_COMPANY_RAG.md.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-25 09:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'company_projects',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('organization_id', sa.String(), nullable=False),
        sa.Column('job_title_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('materials_text', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['job_title_id'], ['job_titles.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'invitations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('organization_id', sa.String(), nullable=False),
        sa.Column('job_title_id', sa.String(), nullable=False),
        sa.Column('company_project_id', sa.String(), nullable=True),
        sa.Column('invited_email', sa.String(), nullable=False),
        sa.Column('invited_by_user_id', sa.String(), nullable=False),
        sa.Column(
            'status',
            postgresql.ENUM('PENDING', 'ACCEPTED', 'DECLINED', name='invitationstatus'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['job_title_id'], ['job_titles.id']),
        sa.ForeignKeyConstraint(['company_project_id'], ['company_projects.id']),
        sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('invitations', schema=None) as batch_op:
        batch_op.create_index('ix_invitations_invited_email', ['invited_email'])


def downgrade() -> None:
    with op.batch_alter_table('invitations', schema=None) as batch_op:
        batch_op.drop_index('ix_invitations_invited_email')
    op.drop_table('invitations')
    op.drop_table('company_projects')

    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS invitationstatus")
