# -*- coding: utf-8 -*-
"""Configuracion del central, leida del entorno (.env local, nunca versionado).

Se mantiene sin dependencias extra (nada de pydantic-settings): leer variables de
entorno con valores por defecto es mas que suficiente y una pieza menos que pueda
fallar en produccion.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _cargar_dotenv() -> None:
    """Carga un `.env` de la raiz del repo si existe, sin depender de python-dotenv.

    Solo rellena variables que no esten ya en el entorno (el entorno manda).
    """
    aqui = os.path.dirname(os.path.abspath(__file__))
    raiz = os.path.abspath(os.path.join(aqui, "..", ".."))
    ruta = os.path.join(raiz, ".env")
    if not os.path.isfile(ruta):
        return
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip())


@dataclass(frozen=True)
class Config:
    database_url: str
    host: str
    port: int
    sede_defecto: str


def cargar_config() -> Config:
    _cargar_dotenv()
    return Config(
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg2://etiquetas:etiquetas@localhost:5432/etiquetas",
        ),
        host=os.environ.get("CENTRAL_HOST", "0.0.0.0"),
        port=int(os.environ.get("CENTRAL_PORT", "8000")),
        sede_defecto=os.environ.get("SEDE_DEFECTO", "nave1"),
    )
