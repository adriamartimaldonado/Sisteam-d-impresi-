# -*- coding: utf-8 -*-
"""Tests del contrato compartido. Que el esqueleto tenga CI verde desde el commit 0."""

from comun.contrato import (
    API_VERSION,
    EstadoSesion,
    EstadoTrabajo,
    Rol,
    transicion_valida,
)


def test_api_version_es_cadena():
    assert isinstance(API_VERSION, str) and API_VERSION


def test_roles_definidos():
    assert {r.value for r in Rol} == {"origen", "puesto", "lectura"}


def test_estados_sesion_del_documento():
    assert {e.value for e in EstadoSesion} == {
        "abierta", "calibrando", "preparada", "imprimiendo", "cerrada", "abortada",
    }


def test_estados_trabajo_del_documento():
    assert {e.value for e in EstadoTrabajo} == {
        "pendiente", "reclamado", "enviado", "confirmado", "fallido",
    }


def test_transiciones_validas_de_trabajo():
    # El camino feliz.
    assert transicion_valida(EstadoTrabajo.PENDIENTE, EstadoTrabajo.RECLAMADO)
    assert transicion_valida(EstadoTrabajo.RECLAMADO, EstadoTrabajo.ENVIADO)
    assert transicion_valida(EstadoTrabajo.ENVIADO, EstadoTrabajo.CONFIRMADO)
    # Un fallido puede volver a la cola; un confirmado es terminal.
    assert transicion_valida(EstadoTrabajo.FALLIDO, EstadoTrabajo.PENDIENTE)
    assert not transicion_valida(EstadoTrabajo.CONFIRMADO, EstadoTrabajo.ENVIADO)
    # No se puede saltar de pendiente a enviado sin reclamar.
    assert not transicion_valida(EstadoTrabajo.PENDIENTE, EstadoTrabajo.ENVIADO)
