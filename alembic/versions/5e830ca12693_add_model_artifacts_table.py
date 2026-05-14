"""add_model_artifacts_table

Revision ID: 5e830ca12693
Revises: aad88b893095
Create Date: 2026-05-09 21:51:02.343680

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '5e830ca12693'
down_revision: Union[str, Sequence[str], None] = 'aad88b893095'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Créer la table models (ModelArtifact)
    op.create_table(
        'models',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('run_id', sa.UUID(), nullable=False),
        sa.Column('environment_id', sa.UUID(), nullable=False),
        sa.Column('algorithm', sa.String(100), nullable=False),
        sa.Column('mlflow_run_id', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['environment_id'], ['environments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id'),
    )
    op.create_index('ix_models_run_id', 'models', ['run_id'])
    op.create_index('ix_models_environment_id', 'models', ['environment_id'])

    # Créer la table deployments
    op.create_table(
        'deployments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('model_id', sa.UUID(), nullable=False),
        sa.Column('environment_id', sa.UUID(), nullable=False),
        sa.Column('container_id', sa.String(255), nullable=True),
        sa.Column('container_name', sa.String(255), nullable=True),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('endpoint_url', sa.String(500), nullable=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('total_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_called_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deployed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stopped_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['environment_id'], ['environments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_deployments_environment_id', 'deployments', ['environment_id'])
    op.create_index('ix_deployments_status', 'deployments', ['status'])


def downgrade() -> None:
    op.drop_index('ix_deployments_status', table_name='deployments')
    op.drop_index('ix_deployments_environment_id', table_name='deployments')
    op.drop_table('deployments')
    op.drop_index('ix_models_environment_id', table_name='models')
    op.drop_index('ix_models_run_id', table_name='models')
    op.drop_table('models')