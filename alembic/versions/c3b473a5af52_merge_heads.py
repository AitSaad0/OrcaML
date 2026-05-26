"""merge_heads

Revision ID: c3b473a5af52
Revises: ad9d5860b03d
Create Date: 2026-05-26 01:51:11.969304

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3b473a5af52'
down_revision: Union[str, Sequence[str], None] = 'ad9d5860b03d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
