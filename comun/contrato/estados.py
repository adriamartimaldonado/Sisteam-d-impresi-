# -*- coding: utf-8 -*-
"""Contrato COMPARTIDO entre central y puesto: estados, roles y version de API.

Vive en `comun/` a proposito: es la unica fuente de verdad de los estados y las
transiciones. Si cambia el protocolo, cambia AQUI y en un solo commit las dos
mitades quedan alineadas (monorepo, decision D9 del documento de contexto).

No importa nada de central/ ni de puesto/: es la base de la que dependen ambos.
"""

from __future__ import annotations

from enum import Enum


# Version del contrato de API. Los puestos y el central la comparan para no
# hablar idiomas distintos tras una actualizacion parcial.
API_VERSION = "1"


class Rol(str, Enum):
    """Rol asociado a cada API key (cabecera X-API-Key). Decision D7/§10."""
    ORIGEN = "origen"      # crear pedidos
    PUESTO = "puesto"      # reclamar trabajo e informar resultados
    LECTURA = "lectura"    # paneles e integraciones (solo lectura)


class EstadoPedido(str, Enum):
    ABIERTO = "abierto"        # admite sesiones y hay trabajo pendiente
    EN_CURSO = "en_curso"      # hay al menos una sesion imprimiendo
    COMPLETADO = "completado"  # todos los trabajos confirmados
    CANCELADO = "cancelado"


class EstadoSesion(str, Enum):
    """Ciclo de vida de una sesion de impresion (puesto + pedido). §6.1.

        abierta -> calibrando -> preparada -> imprimiendo -> cerrada
                       |                          |
                       +----> abortada <----------+
    """
    ABIERTA = "abierta"          # cogio plaza (segun max_puestos) y descargo el paquete
    CALIBRANDO = "calibrando"    # calibrando + etiquetas de prueba (se cuentan aparte)
    PREPARADA = "preparada"      # una persona valido la prueba: AQUI empieza produccion
    IMPRIMIENDO = "imprimiendo"  # reclamando y enviando bloques
    CERRADA = "cerrada"          # el pedido se acabo o el operario paro
    ABORTADA = "abortada"        # cancelada en preparacion, o puesto sin señales


class EstadoTrabajo(str, Enum):
    """Ciclo de vida de un trabajo = una etiqueta. §6.2.

        pendiente -> reclamado -> enviado -> confirmado
             ^           |           |
             |           |           +--> fallido --+
             +-----------+--------------------------+
               (vuelve a la cola por caducidad o reintento)

    OJO (§8): `enviado` = "salieron los bytes por el socket"; `confirmado` = "la
    impresora dice que lo hizo". NO son lo mismo y no deben mezclarse.
    """
    PENDIENTE = "pendiente"      # en la cola, nadie lo ha cogido
    RECLAMADO = "reclamado"      # un puesto lo cogio en exclusiva (lleva reclamado_en)
    ENVIADO = "enviado"          # bytes enviados al 9100 (aun no confirmado)
    CONFIRMADO = "confirmado"    # la impresora confirmo la impresion
    FALLIDO = "fallido"          # fallo; puede volver a la cola para reintento


# Transiciones validas (origen -> destinos permitidos). Sirve para que ambos
# lados validen igual y para tests. No cubre el rescate por caducidad, que lo
# hace el central devolviendo RECLAMADO -> PENDIENTE por barrido temporal.
TRANSICIONES_SESION: dict[EstadoSesion, frozenset[EstadoSesion]] = {
    EstadoSesion.ABIERTA: frozenset({EstadoSesion.CALIBRANDO, EstadoSesion.ABORTADA}),
    EstadoSesion.CALIBRANDO: frozenset({EstadoSesion.PREPARADA, EstadoSesion.ABORTADA}),
    EstadoSesion.PREPARADA: frozenset({EstadoSesion.IMPRIMIENDO, EstadoSesion.ABORTADA}),
    EstadoSesion.IMPRIMIENDO: frozenset({EstadoSesion.CERRADA, EstadoSesion.ABORTADA}),
    EstadoSesion.CERRADA: frozenset(),
    EstadoSesion.ABORTADA: frozenset(),
}

TRANSICIONES_TRABAJO: dict[EstadoTrabajo, frozenset[EstadoTrabajo]] = {
    EstadoTrabajo.PENDIENTE: frozenset({EstadoTrabajo.RECLAMADO}),
    EstadoTrabajo.RECLAMADO: frozenset({EstadoTrabajo.ENVIADO, EstadoTrabajo.PENDIENTE}),
    EstadoTrabajo.ENVIADO: frozenset({EstadoTrabajo.CONFIRMADO, EstadoTrabajo.FALLIDO}),
    EstadoTrabajo.FALLIDO: frozenset({EstadoTrabajo.PENDIENTE, EstadoTrabajo.RECLAMADO}),
    EstadoTrabajo.CONFIRMADO: frozenset(),
}


def transicion_valida(actual: EstadoTrabajo, siguiente: EstadoTrabajo) -> bool:
    """True si se puede pasar de `actual` a `siguiente` (trabajo)."""
    return siguiente in TRANSICIONES_TRABAJO.get(actual, frozenset())
