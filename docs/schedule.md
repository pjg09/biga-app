# Horarios — referencia funcional

> Extraído de `docs/admin.md`. Cubre `class_periods` (los bloques del horario de cada salón) y
> `user_groups` (qué docente está asignado a qué salón), que son cosas distintas y confundirlas
> fue el problema del diseño anterior.
>
> El esquema de la tabla y sus constraints están en `docs/database-schema.md`; la vista de
> calendario del front, en `docs/frontend.md`.

## Horarios — calendario semanal y docentes por salón

La consola está partida en dos pestañas porque responden preguntas distintas, y confundirlas era
el problema del diseño anterior:

- **Calendario semanal** — el horario del salón: qué materia y qué docente en cada día y hora.
- **Docentes por salón** — `user_groups`. **Esta es la que decide qué clases ve un docente en
  «Mis clases de hoy»**: Asistencia une `ClassPeriod → UserGroup` por salón. Un docente que
  aparezca en el calendario pero no aquí **no podrá tomar asistencia**.

### Materia y docente por bloque (migración `c5b9e2f47a13`)

`class_periods` tiene `subject_id` y `user_id`, ambos **nullable**: un horario a medio armar debe
poder guardarse. Antes la materia vivía duplicada en `class_periods.name` (texto libre que ya
divergía del catálogo) y el docente solo estaba a nivel de salón entero.

`name` sigue existiendo pero como **etiqueta del bloque** ("Primera hora", "Descanso"); la materia
sale del catálogo. El calendario muestra `subject_name` y cae a `name` cuando no hay materia, para
no dejar en blanco los bloques anteriores a la migración. En el formulario la etiqueta es
**opcional**: si se deja vacía se guarda el nombre de la materia (y "Clase" si tampoco hay materia),
porque la columna es NOT NULL pero obligar a inventar un nombre por bloque es fricción pura.

El cambio es **aditivo**: no toca `user_groups` ni el join de Asistencia, así que ese módulo no
cambió de comportamiento. Que el docente vea solo sus bloques en vez del salón entero es una
decisión pendiente, no algo que esta migración haya hecho.

### El docente del bloque es quien toma lista — regla crítica

`class_periods.user_id` es **NOT NULL** (migración `d6c1f8a390b4`) y Asistencia filtra por él, no
por `user_groups`. Antes, un docente asignado a un salón veía **todas** las horas de ese salón como
suyas: con 3 docentes en Once A, los 3 veían las 6 clases del día.

Las cuatro consultas de `attendance_repository` que unían `ClassPeriod → UserGroup` ahora filtran
`ClassPeriod.user_id == user_id`, incluida `teacher_owns_class_period`, que es la **autorización**
al registrar asistencia: un docente ya no puede tomar lista en un bloque ajeno (`404`).

> **Ojo con el año académico.** `class_periods` no tiene `academic_year`; lo aportaba el join a
> `user_groups`. Al quitarlo hay que unir `Group` y filtrar `Group.academic_year`, o un bloque de un
> salón de 2025 reaparecería en 2026. Las cuatro consultas lo hacen.

Por qué la columna es obligatoria: si un bloque no tuviera docente, nadie tomaría lista ahí — y si
fuese primera hora, **la notificación de inasistencia al acudiente nunca se enviaría**. La regla
"todo bloque tiene docente" es lo que hace segura la otra mitad del cambio. Tres guardas la
sostienen:

- `POST`/`PUT` de bloques exigen `user_id` → `422` sin él.
- No se puede asignar un docente **desactivado** a un bloque → `409`.
- **No se puede desactivar a un docente que dicta bloques** → `409` con el conteo, pidiendo
  reasignarlos primero en el calendario.

Al fijar un docente en un bloque se crea, si falta, su fila en `user_groups`. Sin ella vería la
clase en «Mis clases de hoy» (que ahora filtra por bloque) pero no a sus estudiantes en «Mis
estudiantes» (que sigue filtrando por salón).

### No hay creación masiva de horario (eliminado)

Existió un `POST /admin/class-periods/bulk` («Crear jornada») que armaba N bloques × M días en
una petición, con **un docente para toda la semana**. Se eliminó, y la razón de fondo es que el
concepto no existía en ninguna parte: no hay tabla `jornadas`, ningún bloque recuerda haberse
creado con otros, y ningún profesor dicta las 30 horas semanales de un salón.

La constraint del docente (`b7e4f1c8a209`) lo dejó además inservible en la práctica: como el
modal asignaba el mismo docente a toda la jornada y ese docente no puede estar en dos salones a
la vez, **a partir del segundo salón se omitía todo** — medido: `{created: 0, skipped: 30,
skipped_teacher: 30}`.

El horario se carga ahora **bloque a bloque** desde el calendario: clic en un hueco → modal con
la hora ya puesta → materia y docente. Decisión explícita, con su coste asumido: son ~30
formularios por salón (unos 600 en un colegio de 20 salones), así que la carga inicial la hace
quien implanta, no el colegio.

> Si algún día vuelve a hacer falta abaratarla, el eje correcto es **duplicar un día** (copiar el
> lunes al resto de la semana), no duplicar el salón: dos salones a la misma hora nunca pueden
> compartir docente, pero dos días del mismo salón sí — por eso el bulk anterior chocaba de
> frente con el invariante y una copia por día no lo haría.

### Duración libre y `period_order` derivado (migración `f2d5a81c9e37`) — regla crítica

Un bloque se define por **hora de inicio y hora de fin**, y nada más. No hay tamaño de bloque
base, ni `span`, ni orden que elegir: `period_order` lo recalcula el service (`_renumber_day`) como
la posición del bloque dentro de su día ordenando por `start_time`, después de **cualquier** alta,
edición o borrado.

Por qué `period_order` sigue existiendo si nadie lo elige: Asistencia dispara la notificación de
inasistencia al acudiente cuando `period_order == 1`. Al derivarlo, "primera hora" pasa a ser
literalmente la primera clase del día, que es lo que ese job siempre quiso decir.

> **Renumerar en dos fases.** `UNIQUE(group_id, period_order, day_of_week)` no es DEFERRABLE y el
> ORM emite un UPDATE por fila, así que permutar órdenes directamente (2→1, 1→2) choca a mitad de
> camino. `_renumber_day` desplaza primero todo a 1000+ y después reparte 1..N.

> **El borrado también renumera.** Sin eso, borrar la clase de las 7:00 deja el día empezando en el
> orden 2: nadie sería primera hora y la notificación al acudiente no se enviaría en ese día nunca
> más. Es el fallo más silencioso de todo el módulo.

### Un docente no puede estar en dos salones a la vez (migración `b7e4f1c8a209`)

Segunda constraint, **distinta** de la del salón: `EXCLUDE USING gist (user_id, day_of_week,
timerange(start_time, end_time))`. Aquella protege el aula (dos clases no comparten hora y
salón); esta protege a la persona.

Faltaba, y no era teórico: el seed de estadísticas repartía docentes por índice sin mirar
ocupación y dejó **120 pares de bloques solapados**. El síntoma salió en «Mis clases de hoy»
del docente — Carlos Docente con cuatro primeras horas simultáneas (Décimo A, Décimo B, Once A,
Once B), las cuatro con lista pendiente. Asistencia filtra por `class_periods.user_id`, así que
se las mostraba todas; y en primera hora eso son cuatro tandas de notificación a acudientes de
salones donde ese docente no estuvo.

- `POST`/`PUT` → **409** con mensaje que nombra el choque: «Carlos Docente ya dicta
  «Matemáticas» en Once A de 07:50 a 08:40 ese día».
- El chequeo del **salón corre primero**, así que cuando hay ambos conflictos el mensaje es el
  del salón. Es el orden correcto: el aula ocupada es el problema más cercano.

> Un colegio con 4 salones necesita **al menos 4 docentes por franja**. La BD demo tenía 4
> usuarios activos en total, y por eso era imposible cubrir el horario sin duplicar a alguien:
> `seed_stats_demo.py` ahora lleva un registro de ocupación (precargado con lo que ya hay en la
> BD) y **crea los docentes que falten** en vez de reutilizar al mismo.

El no-solapamiento pasó de los rangos de `period_order` al **reloj**: `EXCLUDE USING gist` sobre
`timerange(start_time, end_time)`. El invariante viejo protegía lo que no importaba — la BD de
desarrollo tenía un bloque `period_order = 2, span = 2` de 07:00–08:50 conviviendo con el orden 1
de 07:00–07:50: no chocaban en órdenes y se pisaban una hora entera. El service duplica la
comprobación (`find_overlapping_period`) solo para dar un `409` legible («Ese horario se cruza con
«Matemáticas», de 07:50 a 09:30») en vez de dejar que reviente la constraint. Detalle del tipo
`timerange` y de por qué la migración aborta ante solapes previos en `database-schema.md`.

### `PUT` / `DELETE /admin/class-periods/{cp_id}`

El `PUT` no cambia `group_id` — mover un bloque de salón es recolocarlo — pero **sí acepta
`day_of_week`**: pasar una clase del martes al jueves es una edición legítima, y sin orden elegible
ya no hay `UNIQUE` que esquivar. Al cambiar de día se renumeran **los dos** días, el de origen y el
de destino.

> Al mover de día, el orden provisional del bloque se pide **antes** de tocar `cp.day_of_week`: ese
> `SELECT` dispara el autoflush de SQLAlchemy y, con el día ya cambiado y el orden viejo todavía
> puesto, la escritura intermedia viola la UNIQUE del día destino. Costó un `500` en pruebas.

El `DELETE` es **borrado real, no baja lógica**: un bloque es configuración, no histórico. Pero
`409` si ya tiene asistencia tomada — `attendance_records.class_period_id` es FK y esos registros
sí son histórico.

### `day_of_week` llega a 7, no a 5

El modelo declaraba `CHECK BETWEEN 1 AND 5` mientras la BD real tenía `1 AND 7`, y existen bloques
en sábado creados por API que el front nunca mostró. Se alineó el modelo a la BD (`c5b9e2f47a13`)
en vez de estrechar el CHECK y tener que borrar esas filas. El calendario pinta Lun–Vie siempre y
añade Sáb/Dom **solo si esos días tienen bloques**, para no mostrar dos columnas vacías en el 99%
de los colegios.


### `POST /admin/class-periods` / `GET /admin/class-periods?group_id=`
`ClassPeriodCreate(group_id, name, start_time, end_time, day_of_week, user_id, subject_id=None)`.
`day_of_week` 1–7. Valida `start_time < end_time` (`422`) y que el rango no se cruce con otro
bloque de ese salón y día (`409`). **No lleva `period_order` ni `span`**: el orden lo deriva el
service y la duración son las dos horas.

### `POST /admin/teacher-assignments` / `GET /admin/teacher-assignments`
`UserGroupCreate(user_id, group_id, academic_year, subject_id=None)` — asigna un docente a un
salón para un año, opcionalmente con la materia que dicta ahí (`subject_id`, FK al catálogo
`subjects` de arriba, `NULL` si se omite; `404` si el `subject_id` no existe en la
institución). Esta tabla (`user_groups`) es la que usa `StudentService.list_students` para
acotar "Mis estudiantes" de `TEACHER`/`PAE_OPERATOR` (ver `docs/students.md`), y la que
determina qué salones ve un docente en Horario/Asistencia — **no** el horario de clases en sí
(`class_periods`), que es una tabla distinta.

`subject_id` alimenta el filtro "materia" del módulo de Aula del docente: sin valor, ese
docente simplemente no tiene materia asociada a ese salón y el filtro de materia lo ignora
(no rompe nada, solo queda sin dato). La respuesta (`UserGroupResponse`) trae también
`subject_name` resuelto (join a `subjects`) para no forzar un segundo fetch en el front.

Antes de la migración `d7e1a4c8f5b3` la materia era texto libre directo en `user_groups`
(sin catálogo) — se migró justamente porque dos docentes del mismo salón podían dictar la
misma materia escrita distinto ("Matemáticas" vs "Mate") y el filtro los trataba como
valores diferentes.

---
