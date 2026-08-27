# plantillas

ZPL versionados. Cada plantilla se identifica por `codigo` + `version`
(`UNIQUE(codigo, version)` en la tabla `plantilla`).

Se prefieren campos de texto nativos (`^A0N` / `^FD`) sobre imágenes `^GFA`, para
poder sustituir valores por tokens desde el Excel (§1).

El central guarda, por cada etiqueta, los **datos resueltos** y la **versión de
plantilla** usada, de modo que siempre se puede reconstruir lo impreso sin tener que
renderizar en el central (§7).
