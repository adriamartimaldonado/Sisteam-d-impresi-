# -*- coding: utf-8 -*-
"""Motor SQLAlchemy y sesion de base de datos del central."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import cargar_config

_config = cargar_config()

# pool_pre_ping: reconecta si Postgres cerro la conexion (fiabilidad en produccion).
engine = create_engine(_config.database_url, pool_pre_ping=True, future=True)
FabricaSesion = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False,
                            class_=Session)


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesion por peticion, cerrada al terminar."""
    db = FabricaSesion()
    try:
        yield db
    finally:
        db.close()
