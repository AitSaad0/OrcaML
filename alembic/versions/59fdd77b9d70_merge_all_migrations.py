"""merge_all_migrations

Revision ID: 59fdd77b9d70
Revises: bd77b6d46852, c09b70d7fe8b
Create Date: 2026-04-20 22:12:15.675075

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '59fdd77b9d70'
down_revision: Union[str, Sequence[str], None] = ('bd77b6d46852', 'c09b70d7fe8b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
