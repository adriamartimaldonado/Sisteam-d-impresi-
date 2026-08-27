# -*- coding: utf-8 -*-
"""Contrato compartido central <-> puesto."""

from .estados import (
    API_VERSION,
    EstadoPedido,
    EstadoSesion,
    EstadoTrabajo,
    Rol,
    TRANSICIONES_SESION,
    TRANSICIONES_TRABAJO,
    transicion_valida,
)

__all__ = [
    "API_VERSION",
    "Rol",
    "EstadoPedido",
    "EstadoSesion",
    "EstadoTrabajo",
    "TRANSICIONES_SESION",
    "TRANSICIONES_TRABAJO",
    "transicion_valida",
]
