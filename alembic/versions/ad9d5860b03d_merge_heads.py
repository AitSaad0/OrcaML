"""merge_heads

Revision ID: ad9d5860b03d
Revises: 14761a650a05, b06369c1e2e2
Create Date: 2026-05-26 01:34:22.624361

"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = 'ad9d5860b03d'
down_revision: Union[str, Sequence[str], None] = ('14761a650a05', 'b06369c1e2e2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
