import os
import sys
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config.db import Base
from src.config.config import settings

# --- IMPORT OBLIGATOIRE ---
# Ces imports sont nécessaires pour qu'Alembic détecte les tables
# noqa comments prevent ruff from removing them
from src.auth.models.user import User  # noqa: F401
from src.project.models.project import Project  # noqa: F401
from src.environment.models.Environment import Environment  # noqa: F401
from src.dataset.models.dataset import Dataset  # noqa: F401
from src.dataset.models.cleaning_config import CleaningConfig  # noqa: F401
from src.dataset.models.cleaned_dataset import CleanedDataset  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()