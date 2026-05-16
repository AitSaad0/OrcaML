"""merge_heads

Revision ID: d9d87e0a4876
Revises: 0422cdb97ed5, fc8a99fff3a1
Create Date: 2026-05-14 16:45:59.664975

"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = 'd9d87e0a4876'
down_revision: Union[str, Sequence[str], None] = ('0422cdb97ed5', 'fc8a99fff3a1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
