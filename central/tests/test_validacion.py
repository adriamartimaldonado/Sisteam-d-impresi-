# -*- coding: utf-8 -*-
"""Tests de la validacion del Excel (§14). Puros: no necesitan base de datos."""

from io import BytesIO

from openpyxl import Workbook

from central.app.excel import Campo, abrir_filas, validar

CAMPOS = [
    Campo("codigo", requerido=True, tipo="texto"),
    Campo("gtin", requerido=True, tipo="gtin"),
    Campo("epc", requerido=False, tipo="epc", unico=True),
]

GTIN = "4006381333931"     # GTIN-13 con digito de control correcto


def _xlsx(filas, cabeceras=("codigo", "gtin", "epc")) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(list(cabeceras))
    for f in filas:
        ws.append(list(f))
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


def test_fichero_bueno_conserva_ceros():
    cab, filas = abrir_filas(_xlsx([
        ("0012345", GTIN, f"{1:024X}"),
        ("0012346", GTIN, f"{2:024X}"),
        ("0012347", GTIN, ""),           # epc no requerido: vacio permitido
    ]))
    datos, errores = validar(cab, filas, CAMPOS)
    assert errores == []
    assert len(datos) == 3
    assert datos[0]["codigo"] == "0012345"   # el cero se conserva (leido como texto)


def test_celda_numerica_se_rechaza():
    cab, filas = abrir_filas(_xlsx([
        ("0012345", GTIN, f"{1:024X}"),
        (12346, GTIN, f"{2:024X}"),          # numero: Excel pierde el cero
    ]))
    datos, errores = validar(cab, filas, CAMPOS)
    assert datos == [] and errores
    assert errores[0].fila == 3 and errores[0].columna == "codigo"
    assert "numerica" in errores[0].motivo


def test_epc_duplicado_se_rechaza():
    epc = f"{7:024X}"
    cab, filas = abrir_filas(_xlsx([("A", GTIN, epc), ("B", GTIN, epc)]))
    datos, errores = validar(cab, filas, CAMPOS)
    assert datos == [] and errores
    assert errores[0].columna == "epc" and "duplicado" in errores[0].motivo


def test_falta_columna_requerida():
    cab, filas = abrir_filas(_xlsx([("A", f"{1:024X}")], cabeceras=("codigo", "epc")))
    datos, errores = validar(cab, filas, CAMPOS)
    assert errores and errores[0].columna == "gtin" and "falta" in errores[0].motivo


def test_gtin_digito_de_control_malo():
    cab, filas = abrir_filas(_xlsx([("A", "4006381333930", "")]))
    datos, errores = validar(cab, filas, CAMPOS)
    assert errores and "digito de control" in errores[0].motivo
