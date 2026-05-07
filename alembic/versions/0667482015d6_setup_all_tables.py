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
    # 1. Table Users
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(), nullable=False)
    )
    # 2. Table Projects
    op.create_table('projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'))
    )
    # 3. Table Environments
    op.create_table('environments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id'))
    )
    # 4. Table Cleaning Configs
    op.create_table('cleaning_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('environment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('environments.id'), nullable=False),
        sa.Column('missing_strategy', sa.String(), nullable=False),
        sa.Column('remove_duplicates', sa.Boolean(), default=True),
        sa.Column('encoding_method', sa.String(), nullable=False),
        sa.Column('scaling_method', sa.String(), nullable=False),
        sa.Column('version', sa.String(), default="V1"),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    # 5. Table Cleaned Datasets
    op.create_table('cleaned_datasets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('environment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('environments.id'), nullable=False),
        sa.Column('cleaning_config_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cleaning_configs.id'), nullable=False),
        sa.Column('file_path', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )

def downgrade():
    op.drop_table('cleaned_datasets')
    op.drop_table('cleaning_configs')
    op.drop_table('environments')
    op.drop_table('projects')
    op.drop_table('users')