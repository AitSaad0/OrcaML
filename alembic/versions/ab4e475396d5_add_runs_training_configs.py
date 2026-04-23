"""add_runs_training_configs

Revision ID: ab4e475396d5
Revises: 95fd74d77755
Create Date: 2026-04-12 18:09:00.375044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM


revision: str = 'ab4e475396d5'
down_revision: Union[str, Sequence[str], None] = '95fd74d77755'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

algorithm_enum = ENUM(
    'LOGISTIC_REGRESSION', 'RANDOM_FOREST', 'SVM',
    'DECISION_TREE', 'LINEAR_REGRESSION', 'KNN',  # ← XGBOOST supprimé
    name='algorithm',
    create_type=False  # ← on gère la création manuellement
)

runstatus_enum = ENUM(
    'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED',
    name='runstatus',
    create_type=False  # ← idem
)


def upgrade() -> None:
    bind = op.get_bind()

    # Créer les enums manuellement avec checkfirst
    ENUM('LOGISTIC_REGRESSION', 'RANDOM_FOREST', 'SVM',
         'DECISION_TREE', 'LINEAR_REGRESSION', 'KNN',
         name='algorithm').create(bind, checkfirst=True)

    ENUM('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED',
         name='runstatus').create(bind, checkfirst=True)

    # Créer la table runs seulement si elle n'existe pas
    if not op.get_bind().dialect.has_table(bind, 'runs'):
        op.create_table('runs',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('environment_id', sa.UUID(), nullable=False),
            sa.Column('algorithm', algorithm_enum, nullable=False),
            sa.Column('status', runstatus_enum, nullable=False),
            sa.Column('mlflow_run_id', sa.String(length=255), nullable=True),
            sa.Column('celery_task_id', sa.String(length=255), nullable=True),
            sa.Column('accuracy', sa.Float(), nullable=True),
            sa.Column('f1_score', sa.Float(), nullable=True),
            sa.Column('precision', sa.Float(), nullable=True),
            sa.Column('recall', sa.Float(), nullable=True),
            sa.Column('duration_seconds', sa.Float(), nullable=True),
            sa.Column('is_manual', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['environment_id'], ['environments.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_runs_environment_id'), 'runs', ['environment_id'], unique=False)
        op.create_index(op.f('ix_runs_status'), 'runs', ['status'], unique=False)

    # Créer training_configs seulement si elle n'existe pas
    if not op.get_bind().dialect.has_table(bind, 'training_configs'):
        op.create_table('training_configs',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('run_id', sa.UUID(), nullable=False),
            sa.Column('algorithm', algorithm_enum, nullable=False),
            sa.Column('hyperparameters', sa.JSON(), nullable=False),
            sa.Column('test_size', sa.Float(), nullable=False),
            sa.Column('random_state', sa.Integer(), nullable=False),
            sa.Column('cross_validation', sa.Boolean(), nullable=False),
            sa.Column('cv_folds', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('run_id'),
        )


def downgrade() -> None:
    bind = op.get_bind()

    if op.get_bind().dialect.has_table(bind, 'training_configs'):
        op.drop_table('training_configs')

    if op.get_bind().dialect.has_table(bind, 'runs'):
        op.drop_index(op.f('ix_runs_status'), table_name='runs')
        op.drop_index(op.f('ix_runs_environment_id'), table_name='runs')
        op.drop_table('runs')

    ENUM(name='algorithm').drop(bind, checkfirst=True)
    ENUM(name='runstatus').drop(bind, checkfirst=True)