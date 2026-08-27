# central

Servicio único, dueño de la verdad. API HTTP (FastAPI) + PostgreSQL.

Responsabilidades:
- Recibir pedidos (`POST /v1/pedidos`), **validar el Excel entero** antes de nada
  (§14) y expandirlos a N trabajos en una cola única.
- Servir la reclamación atómica de bloques (`FOR UPDATE SKIP LOCKED`, §5).
- Controlar sesiones y `max_puestos`.
- Publicar cambios por cursor (`GET /v1/eventos?desde=`) para la Raspberry y paneles.
- Barrer trabajos `reclamado` caducados (5 min) y devolverlos a la cola.

Nunca abre conexiones hacia los puestos.

Pendiente (se rellena en Fase 0): `app/` (FastAPI), migraciones Alembic,
`requirements.txt`, y `tests/` con la validación de Excel y la idempotencia por
`clave_idem`.
