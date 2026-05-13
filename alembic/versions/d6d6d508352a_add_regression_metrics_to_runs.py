"""add regression metrics to runs

Revision ID: d6d6d508352a
Revises: 7048f6ea679f
Create Date: 2026-05-08 01:23:33.068786

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6d6d508352a'
down_revision: Union[str, Sequence[str], None] = '7048f6ea679f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = [col['name'] for col in inspector.get_columns('runs')]

    if 'rmse' not in existing_columns:
        op.add_column('runs', sa.Column('rmse', sa.Float(), nullable=True))
    if 'mae' not in existing_columns:
        op.add_column('runs', sa.Column('mae', sa.Float(), nullable=True))
    if 'r2' not in existing_columns:
        op.add_column('runs', sa.Column('r2', sa.Float(), nullable=True))

def downgrade() -> None:
    op.drop_column('runs', 'r2')
    op.drop_column('runs', 'mae')
    op.drop_column('runs', 'rmse')
