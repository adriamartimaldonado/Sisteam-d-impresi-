# -*- coding: utf-8 -*-
"""Esquemas Pydantic de entrada/salida de la API del central."""

from __future__ import annotations

from pydantic import BaseModel


class PedidoCreado(BaseModel):
    pedido_id: int
    estado: str
    n_trabajos: int
    idempotente: bool = False   # True si ya existia (misma clave_idem) y no se recreo


class ErrorExcel(BaseModel):
    rechazado: bool = True
    total_errores: int
    errores: list[dict]         # {fila, columna, motivo}


class PedidoResumen(BaseModel):
    pedido_id: int
    estado: str
    max_puestos: int
    pendientes: int
    plazas_libres: int
