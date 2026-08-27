# -*- coding: utf-8 -*-
"""Fixtures de los tests del central. Los que necesitan BD se saltan solos si no
hay un PostgreSQL disponible (en CI lo hay como servicio)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from central.app.db import get_db
from central.app.main import app
from central.app.modelos import Base, ClienteApi, Plantilla, Sede
from central.app.seguridad import generar_clave

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://etiquetas:etiquetas@localhost:5432/etiquetas_test",
)


@pytest.fixture(scope="session")
def engine():
    try:
        eng = create_engine(DB_URL, future=True)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as exc:                       # noqa: BLE001
        pytest.skip(f"PostgreSQL no disponible: {exc}")
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def db(engine):
    """Sesion limpia por test: vacia todas las tablas antes de empezar."""
    Fabrica = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = Fabrica()
    for tabla in reversed(Base.metadata.sorted_tables):
        s.execute(tabla.delete())
    s.commit()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def origen_key(db) -> str:
    """Crea sede + plantilla demo + una API key de origen. Devuelve la clave plana."""
    sede = Sede(codigo="test", nombre="Test")
    db.add(sede)
    db.flush()
    db.add(Plantilla(codigo="demo", version=1, contenido="^XA^XZ", campos=[
        {"nombre": "codigo", "requerido": True, "tipo": "texto"},
        {"nombre": "gtin", "requerido": True, "tipo": "gtin"},
        {"nombre": "epc", "requerido": False, "tipo": "epc", "unico": True},
    ]))
    plana, h = generar_clave()
    db.add(ClienteApi(sede_id=sede.id, nombre="origen", rol="origen",
                      clave_hash=h, activo=True))
    db.commit()
    return plana


@pytest.fixture
def client(engine, db):
    """TestClient de FastAPI con la sesion apuntando a la BD de test."""
    from fastapi.testclient import TestClient

    Fabrica = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _get_db():
        s = Fabrica()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
