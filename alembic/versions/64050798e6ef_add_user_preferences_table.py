"""add user_preferences table

Revision ID: 64050798e6ef
Revises: acd402710fd4
Create Date: 2026-05-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '64050798e6ef'
down_revision: Union[str, Sequence[str], None] = 'acd402710fd4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_preferences',
        sa.Column('id',          postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id',     postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('email_runs',  sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('deployments', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('weekly',      sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('security',    sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('updated_at',  sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('user_preferences')