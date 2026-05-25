"""add enhanced cleaning

Revision ID: b06369c1e2e2
Revises: 64050798e6ef
Create Date: 2026-05-24 16:46:18.144428

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b06369c1e2e2'
down_revision: Union[str, Sequence[str], None] = '64050798e6ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('cleaned_datasets', sa.Column('cleaning_report', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('cleaned_datasets', sa.Column('rolled_back', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('cleaned_datasets', sa.Column('rolled_back_at', sa.DateTime(), nullable=True))
    op.add_column('cleaning_configs', sa.Column('column_rules', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('cleaning_configs', sa.Column('status', sa.String(), nullable=False, server_default='configured'))


def downgrade() -> None:
    op.drop_column('cleaned_datasets', 'rolled_back_at')
    op.drop_column('cleaned_datasets', 'rolled_back')
    op.drop_column('cleaned_datasets', 'cleaning_report')
    op.drop_column('cleaning_configs', 'status')
    op.drop_column('cleaning_configs', 'column_rules')
