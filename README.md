# etiquetas — sistema de impresión distribuida de etiquetas ZPL/RFID

Monorepo del sistema que reparte tiradas de etiquetas ZPL entre varias impresoras
Zebra de una misma nave, con un **ordenador central** dueño de la verdad y unos
**puestos** (un PC por impresora) que **reclaman** el trabajo en vez de recibirlo
asignado.

> El diseño completo, las decisiones tomadas y su porqué están en
> [`docs/contexto-sistema-impresion.md`](docs/contexto-sistema-impresion.md).
> Este README es el mapa del repo; ese documento es la razón de ser.

## Idea central (léela antes de tocar nada)

- **Una sola base de datos** en el central (PostgreSQL). La Raspberry pasa a ser un
  cliente más de la API, no un segundo cerebro.
- Los puestos **reclaman** bloques de trabajo (`FOR UPDATE SKIP LOCKED`); no se les
  asigna. La impresora rápida hace más, la atascada deja de pedir, y una que se
  suma a mitad ayuda sola. `max_puestos` es un **límite** de sesiones simultáneas,
  no un troceado.
- Ningún trabajo real se sirve fuera de una **sesión preparada**: primero un humano
  calibra y valida la etiqueta de prueba. La validación es un **estado**, no un paso
  informal.
- **La memoria de "esto ya lo imprimí" vive en el puesto** (SQLite `impreso`), porque
  es el único que estuvo delante de la impresora. Es la protección contra el EPC
  duplicado.
- Los puestos **preguntan** al central; el central **nunca** abre conexiones hacia
  los puestos.

## Estructura

```
etiquetas/
  central/            API FastAPI + PostgreSQL + migraciones (Alembic) + panel
    app/              código de la API
    tests/            pytest (incluye el test de reclamación concurrente, fase 1)
  puesto/             servicio del puesto: sesión, calibrado, envío, SQLite local
  comun/              contrato compartido: estados, roles, versión de API
    contrato/         estados.py (fuente de verdad de estados y transiciones)
  plantillas/         ZPL versionados
  .github/workflows/  CI (tests en cada push)
```

Monorepo (no dos repos) porque central y puesto **comparten contrato**: si cambia
el protocolo, cambia en un commit y no hay forma de que las mitades queden
desfasadas (decisión D9).

## Reutilización del controlador existente

El motor de impresión que ya funciona (envío etiqueta-a-etiqueta con confirmación
`~HS`, calibración, reescalado por dpi) se **reaprovecha** dentro de `puesto/`; no se
reescribe (decisión D8). Procede del proyecto *Controlador impresoras*
(`printer_link`, `print_controller`, `zpl_scale`, `prn_parser`).

## Plan por fases (cada una termina en algo verificable)

- **Fase 0** — Base y esqueleto de API: tablas, API keys, `POST /v1/pedidos` con
  validación del Excel entera. Sin interfaz ni impresoras.
- **Fase 1** — Sesiones y reclamación con puestos simulados. *Decide si el sistema
  es correcto* (test: 3 clientes, `max_puestos=2`, pedido de 1000 sin duplicados).
- **Fase 2** — Puesto real: calibrado, impresión y memoria de lo impreso.
- **Fase 3** — Panel: cola, pedidos, sesiones, puestos vivos, reimprimir.
- **Fase 4** — Confirmación real de impresora (estado Zebra verificado) y operación.

## Puesta en marcha (local)

Requisitos: Python 3.11+, PostgreSQL 14+.

```bash
cp .env.ejemplo .env      # y rellena los valores
# (instrucciones de instalación y arranque se añaden con la Fase 0)
```

## Reglas que no se tocan sin discutirlo

Una sola BD que es la verdad · los trabajos se reclaman, no se asignan · el número
de puestos es un límite, no un troceado · la memoria de lo impreso vive en el puesto
· los puestos preguntan, el central nunca llama · API key y columna `sede` desde el
día uno.
