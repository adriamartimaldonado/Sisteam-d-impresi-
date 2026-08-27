# -*- coding: utf-8 -*-
"""Semilla minima para poder probar el central a mano.

Crea (si no existen) una sede por defecto y una plantilla demo, y genera una API
key de rol `origen` que se imprime UNA sola vez (solo se guarda su hash).

Uso:
    python -m central.app.seed
"""

from __future__ import annotations

from sqlalchemy import select

from .config import cargar_config
from .db import FabricaSesion
from .modelos import ClienteApi, Plantilla, Sede
from .seguridad import generar_clave

# Campos de la plantilla demo (spec que valida el Excel).
CAMPOS_DEMO = [
    {"nombre": "codigo", "requerido": True, "tipo": "texto"},
    {"nombre": "gtin", "requerido": True, "tipo": "gtin"},
    {"nombre": "epc", "requerido": False, "tipo": "epc", "unico": True},
    {"nombre": "talla", "requerido": False, "tipo": "texto"},
]


def main() -> None:
    cfg = cargar_config()
    db = FabricaSesion()
    try:
        sede = db.scalar(select(Sede).where(Sede.codigo == cfg.sede_defecto))
        if sede is None:
            sede = Sede(codigo=cfg.sede_defecto, nombre=f"Sede {cfg.sede_defecto}")
            db.add(sede)
            db.flush()
            print(f"[+] Sede creada: {sede.codigo}")
        else:
            print(f"[=] Sede ya existia: {sede.codigo}")

        if db.scalar(select(Plantilla).where(Plantilla.codigo == "demo")) is None:
            db.add(Plantilla(codigo="demo", version=1,
                             contenido="^XA^FO50,50^A0N,40,40^FD{codigo}^FS^XZ",
                             campos=CAMPOS_DEMO))
            print("[+] Plantilla 'demo' v1 creada")
        else:
            print("[=] Plantilla 'demo' ya existia")

        plana, hash_ = generar_clave()
        db.add(ClienteApi(sede_id=sede.id, nombre="origen-seed", rol="origen",
                          clave_hash=hash_, activo=True))
        db.commit()
        print("\n[+] API key de ORIGEN (guardala, no se vuelve a mostrar):")
        print(f"    {plana}\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
