from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from src.config.config import settings
from src.config.db import Base

# =========================
# IMPORT MODELS (IMPORTANT)
# =========================
# Force l'enregistrement de tous les modèles dans Base.metadata
import src.models  # noqa: F401

# =========================
# ALEMBIC CONFIG
# =========================
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata pour autogenerate
target_metadata = Base.metadata

# DB URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


# =========================
# OFFLINE MODE
# =========================
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# =========================
# ONLINE MODE
# =========================
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# =========================
# ENTRY POINT
# =========================
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()