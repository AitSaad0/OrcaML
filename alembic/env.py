from logging.config import fileConfig
from alembic import context

from src.config.config import settings
from src.config.db import Base
from src.auth.models.user import User  # noqa: F401
from src.project.models.project import Project  # noqa: F401
from src.environment.models.Environment import Environment  # noqa: F401
from src.environment.models.Task_type import TaskType  # noqa: F401
from src.environment.models.Environment_status import EnvironmentStatus  # noqa: F401
from src.dataset.models.dataset import Dataset  # noqa: F401

# =========================
# IMPORT MODELS (IMPORTANT)
# =========================
import src.models  # noqa: F401

# =========================
# ALEMBIC CONFIG
# =========================
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# DB URL
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)