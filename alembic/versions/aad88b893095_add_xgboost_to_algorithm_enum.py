"""add xgboost to algorithm enum

Revision ID: aad88b893095
Revises: d6d6d508352a
Create Date: 2026-05-08 11:24:45.200778

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'aad88b893095'
down_revision: Union[str, Sequence[str], None] = 'd6d6d508352a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("ALTER TYPE algorithm ADD VALUE IF NOT EXISTS 'XGBOOST'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
