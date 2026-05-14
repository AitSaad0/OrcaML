"""add_unique_constraint_datasets_env_id

Revision ID: 0422cdb97ed5
Revises: d6d6d508352a
Create Date: 2026-05-13 17:21:28.260586

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0422cdb97ed5'
down_revision: Union[str, Sequence[str], None] = 'd6d6d508352a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint("uq_datasets_env_id", "datasets", ["env_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_datasets_env_id", "datasets", type_="unique")
