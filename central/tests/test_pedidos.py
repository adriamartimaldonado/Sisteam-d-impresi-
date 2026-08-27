# -*- coding: utf-8 -*-
"""Tests de `POST /v1/pedidos` (Fase 0). Necesitan PostgreSQL (se saltan si no hay).

Verificacion de la fase (§16):
- un pedido de 5 filas deja 5 trabajos;
- repetir la misma `clave_idem` no crea mas;
- un Excel con celda que pierde el cero se rechaza entero indicando fila y motivo.
"""

from io import BytesIO

from openpyxl import Workbook

GTIN = "4006381333931"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(filas, cabeceras=("codigo", "gtin", "epc")) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(list(cabeceras))
    for f in filas:
        ws.append(list(f))
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


def _post(client, key, contenido, clave_idem="k1", **extra):
    data = {"plantilla_codigo": "demo", "clave_idem": clave_idem, **extra}
    files = {"excel": ("pedido.xlsx", contenido, XLSX)}
    return client.post("/v1/pedidos", data=data, files=files,
                       headers={"X-API-Key": key})


def test_cinco_filas_cinco_trabajos(client, origen_key):
    xlsx = _xlsx([(f"{i:03d}", GTIN, f"{i:024X}") for i in range(1, 6)])
    r = _post(client, origen_key, xlsx, clave_idem="p5")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["n_trabajos"] == 5
    assert j["idempotente"] is False


def test_idempotencia_no_duplica(client, origen_key):
    xlsx = _xlsx([("001", GTIN, f"{1:024X}")])
    r1 = _post(client, origen_key, xlsx, clave_idem="dup")
    r2 = _post(client, origen_key, xlsx, clave_idem="dup")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["n_trabajos"] == 1
    assert r2.json()["idempotente"] is True
    assert r2.json()["n_trabajos"] == 1
    assert r1.json()["pedido_id"] == r2.json()["pedido_id"]


def test_excel_malo_se_rechaza_entero(client, origen_key):
    xlsx = _xlsx([
        ("001", GTIN, f"{1:024X}"),
        (2, GTIN, f"{2:024X}"),          # codigo numerico: pierde el cero
    ])
    r = _post(client, origen_key, xlsx, clave_idem="malo")
    assert r.status_code == 422, r.text
    detalle = r.json()["detail"]
    assert detalle["rechazado"] is True
    assert detalle["total_errores"] >= 1
    assert detalle["errores"][0]["fila"] == 3


def test_sin_api_key_es_401(client):
    files = {"excel": ("p.xlsx", _xlsx([("001", GTIN, "")]), XLSX)}
    r = client.post("/v1/pedidos",
                    data={"plantilla_codigo": "demo", "clave_idem": "x"}, files=files)
    assert r.status_code == 401


def test_rol_incorrecto_es_403(client, origen_key, db):
    from sqlalchemy import select
    from central.app.modelos import ClienteApi, Sede
    from central.app.seguridad import generar_clave
    sede = db.scalar(select(Sede).where(Sede.codigo == "test"))  # creada por origen_key
    plana, h = generar_clave()
    db.add(ClienteApi(sede_id=sede.id, nombre="lector", rol="lectura",
                      clave_hash=h, activo=True))
    db.commit()
    r = _post(client, plana, _xlsx([("001", GTIN, "")]), clave_idem="rol")
    assert r.status_code == 403
