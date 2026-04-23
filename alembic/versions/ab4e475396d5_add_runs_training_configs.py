"""add_runs_training_configs

Revision ID: ab4e475396d5
Revises: 95fd74d77755
Create Date: 2026-04-12 18:09:00.375044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM


# revision identifiers, used by Alembic.
revision: str = 'ab4e475396d5'
down_revision: Union[str, Sequence[str], None] = '95fd74d77755'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

algorithm_enum = ENUM(
    'LOGISTIC_REGRESSION', 'RANDOM_FOREST', 'SVM', 'XGBOOST',
    'DECISION_TREE', 'LINEAR_REGRESSION', 'KNN',
    name='algorithm'
)

runstatus_enum = ENUM(
    'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED',
    name='runstatus'
)


def upgrade() -> None:
    # Crée les enums seulement s'ils n'existent pas déjà
    algorithm_enum.create(op.get_bind(), checkfirst=True)
    runstatus_enum.create(op.get_bind(), checkfirst=True)

    op.create_table('runs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('environment_id', sa.UUID(), nullable=False),
    sa.Column('algorithm', sa.Enum('LOGISTIC_REGRESSION', 'RANDOM_FOREST', 'SVM', 'XGBOOST', 'DECISION_TREE', 'LINEAR_REGRESSION', 'KNN', name='algorithm', create_type=False), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', name='runstatus', create_type=False), nullable=False),
    sa.Column('mlflow_run_id', sa.String(length=255), nullable=True),
    sa.Column('duration_seconds', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_runs_environment_id'), 'runs', ['environment_id'], unique=False)
    op.create_index(op.f('ix_runs_status'), 'runs', ['status'], unique=False)
    op.create_table('training_configs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('algorithm', sa.Enum('LOGISTIC_REGRESSION', 'RANDOM_FOREST', 'SVM', 'XGBOOST', 'DECISION_TREE', 'LINEAR_REGRESSION', 'KNN', name='algorithm', create_type=False), nullable=False),
    sa.Column('hyperparameters', sa.JSON(), nullable=False),
    sa.Column('test_size', sa.Float(), nullable=False),
    sa.Column('random_state', sa.Integer(), nullable=False),
    sa.Column('cross_validation', sa.Boolean(), nullable=False),
    sa.Column('cv_folds', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('run_id')
    )


def downgrade() -> None:
    op.drop_table('training_configs')
    op.drop_index(op.f('ix_runs_status'), table_name='runs')
    op.drop_index(op.f('ix_runs_environment_id'), table_name='runs')
    op.drop_table('runs')
    algorithm_enum.drop(op.get_bind(), checkfirst=True)
    runstatus_enum.drop(op.get_bind(), checkfirst=True)