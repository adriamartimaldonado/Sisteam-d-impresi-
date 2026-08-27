# -*- coding: utf-8 -*-
"""Aplicacion FastAPI del central."""

from __future__ import annotations

from fastapi import FastAPI

from comun.contrato import API_VERSION
from .rutas import pedidos


def crear_app() -> FastAPI:
    app = FastAPI(
        title="Central de impresion de etiquetas",
        version=API_VERSION,
        description="Dueño de la verdad: pedidos, trabajos, sesiones y flota.",
    )

    @app.get("/salud", tags=["infra"])
    def salud():
        return {"ok": True, "api": API_VERSION}

    app.include_router(pedidos.router)
    return app


app = crear_app()
