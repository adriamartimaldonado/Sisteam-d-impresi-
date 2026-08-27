# puesto

Un PC por impresora. Servicio que arranca con la máquina — en Windows tiene que ser
un **servicio real**, no "ejecutar al iniciar sesión" (si alguien cierra sesión, el
puesto desaparecería en silencio).

Responsabilidades:
- Abrir sesión sobre un pedido (si hay plaza según `max_puestos`) y descargar el
  **paquete** una sola vez.
- Calibrar e imprimir etiquetas de prueba; marcar la sesión `preparada` tras la
  validación humana.
- Reclamar bloques y enviarlos a la impresora **etiqueta a etiqueta con
  confirmación** (motor reutilizado del Controlador: `printer_link`,
  `print_controller`, `zpl_scale`).
- Mantener su SQLite local: `cola`, `impreso` (memoria anti-duplicado, purgar a los
  30 días, **no** antes), `salida`.
- Informar resultados en lote (`POST /v1/sesiones/{id}/resultados`), que hace de
  latido.

Pregunta al central; nunca escucha en ningún puerto.
