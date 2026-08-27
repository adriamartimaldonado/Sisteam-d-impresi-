# -*- coding: utf-8 -*-
"""Entorno de Alembic. Pone la raiz del repo en sys.path para importar `comun` y
`central.app`, y toma la URL de la BD del entorno (nunca del .ini)."""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# --- rutas: raiz del repo (dos niveles por encima de este archivo) ---
_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.abspath(os.path.join(_AQUI, "..", ".."))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from central.app.config import cargar_config   # noqa: E402
from central.app.modelos import Base            # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# La URL manda desde el entorno.
config.set_main_option("sqlalchemy.url", cargar_config().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
