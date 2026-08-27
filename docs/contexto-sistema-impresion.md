# Sistema de impresión de etiquetas — documento de contexto

**Estado:** diseño. No hay código escrito todavía.
**Fecha:** 27 de agosto de 2026.
**Propósito de este documento:** dar contexto completo del proyecto a una persona o a un
modelo de IA que no ha participado en las conversaciones previas. Es autocontenido: no
hace falta leer nada más para entender qué se quiere construir, qué se ha decidido, por
qué, y qué queda abierto.

---

## 1. Qué se quiere construir

Un sistema para producir tiradas de etiquetas ZPL en Zebra, repartiendo el trabajo entre
varias impresoras que están **todas en la misma nave, en la misma red local**. No es un
sistema multi-sede. La escalabilidad a otras sedes es un requisito de futuro, no de hoy.

El flujo, en palabras del responsable del proyecto:

> Yo lanzo un pedido, combinación de un ZPL, un Excel y unas configuraciones. Va a un
> ordenador central, que se comunica con la Raspberry y le transmite todo. El central
> reparte a cada ordenador adjunto a una impresora un pedido, que mediante otro
> subprograma se imprime. Todo esto debe seguir informando a la Raspberry.

### Entorno y restricciones que condicionan todo

- El código acaba corriendo en producción, atendido por personal no necesariamente
  técnico, y los fallos ocurren en el peor momento posible. La fiabilidad manda sobre la
  elegancia y sobre las funcionalidades.
- Las impresoras son Zebra (hay al menos una **ZT411R**, versión RFID). Se les habla por
  socket TCP al **puerto 9100**.
- Las etiquetas pueden llevar **codificación RFID (EPC)**. Una etiqueta duplicada no es un
  problema estético: son dos tags con el mismo EPC y stock corrupto.
- Las plantillas se diseñan con **ZebraDesigner** y se quieren con campos de texto nativos
  (`^A0N` / `^FD`) en lugar de imágenes `^GFA`, para poder sustituir valores por tokens.
- Existe una **Raspberry Pi** con una base de datos SQL de pedidos teóricos y reales, que
  hoy escribe y lee de forma continua.
- El **subprograma de impresión ya existe** y funciona. Recibe un fichero `.prn`, un Excel
  de referencia y la información necesaria para la impresora. **No hay que reescribirlo.**

---

## 2. La pieza del proceso que más condiciona el diseño: el calibrado

Esto no es un detalle de implementación, es una fase del proceso con una persona dentro,
y determina la forma del sistema entero.

Antes de imprimir una tirada, el ordenador del puesto tiene que:

1. Comunicarse con la impresora y **calibrarla**.
2. Imprimir **etiquetas de prueba** con un ZPL concreto.
3. Comprobar que **sale centrado** y correcto.
4. Solo cuando todo eso es correcto, empieza la tirada real.

Consecuencias de diseño, y son grandes:

- **La unidad de trabajo de un puesto no es una etiqueta suelta, es una sesión de
  impresión** que empieza con esa preparación. No se puede repartir etiqueta a etiqueta a
  ciegas entre puestos que no están preparados.
- **Hay un humano en el bucle**, y su validación es un estado del sistema, no un paso
  informal. Si no se modela, ese estado acaba viviendo en la cabeza del operario.
- Las etiquetas de prueba **consumen material**, y con RFID consumen tags. El sistema
  debe contarlas aparte y no confundirlas con producción.

---

## 3. Decisiones tomadas

| # | Decisión | Motivo | Estado |
|---|---|---|---|
| D1 | **Una sola base de datos, en el ordenador central** (opción B). La Raspberry pasa a ser un cliente más | Tener dos sistemas que creen saber el estado de un pedido garantiza que algún día divergirán y nadie sabrá cuál tiene razón. Además saca los datos de negocio de una tarjeta SD | Cerrada |
| D2 | **PostgreSQL** como motor | Soporta reclamación atómica con `FOR UPDATE SKIP LOCKED`, que es la pieza clave del reparto. No hay nada más óptimo para este caso (ver §9) | Cerrada |
| D3 | El reparto entre impresoras es **grado de paralelismo, no enrutado**: el pedido lleva un número «usa hasta N puestos», no una asignación fija de etiquetas a máquinas | Confirmado por el responsable: las impresoras son intercambiables y se reparte solo para acabar antes, no porque cada una lleve un material distinto | Cerrada |
| D4 | Los puestos **reclaman** trabajo; el central no se lo asigna | Una impresora atascada deja de pedir y las demás absorben su parte sola; una impresora que se suma a mitad de tirada empieza a ayudar de inmediato; un puesto que se apaga no deja etiquetas huérfanas | Cerrada |
| D5 | Los puestos **preguntan al central**; el central nunca abre conexiones hacia los puestos | Se puede reiniciar, mover o reinstalar un puesto sin tocar nada en el central, y no se depende de la IP que le haya tocado hoy | Cerrada |
| D6 | La memoria de «esto ya lo he impreso» vive **en el puesto**, no en el central | El puesto es el único que estuvo delante de la impresora. El central solo sabe si le llegó un aviso, no si salió el papel | Cerrada |
| D7 | Autenticación por **API key** desde el primer día, y columna de sede en las tablas desde el primer día | Requisito explícito de poder reutilizar el sistema en otras sedes en el futuro sin rehacerlo | Cerrada |
| D8 | El subprograma existente del puesto **no se reescribe**: sigue recibiendo `.prn` + datos + configuración | Ya funciona. El sistema nuevo se construye alrededor de él, no encima | Cerrada |
| D9 | **Todo el código en un solo repositorio de GitHub**; los puestos siguen releases con tag y solo se actualizan cuando no tienen sesión activa | Es la respuesta a «cómo actualizo N puestos sin ir uno por uno», y el modelo de sesiones ya da la ventana segura para hacerlo sin interrumpir una tirada (ver §15) | Cerrada |

---

## 4. Arquitectura

```
        TÚ (web interna o carpeta vigilada)
        pedido = ZPL/plantilla + Excel + configuraciones + "usa hasta N puestos"
                 │  POST /v1/pedidos   (API key de origen)
                 ▼
   ┌─────────────────────────────────────────────┐
   │  ORDENADOR CENTRAL                          │
   │  · API HTTP        · PostgreSQL (LA verdad) │
   │  · valida el Excel entero antes de nada     │
   │  · expande a N trabajos (uno por etiqueta)  │
   │  · publica en una cola única                │
   │  · panel web: cola, puestos, reimprimir     │
   └─────────────────────────────────────────────┘
        ▲ los puestos preguntan          ▲ lee/escribe lo suyo
        │ (nunca al revés)               │
   ┌────┴───────┬───────────┐      ┌─────┴──────────────┐
   │ PUESTO 1   │ PUESTO 2  │ ...  │ RASPBERRY PI       │
   │ + Zebra    │ + Zebra   │      │ cliente de la API  │
   └────────────┴───────────┘      └────────────────────┘
```

- **Central**: un solo servicio, una sola base. Es dueño de pedidos, trabajos, plantillas,
  sesiones y estado de la flota.
- **Puesto**: un ordenador por impresora. Servicio que arranca con la máquina (en Windows
  tiene que ser un **servicio real**, no «ejecutar al iniciar sesión»: el día que alguien
  cierre sesión, ese puesto desaparece del sistema en silencio). Tiene una base local
  pequeña (SQLite) con su cola y su registro de lo ya impreso.
- **Raspberry**: deja de ser un cerebro y pasa a ser un cliente de la API como cualquier
  otro. «Informar a la raspy» deja de ser un problema que resolver: hay una sola verdad.

---

## 5. El reparto: reclamar en vez de asignar

Es la idea central del sistema y conviene entenderla bien porque la alternativa intuitiva
es la que falla.

**Lo que no se hace (asignación):** llegan 1000 etiquetas, el operario pide dos puestos, el
central parte 500 / 500 y cada puesto imprime lo suyo. Funciona hasta el primer imprevisto:
si un puesto se queda sin ribbon, sus 500 se quedan quietas mientras el otro termina y
espera; si se suma un tercer puesto a mitad, no ayuda porque el reparto ya está hecho; si
un PC se apaga, hay que rescatar su mitad a mano.

**Lo que se hace (reclamación):** el central mete los 1000 trabajos en una cola única y no
decide nada más. Cada puesto preparado pide «dame los siguientes 10» y los coge en
exclusiva. La impresora rápida hace más, la lenta menos, la atascada deja de pedir y las
otras absorben su parte sin que nadie intervenga.

**Y el número de puestos que pide el operario se respeta igual**, pero como un límite en
vez de como un troceado: `pedido.max_puestos = 2` significa que como mucho dos sesiones de
impresión pueden estar abiertas sobre ese pedido a la vez. Se conserva el control (por
ejemplo, dejar una impresora libre para urgencias) y se pierde el problema.

La reclamación tiene que ser atómica o dos puestos imprimen lo mismo. En PostgreSQL es una
consulta:

```sql
UPDATE trabajo SET estado = 'reclamado', puesto_id = :puesto, reclamado_en = now()
WHERE id IN (
  SELECT t.id FROM trabajo t
  WHERE t.pedido_id = :pedido AND t.estado = 'pendiente'
  ORDER BY t.orden
  LIMIT :bloque
  FOR UPDATE SKIP LOCKED    -- los que otro puesto ya está cogiendo se saltan
)
RETURNING id, orden, datos;
```

`SKIP LOCKED` es lo que hace que varios puestos pidiendo a la vez se lleven bloques
distintos sin esperarse entre ellos y sin escribir ni un semáforo.

**Tamaño de bloque:** empezar en 10. Bloques grandes reducen las llamadas pero aumentan lo
que hay que rescatar si un puesto muere a media tirada; bloques pequeños hacen lo contrario.

---

## 6. Ciclo de vida

### 6.1 Sesión de impresión (puesto + pedido)

Es la fase que introduce el calibrado. Ningún trabajo real se reclama fuera de una sesión
preparada.

```
abierta ──► calibrando ──► preparada ──► imprimiendo ──► cerrada
                │                             │
                └──► abortada ◄───────────────┘
```

| Estado | Significado |
|---|---|
| `abierta` | El puesto ha cogido plaza en el pedido (si quedaba, según `max_puestos`) y ha descargado el paquete |
| `calibrando` | Se está calibrando e imprimiendo etiquetas de prueba. Las de prueba se cuentan aparte |
| `preparada` | Una persona ha validado que la prueba sale centrada y correcta. **Aquí y no antes** se puede empezar a reclamar producción |
| `imprimiendo` | Reclamando y enviando bloques |
| `cerrada` | El pedido se acabó o el operario paró |
| `abortada` | Se canceló durante la preparación, o el puesto lleva demasiado tiempo sin dar señales |

### 6.2 Trabajo (una etiqueta)

```
pendiente ──► reclamado ──► enviado ──► confirmado
     ▲             │            │
     │             │            └────► fallido ──┐
     └─────────────┴───────────────────────────◄─┘
       vuelve a la cola: por caducidad del bloqueo o por reintento
```

- Un trabajo `reclamado` lleva la hora en que se reclamó. Si pasan **5 minutos sin
  noticias** (puesto apagado, sesión cerrada, Windows actualizándose), **se libera solo** y
  vuelve a la cola, donde lo coge cualquier otro puesto con sesión preparada sobre ese
  pedido. Sin esto, apagar un PC a mitad de tirada deja etiquetas colgadas para siempre.
- `enviado` significa «salieron los bytes por el socket». `confirmado` significa «la
  impresora dice que lo hizo». **No son lo mismo y no deben mezclarse** (ver §8).

### 6.3 La etiqueta duplicada

Ese mismo rescate por caducidad es lo que puede sacar una etiqueta dos veces: si el puesto
sí imprimió y lo que se perdió fue el aviso, el trabajo vuelve a la cola y sale otra vez.

**La protección:** cada puesto guarda en su SQLite local la tabla `impreso(trabajo_id, …)`
y, antes de enviar nada a la impresora, comprueba si ese id ya está. Si está, no imprime y
responde «confirmado» otra vez.

Tiene que estar en el puesto porque es el único que estuvo delante de la impresora.
**Corolario operativo:** esa tabla es dato, no caché. Si se purga para ahorrar espacio o se
restaura un PC desde una imagen vieja, se pierde la protección contra duplicados sin que
nadie se entere. Purgar a los 30 días, no antes.

---

## 7. Qué recibe el puesto

Requisito expreso: *«se les debe pasar la info completa»*, porque el subprograma del puesto
es quien ejecuta la impresión y necesita todo para funcionar de forma autónoma.

Se resuelve en dos piezas, y esto es lo que concilia «info completa» con «reclamar por
bloques»:

1. **El paquete, una sola vez al abrir la sesión** (`GET /v1/sesiones/{id}/paquete`):
   el `.prn` / plantilla ZPL, el ZPL de calibración y prueba, el Excel de referencia
   completo, y todas las configuraciones del pedido. A partir de aquí el puesto tiene todo
   lo que necesita y no depende del central para saber *cómo* imprimir.
2. **Los bloques de trabajo, según va pudiendo**: solo dice *qué* filas imprimir y en qué
   orden. Son unos pocos bytes por etiqueta.

**Compromiso a tener presente:** si el ZPL final lo compone el puesto a partir del Excel, el
central no conoce los bytes exactos que salieron por la impresora. Se compensa guardando en
el central los **datos resueltos de cada etiqueta** y la **versión de la plantilla** usada,
de modo que siempre se puede reconstruir. Es suficiente y no obliga a tocar el subprograma
existente. La alternativa —renderizar en el central— daría trazabilidad exacta pero
significaría reescribir lo que ya funciona.

---

## 8. Lo que todavía no se sabe: si la etiqueta salió

Si se manda ZPL al 9100 y el socket acepta los bytes, lo único que se sabe es que la
impresora tenía buffer libre. Ni papel, ni ribbon, ni cabezal abierto, ni si un tag RFID
falló la codificación.

Zebra permite consultar estado con comandos de host y variables SGD, pero **la sintaxis
exacta y lo que devuelve el modelo concreto con su firmware hay que verificarlo contra el
manual antes de construir nada encima**. No debe darse por sabido de memoria.

Mientras no esté resuelto, el panel debe decir «enviado» donde solo sabe que se envió. Un
sistema que no puede saber algo tiene que decir que no lo sabe.

---

## 9. Sobre el motor: por qué PostgreSQL y no otra cosa

La pregunta era si hay algo más óptimo. Para este caso, no.

- Una cola implementada como tabla de PostgreSQL con `SKIP LOCKED` aguanta con holgura
  varios órdenes de magnitud más de lo que este sistema va a mover. El cuello de botella
  serán siempre las impresoras.
- Añadir Redis, RabbitMQ o Kafka introduce **un segundo almacén que hay que mantener
  consistente con la base de datos**, y esa inconsistencia es precisamente el origen
  habitual de los duplicados que aquí no son admisibles. Se paga complejidad para comprar
  un problema.
- MariaDB no soporta `SKIP LOCKED` (MySQL 8 sí). SQLite no lo soporta y además no está
  pensada para acceso por red: **nunca compartir un fichero SQLite por SMB o carpeta
  compartida**, corrompe el fichero. En el puesto sí es la elección correcta, porque ahí es
  local y de un solo proceso.

---

## 10. Seguridad y preparación para otras sedes

- **API key por cliente** (cada puesto, cada origen de pedidos, la Raspberry), en cabecera
  `X-API-Key`, guardada **hasheada** en la base, con rol asociado: `origen` (crear
  pedidos), `puesto` (reclamar e informar), `lectura` (paneles, integraciones).
- Un puesto solo puede operar sobre **sus** sesiones y sus trabajos. Que la clave sea válida
  no significa que pueda tocar cualquier cosa.
- **Columna `sede` en las tablas desde el primer día**, aunque hoy solo haya un valor.
  Añadirla luego, con datos e integraciones vivas, es una migración desagradable; tenerla
  desde el principio no cuesta nada. **Lo que no hay que hacer ahora es construir la
  multi-sede**: solo dejar de hacerla imposible.
- HTTP dentro de la LAN es aceptable hoy; el día que algo salga fuera, TLS obligatorio.
- **El agujero real está en la propia impresora**: el puerto 9100 de una Zebra no tiene
  autenticación de ningún tipo. Cualquiera en esa red puede imprimir y, en muchos modelos,
  reconfigurarla. Lo correcto es VLAN o subred donde solo lleguen los puestos, con IP fija o
  reserva DHCP. Si no es posible, hay que dejarlo escrito como riesgo aceptado.

---

## 11. Modelo de datos

```sql
-- CENTRAL (PostgreSQL)
sede        (id, codigo, nombre)
cliente_api (id, sede_id, nombre, rol, clave_hash, activo, creada_en)
puesto      (id, sede_id, nombre, capacidades text[], ultimo_latido, version)
impresora   (id, puesto_id, modelo, ip, puerto, dpi, rfid)
plantilla   (id, codigo, version, contenido, campos jsonb)   -- UNIQUE(codigo, version)
pedido      (id, sede_id, clave_idem, plantilla_id, config jsonb,
             max_puestos, prioridad, estado, creado_por, creado_en)  -- UNIQUE(clave_idem)
sesion      (id, pedido_id, puesto_id, estado, abierta_en, preparada_en,
             cerrada_en, pruebas_impresas, validada_por)
trabajo     (id uuid PK, pedido_id, orden int, datos jsonb, estado,
             sesion_id, puesto_id, reclamado_en, intentos, ultimo_error,
             creado_en, actualizado_en)
evento      (id bigserial PK, tipo, pedido_id, trabajo_id, datos jsonb, creado_en)

-- índices imprescindibles
CREATE INDEX ON trabajo (pedido_id, estado, orden);   -- la reclamación
CREATE INDEX ON trabajo (estado, reclamado_en);       -- el barrido de caducados
CREATE INDEX ON sesion  (pedido_id, estado);          -- el control de max_puestos
```

```sql
-- PUESTO (SQLite local, un solo proceso)
cola    (trabajo_id PK, sesion_id, orden, datos, estado, intentos, recibido_en)
impreso (trabajo_id PK, impreso_en, resultado)   -- purgar a los 30 días, NO antes
salida  (id PK, trabajo_id, estado, error, ts)   -- resultados aún no confirmados arriba
```

---

## 12. API

Todo HTTP contra el central, con `X-API-Key`. Los puestos no escuchan en ningún puerto.

| Método y ruta | Quién | Qué hace |
|---|---|---|
| `POST /v1/pedidos` | origen | Plantilla + Excel + config + `max_puestos`. Valida el Excel **entero**, expande a N trabajos y encola. Idempotente por `clave_idem` |
| `GET /v1/pedidos` | puesto, panel | Pedidos con trabajo pendiente y plazas libres |
| `POST /v1/sesiones` | puesto | Coge plaza en un pedido. Falla si ya hay `max_puestos` sesiones activas |
| `GET /v1/sesiones/{id}/paquete` | puesto | Devuelve el paquete completo: `.prn`, ZPL de prueba, Excel de referencia, configuración |
| `POST /v1/sesiones/{id}/prueba` | puesto | Registra que se han impreso etiquetas de prueba y cuántas |
| `POST /v1/sesiones/{id}/preparada` | puesto | El operario valida la prueba. Sin esto no se sirve producción |
| `POST /v1/sesiones/{id}/reclamar` | puesto | «Dame los siguientes N». Devuelve un bloque, o vacío y un `espera_ms` |
| `POST /v1/sesiones/{id}/resultados` | puesto | Qué salió y qué falló, en lote. Reenviar lo mismo no cambia nada. Hace también de latido |
| `POST /v1/sesiones/{id}/cerrar` | puesto | Fin de tirada o parada del operario. Libera la plaza |
| `GET /v1/eventos?desde={id}` | Raspberry, integraciones | Cambios posteriores a un cursor |

Ejemplo de reclamación:

```jsonc
// POST /v1/sesiones/41/reclamar
{ "maximo": 10, "impresora": { "estado": "lista", "papel": "ok" } }

// respuesta
{ "trabajos": [ { "id": "8f2c…c41a", "orden": 137, "datos": { "codigo": "BB-1234-M", "epc": "3034F4…" } } ],
  "espera_ms": 2000 }   // si viene vacío, cuánto esperar antes de volver a pedir
```

El `espera_ms` lo decide el central: el día que ocho puestos machaquen la base cada 200 ms,
se arregla en un sitio en vez de en ocho.

---

## 13. Consumo de cambios: no releer, preguntar qué ha cambiado

Requisito original: la Raspberry «debe estar apuntando todo y leyendo todo en todo
momento». Eso **no** se hace releyendo las tablas en bucle: funciona con dos puestos y se
cae al crecer.

```sql
-- mal: "dame el estado de todo", cada segundo
SELECT * FROM trabajo;

-- bien: "dame lo que ha cambiado desde que miré"
SELECT * FROM evento WHERE id > :cursor ORDER BY id LIMIT 500;
```

Consulta por índice en vez de escaneo completo, sobrevive a que un consumidor esté apagado
un rato (al volver sigue por donde iba), y da el orden real de los cambios, que un campo
`actualizado_en` no garantiza si dos escrituras caen en el mismo milisegundo.

---

## 14. Validación del Excel

Donde se cuelan la mitad de los errores de producción.

- Se valida **el fichero entero antes de imprimir nada**. Si algo falla, se rechaza el
  pedido completo con la lista de filas y motivos. Nunca imprimir medio Excel: media tirada
  mala es peor que ninguna, porque hay que separar a mano lo bueno de lo malo.
- **Cuidado con lo que Excel hace a los datos:** un código `0012345` se convierte en `12345`
  en cuanto la celda es numérica, y un EAN largo se va a notación científica. Con códigos de
  barras y EPC, eso es una tirada entera a la basura. Leer siempre las celdas como texto y
  validar longitud y formato de cada campo, no solo su presencia.
- Comprobar también duplicados dentro del propio fichero, especialmente en EPC.

---

## 15. Despliegue y actualización: todo por GitHub

Requisito expreso: todo el código vive en GitHub y el despliegue se hace desde ahí. Bien
planteado, es exactamente la respuesta a «cómo actualizo N puestos sin ir uno por uno».
Mal planteado, es la forma más rápida de romper todas las impresoras a la vez.

### Un solo repositorio

```
etiquetas/
  central/            API, migraciones, panel
  puesto/             servicio del puesto
  comun/              contrato compartido: esquema de la API, estados, versiones
  plantillas/         ZPL versionados
  .github/workflows/  CI
```

Monorepo, no dos repositorios, porque central y puesto **comparten contrato**: si cambia el
protocolo, cambia en un commit y no hay forma de que las dos mitades queden desfasadas
entre sí sin que se vea.

### Los puestos siguen etiquetas de versión, no ramas

Un puesto que hace `git pull` de `main` es una bomba: cualquier commit llega a todas las
impresoras a la vez y no hay forma de volver atrás con calma. Cada puesto sigue una
**release con tag** (`v1.4.2`), y el central publica en `GET /v1/version_aprobada` cuál es
la que debe correr. El puesto compara y, si difiere, se actualiza.

### Y solo se actualiza entre tiradas

Esta es la parte elegante, y sale gratis porque ya está en la arquitectura: **un puesto solo
puede actualizarse cuando no tiene sesión activa**. Nunca a media tirada.

```
sesión cerrada → comprobar versión aprobada → git fetch --tags
               → git checkout v1.4.2 → reiniciar servicio → disponible otra vez
```

Una actualización no interrumpe jamás una impresión en curso, y el modelo de sesiones que
ya existe te da la ventana segura sin inventar ningún mecanismo nuevo.

### Rollback ensayado

Volver atrás es `git checkout` del tag anterior y reiniciar el servicio. **Ensáyalo una vez
cuando no haga falta**: un rollback que se prueba por primera vez con la producción parada
no es un rollback, es una esperanza.

### Credenciales y configuración

- **Deploy key de solo lectura por puesto**, o token de granularidad fina. Nunca la cuenta
  personal de alguien: el día que esa persona rote la contraseña, se paran las impresoras.
- **Ningún secreto en el repositorio.** La API key del puesto, su nombre y la IP de su
  impresora van en un `.env` local que no se versiona. En el repo va un `.env.ejemplo`.
- **Las migraciones de base de datos van versionadas en el repo** (Alembic o equivalente) y
  las aplica el central al desplegar, no una persona con `psql`. Solo hacia adelante.

### GitHub Actions

Lo mínimo que aporta valor desde el primer día: tests en cada push, y en particular **el test
de la fase 1 —tres clientes reclamando a la vez sobre un pedido de 1000— ejecutándose en
cada commit**. Ese test es la red de seguridad contra la etiqueta duplicada, y una red que
solo se despliega cuando alguien se acuerda no es una red.

---

## 16. Plan por fases

Cada fase termina en algo verificable sin depender de que haya producción real. Si una fase
no se puede verificar, está mal cortada.

**Fase 0 — Base y esqueleto de API.** Tablas, API keys, `POST /v1/pedidos` con validación
del Excel. Sin interfaz y sin impresoras.
*Verificación:* un pedido de 5 filas deja 5 trabajos pendientes; repetir la misma llamada
con la misma `clave_idem` no crea 5 más; un Excel con un código repetido y una celda que
pierde el cero inicial se rechaza entero indicando fila y motivo.

**Fase 1 — Sesiones y reclamación, con puestos simulados.** Dos o tres procesos que abren
sesión, se declaran preparados y reclaman bloques sin impresora. **Es la fase que decide si
el sistema es correcto.**
*Verificación:* pedido de 1000 con `max_puestos = 2`; arrancar tres clientes y comprobar que
solo dos consiguen sesión. Al terminar, cada trabajo aparece reclamado por exactamente un
puesto y la suma da 1000 sin repetidos. Matar un cliente a mitad: sus trabajos vuelven a la
cola en 5 minutos y los coge el otro.

**Fase 2 — Puesto real: calibrado, impresión y memoria de lo impreso.** Integración con el
subprograma existente, tabla `impreso`, servicio de Windows. Antes de tocar una Zebra,
impresora simulada con `nc -l 9100`.
*Verificación:* 20 etiquetas, cortar la red del puesto a mitad, restaurar y contar lo que
salió: tienen que ser 20, no 21. Reiniciar el puesto a media tirada y repetir el recuento.
Comprobar que no se sirve ni una etiqueta de producción antes de marcar la sesión como
preparada.

**Fase 3 — Panel.** Cola, pedidos, sesiones abiertas, puestos vivos, reimprimir.
*Verificación:* que un operario reimprima una etiqueta sin llamar a nadie y sin
instrucciones escritas.

**Fase 4 — Confirmación real de impresora y operación.** Estado de la Zebra verificado
contra el manual; aviso de puesto sin latido; actualización de los N puestos sin ir uno por
uno.
*Verificación:* abrir el cabezal, mandar una etiqueta y comprobar que acaba `fallido` con
motivo, no confirmada. Esto solo se puede comprobar con la impresora delante.

---

## 17. Lo que deliberadamente NO se hace

Ni broker de mensajes, ni contenedores orquestados, ni microservicios, ni colas por
impresora, ni multi-sede real, ni prioridades complicadas. Un servicio central, una base de
datos, un programa de puesto. **La solución aburrida es la preferible: el código más fiable
es el que no existe.** Todo eso se puede añadir cuando un problema real lo pida; nada de eso
se puede quitar una vez que la producción depende de ello.

Lo que sí conviene dejar cerrado desde el principio, porque cambiarlo después duele:

- Una sola base de datos que es la verdad.
- Los trabajos se reclaman, no se asignan.
- El número de puestos es un límite, no un troceado.
- La memoria de lo impreso vive en cada puesto.
- Los puestos preguntan; el central nunca llama.
- API key y columna de sede desde el día uno.

---

## 18. Preguntas abiertas

1. **¿Qué contiene exactamente «las configuraciones» de un pedido?** Copias por fila,
   oscurecimiento, velocidad, si se codifica RFID, forzar una impresora concreta. Cada una
   necesita un sitio explícito con valor por defecto, o acabará viviendo solo en la cabeza
   de quien lanzó el pedido.
2. **¿Cuántas etiquetas al día en pico y cuántos puestos?** No cambia la arquitectura, pero
   sí los tamaños de bloque y los tiempos de espera.
3. **¿Qué comandos de estado admite exactamente la ZT411R con su firmware?** Pendiente de
   verificar contra el manual. Decide si «confirmado» significa «salió» o solo «lo mandé».
4. **¿Qué pasa con las etiquetas de prueba de calibrado en tiradas RFID?** Consumen tags.
   Hay que decidir si se contabilizan como merma y si se pueden imprimir sin codificar.
5. **¿Quién puede reimprimir y con qué límite?** Con EPC de por medio, reimprimir no es
   inocuo.
6. **¿Qué pasa si el operario abandona una sesión preparada sin cerrarla?** Hay un tiempo de
   caducidad, pero hay que decidir cuánto y qué se le muestra al siguiente que llegue.
