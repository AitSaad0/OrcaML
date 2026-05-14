"""add_predictions_table

Revision ID: fc8a99fff3a1
Revises: fc5d0df02d8c
Create Date: 2026-05-13 23:09:45.158553

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'fc8a99fff3a1'
down_revision: Union[str, Sequence[str], None] = 'fc5d0df02d8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('predictions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('deployment_id', sa.UUID(), nullable=False),
    sa.Column('input_features', sa.JSON(), nullable=False),
    sa.Column('prediction', sa.JSON(), nullable=False),
    sa.Column('prediction_label', sa.String(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['deployment_id'], ['deployments.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_predictions_deployment_id'), 'predictions', ['deployment_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_predictions_deployment_id'), table_name='predictions')
    op.drop_table('predictions')