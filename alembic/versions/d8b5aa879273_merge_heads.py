"""merge heads

Revision ID: d8b5aa879273
Revises: 59fdd77b9d70, a79d812542e3
Create Date: 2026-04-23 13:08:47.517456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8b5aa879273'
down_revision: Union[str, Sequence[str], None] = ('59fdd77b9d70', 'a79d812542e3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
