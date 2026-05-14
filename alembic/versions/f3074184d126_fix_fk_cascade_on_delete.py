"""fix_fk_cascade_on_delete

Revision ID: f3074184d126
Revises: 5e830ca12693
Create Date: 2026-05-12 20:50:13.100191

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3074184d126'
down_revision: Union[str, Sequence[str], None] = '5e830ca12693'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # cleaning_configs
    op.drop_constraint("cleaning_configs_environment_id_fkey", "cleaning_configs", type_="foreignkey")
    op.create_foreign_key(
        "cleaning_configs_environment_id_fkey",
        "cleaning_configs", "environments",
        ["environment_id"], ["id"],
        ondelete="CASCADE"
    )

    # cleaned_datasets
    op.drop_constraint("cleaned_datasets_environment_id_fkey", "cleaned_datasets", type_="foreignkey")
    op.create_foreign_key(
        "cleaned_datasets_environment_id_fkey",
        "cleaned_datasets", "environments",
        ["environment_id"], ["id"],
        ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint("cleaning_configs_environment_id_fkey", "cleaning_configs", type_="foreignkey")
    op.create_foreign_key(
        "cleaning_configs_environment_id_fkey",
        "cleaning_configs", "environments",
        ["environment_id"], ["id"],
    )

    op.drop_constraint("cleaned_datasets_environment_id_fkey", "cleaned_datasets", type_="foreignkey")
    op.create_foreign_key(
        "cleaned_datasets_environment_id_fkey",
        "cleaned_datasets", "environments",
        ["environment_id"], ["id"],
    )