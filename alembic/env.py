from __future__ import annotations

import os
import re
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

# ---------------------------------------------------------------------------
# Load .env so DATABASE_URL is available
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# Alembic Config
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Convert asyncpg URL → psycopg2 URL for Alembic's sync engine
# e.g. postgresql+asyncpg://... → postgresql+psycopg2://...
# ---------------------------------------------------------------------------
raw_url = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:devpassword@localhost:5432/fl_outbreak",
)
sync_url = re.sub(r"^postgresql\+asyncpg", "postgresql+psycopg2", raw_url)
config.set_main_option("sqlalchemy.url", sync_url)

# ---------------------------------------------------------------------------
# Import all models so autogenerate sees them
# ---------------------------------------------------------------------------
from backend.models.database import Base  # noqa: E402

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live DB connection."""
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
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
