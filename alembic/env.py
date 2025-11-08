# alembic/env.py

import os
import sys
import importlib
from logging.config import fileConfig
from pathlib import Path
from sqlalchemy import engine_from_config, pool
from alembic import context

# Добавляем корень проекта в Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Импортируем Base
from utils.db import Base, ENGINE_URL

config = context.config

# Настройка логирования
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def import_models_dynamically():
    """Динамически импортирует все модули из папки models"""
    models_path = Path(__file__).parent.parent / "models"

    for file_path in models_path.glob("*.py"):
        if file_path.name == "__init__.py":
            continue

        module_name = f"models.{file_path.stem}"
        try:
            importlib.import_module(module_name)
            print(f"✅ Импортирован модуль: {module_name}")
        except ImportError as e:
            print(f"⚠️  Не удалось импортировать {module_name}: {e}")


# Импортируем все модели
import_models_dynamically()

target_metadata = Base.metadata

alembic_config = {
    'target_metadata': target_metadata,
    'render_as_batch': True,
    'compare_type': True,
    'compare_server_default': True,
    # Принудительно включаем генерацию имен
    'naming_convention': {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    }
}


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **alembic_config
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        {"sqlalchemy.url": ENGINE_URL},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            **alembic_config
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()