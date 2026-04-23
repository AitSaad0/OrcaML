"""fix conflict

Revision ID: 1036a16afd94
Revises: d8b5aa879273
Create Date: 2026-04-23 13:20:14.374901

"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = '1036a16afd94'
down_revision: Union[str, Sequence[str], None] = 'd8b5aa879273'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
