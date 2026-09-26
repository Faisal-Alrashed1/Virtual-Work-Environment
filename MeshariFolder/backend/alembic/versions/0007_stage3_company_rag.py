"""stage 3: company accounts + RAG knowledge base

Organization gains `field` (free-text industry) and a `join_code` other
reps use to join instead of creating a new company by accident. users
gains `account_type` (STUDENT/COMPANY, backfilled to 'student' for every
existing row via server_default — nothing before this migration ever
created a COMPANY user) and `company_role` (nullable — only meaningful
for a COMPANY account). Three new tables: job_titles (free text, per
org), knowledge_materials (raw uploaded/pasted source), knowledge_chunks
(chunked + embedded — what app/rag.py actually searches).

See docs/STAGE3_COMPANY_RAG.md.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-24 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# New enum types this migration introduces (not reused from elsewhere —
# unlike 0006's team_messages, which reused agenttype/sendertype). Cleaned
# up in downgrade() the same way 0001's baseline cleans up its own, since
# dropping the columns/tables that use them does not drop the types
# themselves on Postgres.
_NEW_PG_ENUM_TYPES = ("accounttype", "companyrole")


def upgrade() -> None:
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('field', sa.String(), nullable=True))
        # server_default backfills any pre-existing row (e.g. a database
        # adopted from before this migration existed — see
        # smoke_test_migrations.py's adoption test, which seeds exactly
        # one). Every new Organization going forward gets a real unique
        # code from models.gen_join_code() at the Python/ORM level; this
        # placeholder only ever has to cover legacy rows, realistically at
        # most one.
        batch_op.add_column(
            sa.Column(
                'join_code', sa.String(), nullable=False, server_default='LEGACYJOIN'
            )
        )
        batch_op.create_unique_constraint('uq_organizations_join_code', ['join_code'])

    # Postgres enum types must exist before a column can reference them.
    # op.create_table's DDL compiler emits CREATE TYPE automatically for a
    # brand-new table, but ADD COLUMN inside batch_alter_table does not —
    # confirmed the hard way (this migration originally 500'd against a
    # real Postgres 16 instance with "type accounttype does not exist"
    # before this explicit create was added). SQLite has no such
    # statement or need, hence the dialect guard. Below, the columns use
    # postgresql.ENUM(create_type=False) rather than generic sa.Enum —
    # also confirmed the hard way (see 0006's docstring) that generic
    # sa.Enum does not reliably honor create_type=False.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        postgresql.ENUM('STUDENT', 'COMPANY', name='accounttype').create(bind, checkfirst=True)
        postgresql.ENUM('ADMIN', 'HR', 'TECH_LEAD', name='companyrole').create(bind, checkfirst=True)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'account_type',
                postgresql.ENUM('STUDENT', 'COMPANY', name='accounttype', create_type=False),
                nullable=False,
                # Must match the enum's actual label spelling exactly — this
                # codebase's Enum columns store the Python member NAME
                # ('STUDENT'), not .value ('student'). Confirmed the hard
                # way: a real Postgres 16 run rejected 'student' with
                # "invalid input value for enum accounttype" the first
                # time, since native enum validation (unlike SQLite, which
                # has none) actually checks this.
                server_default='STUDENT',
            )
        )
        batch_op.add_column(
            sa.Column(
                'company_role',
                postgresql.ENUM('ADMIN', 'HR', 'TECH_LEAD', name='companyrole', create_type=False),
                nullable=True,
            )
        )

    op.create_table(
        'job_titles',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('organization_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'knowledge_materials',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('organization_id', sa.String(), nullable=False),
        sa.Column('job_title_id', sa.String(), nullable=False),
        sa.Column('filename', sa.String(), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=False),
        sa.Column('uploaded_by_user_id', sa.String(), nullable=False),
        sa.Column('chunk_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['job_title_id'], ['job_titles.id']),
        sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('organization_id', sa.String(), nullable=False),
        sa.Column('job_title_id', sa.String(), nullable=False),
        sa.Column('material_id', sa.String(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['job_title_id'], ['job_titles.id']),
        sa.ForeignKeyConstraint(['material_id'], ['knowledge_materials.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('knowledge_chunks')
    op.drop_table('knowledge_materials')
    op.drop_table('job_titles')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('company_role')
        batch_op.drop_column('account_type')

    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_constraint('uq_organizations_join_code', type_='unique')
        batch_op.drop_column('join_code')
        batch_op.drop_column('field')

    if op.get_bind().dialect.name == "postgresql":
        for enum_name in _NEW_PG_ENUM_TYPES:
            op.execute(f"DROP TYPE IF EXISTS {enum_name}")
