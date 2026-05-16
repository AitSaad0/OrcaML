"""add datasets and update schema

Revision ID: 7048f6ea679f
Revises: 0667482015d6
Create Date: 2026-05-06 21:21:19.800531

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7048f6ea679f'
down_revision: Union[str, Sequence[str], None] = '0667482015d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Créer les enums de façon sécurisée
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE missingstrategy AS ENUM ('DROP_ROWS', 'DROP_COLUMN', 'MEAN', 'MEDIAN', 'MODE', 'CONSTANT', 'FORWARD_FILL');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE encodingmethod AS ENUM ('LABEL', 'ONE_HOT', 'ORDINAL', 'BINARY');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE scalingmethod AS ENUM ('MIN_MAX', 'STANDARD', 'ROBUST', 'LOG');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE cleaningversion AS ENUM ('V1', 'V2', 'V3');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE tasktype AS ENUM ('CLASSIFICATION', 'REGRESSION');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE environmentstatus AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELED');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    # Le reste du fichier reste identique...

    # Alter enum columns via raw SQL (requires USING cast)
    op.execute("ALTER TABLE cleaning_configs ALTER COLUMN missing_strategy TYPE missingstrategy USING missing_strategy::missingstrategy")
    op.execute("ALTER TABLE cleaning_configs ALTER COLUMN encoding_method TYPE encodingmethod USING encoding_method::encodingmethod")
    op.execute("ALTER TABLE cleaning_configs ALTER COLUMN scaling_method TYPE scalingmethod USING scaling_method::scalingmethod")
    op.execute("ALTER TABLE cleaning_configs ALTER COLUMN version TYPE cleaningversion USING version::cleaningversion")
    op.execute("ALTER TABLE cleaning_configs ALTER COLUMN version SET NOT NULL")

    op.create_table('datasets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('r2_path', sa.String(), nullable=False),
        sa.Column('env_id', sa.UUID(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['env_id'], ['environments.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.add_column('cleaned_datasets', sa.Column('rows_before', sa.Integer(), nullable=True))
    op.add_column('cleaned_datasets', sa.Column('rows_after', sa.Integer(), nullable=True))
    op.add_column('cleaned_datasets', sa.Column('columns_dropped', sa.Integer(), nullable=True))
    op.add_column('cleaned_datasets', sa.Column('cleaned_at', sa.DateTime(timezone=True), nullable=True))
    op.alter_column('cleaning_configs', 'remove_duplicates',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.add_column('environments', sa.Column('name', sa.String(), nullable=False))
    op.add_column('environments', sa.Column('target_column', sa.String(), nullable=False))
    op.add_column('environments', sa.Column('task_type', sa.Enum('CLASSIFICATION', 'REGRESSION', name='tasktype'), nullable=False))
    op.add_column('environments', sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELED', name='environmentstatus'), nullable=False))
    op.add_column('environments', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.alter_column('environments', 'project_id',
               existing_type=sa.UUID(),
               nullable=False)
    op.add_column('projects', sa.Column('description', sa.String(), nullable=True))
    op.add_column('projects', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.alter_column('projects', 'user_id',
               existing_type=sa.UUID(),
               nullable=False)
    op.add_column('users', sa.Column('password_hash', sa.String(), nullable=False))
    op.add_column('users', sa.Column('full_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.drop_constraint(op.f('users_email_key'), 'users', type_='unique')
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.drop_column('users', 'hashed_password')

def downgrade() -> None:
    op.add_column('users', sa.Column('hashed_password', sa.VARCHAR(), autoincrement=False, nullable=False))
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.create_unique_constraint(op.f('users_email_key'), 'users', ['email'], postgresql_nulls_not_distinct=False)
    op.drop_column('users', 'created_at')
    op.drop_column('users', 'full_name')
    op.drop_column('users', 'password_hash')
    op.alter_column('projects', 'user_id', existing_type=sa.UUID(), nullable=True)
    op.drop_column('projects', 'created_at')
    op.drop_column('projects', 'description')
    op.alter_column('environments', 'project_id', existing_type=sa.UUID(), nullable=True)
    op.drop_column('environments', 'created_at')
    op.drop_column('environments', 'status')
    op.drop_column('environments', 'task_type')
    op.drop_column('environments', 'target_column')
    op.drop_column('environments', 'name')
    op.alter_column('cleaning_configs', 'remove_duplicates', existing_type=sa.BOOLEAN(), nullable=True)

    # Drop NOT NULL before converting back to VARCHAR
    op.execute("ALTER TABLE cleaning_configs ALTER COLUMN version DROP NOT NULL")
    op.execute("ALTER TABLE cleaning_configs ALTER COLUMN version TYPE VARCHAR USING version::VARCHAR")
    op.execute("ALTER TABLE cleaning_configs ALTER COLUMN scaling_method TYPE VARCHAR USING scaling_method::VARCHAR")
    op.execute("ALTER TABLE cleaning_configs ALTER COLUMN encoding_method TYPE VARCHAR USING encoding_method::VARCHAR")
    op.execute("ALTER TABLE cleaning_configs ALTER COLUMN missing_strategy TYPE VARCHAR USING missing_strategy::VARCHAR")

    op.drop_column('cleaned_datasets', 'cleaned_at')
    op.drop_column('cleaned_datasets', 'columns_dropped')
    op.drop_column('cleaned_datasets', 'rows_after')
    op.drop_column('cleaned_datasets', 'rows_before')
    op.drop_table('datasets')
    # Drop enum types last
    op.execute("DROP TYPE IF EXISTS missingstrategy")
    op.execute("DROP TYPE IF EXISTS encodingmethod")
    op.execute("DROP TYPE IF EXISTS scalingmethod")
    op.execute("DROP TYPE IF EXISTS cleaningversion")
    op.execute("DROP TYPE IF EXISTS tasktype")
    op.execute("DROP TYPE IF EXISTS environmentstatus")
    