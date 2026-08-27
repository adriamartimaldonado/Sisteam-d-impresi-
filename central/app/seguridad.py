# -*- coding: utf-8 -*-
"""Autenticacion por API key (cabecera X-API-Key), decision D7/§10.

Las claves se guardan SOLO hasheadas (SHA-256). Son tokens aleatorios de alta
entropia, no contraseñas humanas, asi que un hash rapido es lo correcto (igual que
los tokens de GitHub); bcrypt aqui no aporta y si complica.
"""

from __future__ import annotations

import hashlib
import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from comun.contrato import Rol
from .db import get_db
from .modelos import ClienteApi


def hash_clave(clave: str) -> str:
    """SHA-256 en hex de la clave. Deterministico: sirve para buscar en la BD."""
    return hashlib.sha256(clave.encode("utf-8")).hexdigest()


def generar_clave() -> tuple[str, str]:
    """Crea una clave nueva. Devuelve (clave_plana, hash). La plana se enseña UNA vez."""
    plana = secrets.token_urlsafe(32)
    return plana, hash_clave(plana)


def cliente_actual(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> ClienteApi:
    """Dependencia: valida la X-API-Key y devuelve el cliente activo, o 401."""
    if not x_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta la cabecera X-API-Key")
    cliente = db.scalar(
        select(ClienteApi).where(
            ClienteApi.clave_hash == hash_clave(x_api_key),
            ClienteApi.activo.is_(True),
        )
    )
    if cliente is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key invalida o inactiva")
    return cliente


def requiere(*roles: Rol):
    """Devuelve una dependencia que exige que el cliente tenga uno de esos roles."""
    permitidos = {r.value for r in roles}

    def _dep(cliente: ClienteApi = Depends(cliente_actual)) -> ClienteApi:
        if cliente.rol not in permitidos:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"El rol '{cliente.rol}' no puede hacer esta operacion",
            )
        return cliente

    return _dep
