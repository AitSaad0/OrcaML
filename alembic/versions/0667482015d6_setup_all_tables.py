"""setup_all_tables
Revision ID: 0667482015d6
Revises: 
Create Date: 2026-05-06 16:05:37
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0667482015d6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = inspector.get_table_names()

    # 1. Table Users
    if 'users' not in existing:
        op.create_table('users',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('email', sa.String(), nullable=False, unique=True),
            sa.Column('hashed_password', sa.String(), nullable=False)
        )

    # 2. Table Projects
    if 'projects' not in existing:
        op.create_table('projects',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'))
        )

    # 3. Table Environments
    if 'environments' not in existing:
        op.create_table('environments',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id'))
        )

    # 4. Table Cleaning Configs
    if 'cleaning_configs' not in existing:
        op.create_table('cleaning_configs',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('environment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('environments.id'), nullable=False),
            sa.Column('missing_strategy', sa.String(), nullable=False),
            sa.Column('remove_duplicates', sa.Boolean(), default=True),
            sa.Column('encoding_method', sa.String(), nullable=False),
            sa.Column('scaling_method', sa.String(), nullable=False),
            sa.Column('version', sa.String(), default='V1'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
        )

    # 5. Table Cleaned Datasets
    if 'cleaned_datasets' not in existing:
        op.create_table('cleaned_datasets',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('environment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('environments.id'), nullable=False),
            sa.Column('cleaning_config_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cleaning_configs.id'), nullable=False),
            sa.Column('file_path', sa.String(), nullable=True),
            sa.Column('status', sa.String(), nullable=False, server_default='pending'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
        )

    # 6. Table Runs
    if 'runs' not in existing:
        op.create_table('runs',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('environment_id', postgresql.UUID(as_uuid=True),
                      sa.ForeignKey('environments.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('algorithm', sa.Enum(
                'LOGISTIC_REGRESSION', 'RANDOM_FOREST', 'SVM', 'DECISION_TREE',
                'LINEAR_REGRESSION', 'KNN', 'XGBOOST', name='algorithm'
            ), nullable=False),
            sa.Column('status', sa.Enum(
                'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', name='runstatus'
            ), nullable=False, server_default='PENDING', index=True),
            sa.Column('mlflow_run_id', sa.String(255), nullable=True),
            sa.Column('celery_task_id', sa.String(255), unique=True, nullable=True),
            sa.Column('accuracy', sa.Float(), nullable=True),
            sa.Column('f1_score', sa.Float(), nullable=True),
            sa.Column('precision', sa.Float(), nullable=True),
            sa.Column('recall', sa.Float(), nullable=True),
            sa.Column('rmse', sa.Float(), nullable=True),
            sa.Column('mae', sa.Float(), nullable=True),
            sa.Column('r2', sa.Float(), nullable=True),
            sa.Column('duration_seconds', sa.Float(), nullable=True),
            sa.Column('is_manual', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        )

    # 7. Table Training Configs
    if 'training_configs' not in existing:
        op.create_table('training_configs',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('run_id', postgresql.UUID(as_uuid=True),
                      sa.ForeignKey('runs.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('algorithm', sa.Enum(
                'LOGISTIC_REGRESSION', 'RANDOM_FOREST', 'SVM', 'DECISION_TREE',
                'LINEAR_REGRESSION', 'KNN', 'XGBOOST', name='algorithm', create_type=False
            ), nullable=False),
            sa.Column('hyperparameters', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('test_size', sa.Float(), nullable=False, server_default='0.2'),
            sa.Column('random_state', sa.Integer(), nullable=False, server_default='42'),
            sa.Column('cross_validation', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('cv_folds', sa.Integer(), nullable=False, server_default='5'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )


def downgrade():
    op.drop_table('training_configs')
    op.drop_table('runs')
    op.drop_table('cleaned_datasets')
    op.drop_table('cleaning_configs')
    op.drop_table('environments')
    op.drop_table('projects')
    op.drop_table('users')
    sa.Enum(name='algorithm').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='runstatus').drop(op.get_bind(), checkfirst=True)