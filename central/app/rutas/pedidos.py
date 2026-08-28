# -*- coding: utf-8 -*-
"""Rutas de pedidos: crear (valida Excel + expande a trabajos) y listar."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from comun.contrato import EstadoSesion, EstadoTrabajo, Rol
from ..db import get_db
from ..esquemas import ErrorExcel, PedidoCreado, PedidoResumen
from ..excel import Campo, ExcelInvalido, abrir_filas, validar
from ..modelos import Evento, Pedido, Plantilla, Sesion, Trabajo
from ..seguridad import cliente_actual, requiere

router = APIRouter(prefix="/v1/pedidos", tags=["pedidos"])

_SESIONES_ACTIVAS = (
    EstadoSesion.ABIERTA.value, EstadoSesion.CALIBRANDO.value,
    EstadoSesion.PREPARADA.value, EstadoSesion.IMPRIMIENDO.value,
)


def _campos_de_plantilla(plantilla: Plantilla) -> list[Campo]:
    spec = plantilla.campos or []
    if not isinstance(spec, list):
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            "La plantilla tiene 'campos' con formato invalido")
    return [Campo.desde_dict(d) for d in spec]


@router.post("", response_model=PedidoCreado)
async def crear_pedido(
    excel: UploadFile = File(..., description="Excel de referencia del pedido"),
    plantilla_codigo: str = Form(...),
    clave_idem: str = Form(..., description="Clave de idempotencia del pedido"),
    plantilla_version: int | None = Form(None),
    max_puestos: int = Form(1),
    prioridad: int = Form(0),
    config: str = Form("{}", description="JSON con las configuraciones del pedido"),
    hoja: str | None = Form(None),
    cliente=Depends(requiere(Rol.ORIGEN)),
    db: Session = Depends(get_db),
):
    """Crea un pedido: valida el Excel ENTERO y lo expande a N trabajos.

    Idempotente por `clave_idem`: repetir la misma llamada no crea trabajos de mas.
    Si el Excel falla, se rechaza el pedido completo (422) con fila y motivo.
    """
    # 1) Idempotencia: si ya existe ese clave_idem, se devuelve el pedido existente.
    existente = db.scalar(select(Pedido).where(Pedido.clave_idem == clave_idem))
    if existente is not None:
        n = db.scalar(select(func.count()).select_from(Trabajo)
                      .where(Trabajo.pedido_id == existente.id)) or 0
        return PedidoCreado(pedido_id=existente.id, estado=existente.estado,
                            n_trabajos=int(n), idempotente=True)

    # 2) Configuracion (JSON).
    try:
        config_dict = json.loads(config) if config else {}
        if not isinstance(config_dict, dict):
            raise ValueError("debe ser un objeto JSON")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"config invalido: {exc}")

    # 3) Plantilla (version concreta o la mayor si no se indica).
    consulta = select(Plantilla).where(Plantilla.codigo == plantilla_codigo)
    if plantilla_version is not None:
        consulta = consulta.where(Plantilla.version == plantilla_version)
    else:
        consulta = consulta.order_by(Plantilla.version.desc())
    plantilla = db.scalars(consulta).first()
    if plantilla is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"No existe la plantilla '{plantilla_codigo}'"
                            + (f" v{plantilla_version}" if plantilla_version else ""))

    # 4) Leer y validar el Excel ENTERO.
    contenido = await excel.read()
    try:
        cabeceras, filas = abrir_filas(contenido, hoja)
    except ExcelInvalido as exc:
        raise HTTPException(422, str(exc))

    datos, errores = validar(cabeceras, filas, _campos_de_plantilla(plantilla))
    if errores:
        detalle = ErrorExcel(total_errores=len(errores),
                             errores=[e.como_dict() for e in errores])
        raise HTTPException(422, detalle.model_dump())
    if not datos:
        raise HTTPException(422,
                            "El Excel no tiene ninguna fila de datos")

    # 5) Crear pedido + trabajos + evento, en una transaccion.
    pedido = Pedido(
        sede_id=cliente.sede_id, clave_idem=clave_idem, plantilla_id=plantilla.id,
        config=config_dict, max_puestos=max_puestos, prioridad=prioridad,
        creado_por=cliente.id,
    )
    db.add(pedido)
    db.flush()   # asigna pedido.id sin cerrar la transaccion

    db.add_all([
        Trabajo(pedido_id=pedido.id, orden=i, datos=registro,
                estado=EstadoTrabajo.PENDIENTE.value)
        for i, registro in enumerate(datos)
    ])
    db.add(Evento(tipo="pedido_creado", pedido_id=pedido.id,
                  datos={"n_trabajos": len(datos), "plantilla": plantilla.codigo}))
    db.commit()

    return PedidoCreado(pedido_id=pedido.id, estado=pedido.estado,
                        n_trabajos=len(datos), idempotente=False)


@router.get("", response_model=list[PedidoResumen])
def listar_pedidos(
    cliente=Depends(cliente_actual),
    db: Session = Depends(get_db),
):
    """Pedidos con trabajo pendiente y sus plazas libres (para puestos y panel)."""
    pedidos = db.scalars(select(Pedido).order_by(Pedido.prioridad.desc(), Pedido.id)).all()
    salida: list[PedidoResumen] = []
    for p in pedidos:
        pendientes = db.scalar(
            select(func.count()).select_from(Trabajo)
            .where(Trabajo.pedido_id == p.id,
                   Trabajo.estado == EstadoTrabajo.PENDIENTE.value)) or 0
        if pendientes == 0:
            continue
        activas = db.scalar(
            select(func.count()).select_from(Sesion)
            .where(Sesion.pedido_id == p.id, Sesion.estado.in_(_SESIONES_ACTIVAS))) or 0
        salida.append(PedidoResumen(
            pedido_id=p.id, estado=p.estado, max_puestos=p.max_puestos,
            pendientes=int(pendientes), plazas_libres=max(0, p.max_puestos - int(activas)),
        ))
    return salida
