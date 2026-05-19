"""add api_keys table

Revision ID: acd402710fd4
Revises: 582f1882ba52
Create Date: 2026-05-19 11:31:19.047093

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'acd402710fd4'
down_revision: Union[str, Sequence[str], None] = '582f1882ba52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'api_keys',
        sa.Column('id',           postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id',      postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name',         sa.String(),  nullable=False),
        sa.Column('key_hash',     sa.String(),  nullable=False, unique=True),
        sa.Column('prefix',       sa.String(12), nullable=False),
        sa.Column('is_active',    sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at',   sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('api_keys')