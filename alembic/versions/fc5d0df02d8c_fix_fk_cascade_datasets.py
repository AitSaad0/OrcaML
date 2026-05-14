"""fix_fk_cascade_datasets

Revision ID: fc5d0df02d8c
Revises: f3074184d126
Create Date: 2026-05-12 20:58:43.549398

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fc5d0df02d8c'
down_revision: Union[str, Sequence[str], None] = 'f3074184d126'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.drop_constraint("datasets_env_id_fkey", "datasets", type_="foreignkey")
    op.create_foreign_key(
        "datasets_env_id_fkey",
        "datasets", "environments",
        ["env_id"], ["id"],
        ondelete="CASCADE"
    )

def downgrade() -> None:
    op.drop_constraint("datasets_env_id_fkey", "datasets", type_="foreignkey")
    op.create_foreign_key(
        "datasets_env_id_fkey",
        "datasets", "environments",
        ["env_id"], ["id"],
    )