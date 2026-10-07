"""Alembic entry point; migrations use the owner role."""

import os

from alembic import context
from sqlalchemy import create_engine, pool

from backend.app.config import get_settings

url = os.getenv("MIGRATION_DATABASE_URL", get_settings().database_url)
if context.is_offline_mode():
    context.configure(url=url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
