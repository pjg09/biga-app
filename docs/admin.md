# Módulo Admin — Referencia funcional

Consola de gestión institucional: estadísticas, personal, académico (grados/salones) y
horarios. Todo bajo el prefijo `/admin`, todo gateado con `require_admin` salvo donde se
indique lo contrario. Es la consola que usa el colegio — no expone datos comerciales de
BIGA. Las solicitudes de demo de la landing (`POST /leads`, tabla `demo_leads`) se siguen
capturando y notificando por correo (`LEADS_NOTIFY_EMAIL`, ver `docs/database-schema.md`),
pero el equipo de BIGA las gestiona por fuera de este dashboard, no hay visor acá. El alta
de estudiante con
matrícula y acudientes vive documentada en `docs/students.md` (aunque su endpoint,
`POST /admin/students`, cuelga de este mismo router) — acá solo la matrícula standalone y
el resto de "Académico".

---

## Qué resuelve

Es el backoffice del sistema: todo lo que un `ADMIN` necesita para dar de alta la
estructura de la institución (grados, salones, horarios, personal) y consultar cómo le está
yendo (estadísticas). No confundir con `docs/students.md`, que documenta el ciclo de vida
del estudiante — un dato que ADMIN también gestiona, pero con entidad propia.

---

## Estadísticas

### `GET /admin/stats`
Snapshot del día y semana actuales (`AdminService.get_stats`, `AdminRepository`). Todos los
conteos filtran por `institution_id`.

```json
{
  "date": "2026-08-14",
  "students_active": 4, "staff_total": 3, "teachers": 1, "pae_operators": 1,
  "pae_enrolled": 4, "pae_delivered_today": 2, "pae_delivered_week": 2, "pae_claim_rate": 50.0,
  "attendance_present_today": 0, "attendance_absent_today": 0, "attendance_late_today": 0,
  "attendance_justified_today": 0, "attendance_rate_today": 0.0,
  "departures_today": 0,
  "discipline_records": 0, "discipline_leve": 0, "discipline_moderada": 0, "discipline_grave": 0,
  "notifications_sent": 12, "notifications_failed": 0, "notifications_pending": 0
}
```

`pae_claim_rate` = % de inscritos que reclamaron **hoy** (no acumulado). `attendance_rate_today`
= (presentes + tardanzas) / total de registros de hoy — una tardanza cuenta como asistencia
para esta métrica, aunque dispare la notificación de inasistencia si no se marca a tiempo
(ver `docs/attendance.md`).

---

## Personal (usuarios)

### El admin nunca fija contraseñas — regla

Ni `AdminUserCreate` ni `AdminUserUpdate` aceptan `password`. Al crear, el service genera una
contraseña temporal (`generate_temp_password`, `secrets.token_urlsafe`) , guarda solo su bcrypt y
encola `notify_staff_welcome` para enviársela al interesado por correo. Para cambiarla existe el
flujo público `/auth/password-reset`, que exige acceso al buzón del titular.

El motivo es de seguridad, no de comodidad: si el admin pudiera fijar la contraseña de otra
persona, podría entrar como ella y actuar en su nombre — y en este dominio eso significa firmar
registros de convivencia o entregas del PAE atribuidos a un docente. **No reintroducir el campo.**

El job se encola con `argsrepr` para que la contraseña temporal no salga en los logs del worker,
igual que el OTP (`docs/architecture.md`). Viaja en claro por Redis, con la misma contrapartida:
en producción ese puerto no debe publicarse fuera de la red de Docker. Si el correo falla, el
alta **no** se revierte: el usuario ya existe y puede entrar por `/recuperar`.

### `POST /admin/users`
Crea un usuario (`TEACHER`/`PAE_OPERATOR`/`ADMIN`). La contraseña no viene en el payload (ver
arriba); se hashea con `hash_password` (bcrypt directo — ver pitfall de `passlib` en `CLAUDE.md`).
`document_number` es obligatorio y único por institución (`UNIQUE(institution_id, document_number)`,
migración `e2f9c6a1d4b7`, mismo patrón que `students.document_number`) — `409` si ya existe, igual
que `email` (única globalmente, no por institución, porque es el login).

### `GET /admin/users`
Lista completa de la institución, ordenada por rol y nombre. `photo_url` viene ya presignada.

### `GET /admin/users/{id}` / `PUT /admin/users/{id}`
Ficha de detalle y edición — mismo patrón que `GET`/`PUT /admin/students/{id}` (`docs/students.md`):
la consola de Personal tiene un botón "+ Agregar miembro del personal" que abre el alta en un
modal aparte, y cada fila abre una ficha de solo lectura con un botón "Editar" que reabre el
mismo modal precargado.

`AdminUserUpdate` tiene los mismos campos que `AdminUserCreate`. Duplicado de `email` o
`document_number` → `409` (excluyendo al propio usuario en ambos casos, para poder editar sin
cambiarlos).

**Un admin no puede quitarse a sí mismo el rol `ADMIN`** → `409`. Es el mismo autobloqueo que
cubre `DELETE /users/{id}`, pero por la puerta del `PUT`: `require_admin` rechazaría su siguiente
request y, si era el único administrador, la institución se queda sin acceso a la consola, solo
recuperable con un `UPDATE` manual en Postgres. La guarda es **estrecha a propósito**: solo frena
el cambio de rol sobre uno mismo. Editarse el nombre o el correo manteniendo `ADMIN` sigue
funcionando, y degradar o desactivar a **otro** administrador también — quien llama sigue siendo
admin, así que nunca se queda la institución sin ninguno.

### `DELETE /admin/users/{id}` — baja lógica (el botón «Eliminar»)

**No borra la fila.** Apaga `is_active`, nada más. Todo lo que ese usuario firmó — registros de
convivencia, tomas de asistencia, entregas del PAE — sigue apuntando a su `user_id` y el histórico
queda trazable. Borrar de verdad rompería esas referencias.

El acceso se revoca **de inmediato, no al expirar el JWT**: `get_current_user` comprueba
`is_active` en cada request (`app/core/dependencies.py`), así que un token todavía vigente deja de
servir en el siguiente request. `POST /auth/login` también lo comprueba (403).

Dos guardas, ambas `409`:
- **No puedes desactivarte a ti mismo.** Sería un autobloqueo inmediato.
- **No puedes dejar la institución sin ningún administrador activo.** Defensiva: hoy es
  inalcanzable, porque quien llama siempre es un admin activo distinto del objetivo. Se mantiene
  para que la invariante siga cubierta si algún día se añade una baja en lote o se relaja la
  primera guarda.

`GET /admin/users?include_inactive=true` los devuelve para poder reactivarlos, y
`POST /admin/users/{id}/reactivate` los vuelve a activar. En el front es el check «Ver inactivos»
de la lista de Personal: por defecto solo se ven los activos, y la ficha de un inactivo cambia el
botón «Editar» por «Reactivar».

### `DELETE /admin/students/{id}` — baja lógica del estudiante

Mismo principio. Basta con apagar `is_active` para que desaparezca de toda la operación:
listados, `GET /students/search`, rosters de asistencia y del PAE **ya filtran esa columna**
(`student_repository`, `attendance_repository`, `pae_repository`). No hay que tocar nada más.

Las inscripciones al PAE **no se tocan**, y es deliberado: sus consultas hacen join con `students`
y ya lo excluyen, así que apagarlas además sería redundante y tocaría una tabla firmada.

`GET /students?include_inactive=true` solo aplica a la rama del **ADMIN** de
`StudentService.list_students`; docente y operador PAE nunca ven estudiantes dados de baja en su
aula. Reactivación en `POST /admin/students/{id}/reactivate`.

### `POST /admin/users/{id}/photo`
Sube la foto del miembro del personal a object storage (multipart, `photo`), igual que
`POST /students/{id}/photo`. Dos diferencias con la del estudiante:

- La key va bajo `staff-photos/{institution_id}/{user_id}.{ext}`, separada de `photos/` — las
  fotos de estudiante alimentan la identificación del PAE y estas no.
- `users.photo_url` guarda la **key**, nunca la URL; se presigna al leer con `resolve_photo_url`.

Content-types aceptados (`ALLOWED_PHOTO_TYPES` en `app/core/photos.py`, compartido con estudiantes):
JPG, PNG y WEBP → `400` en cualquier otro. La extensión sale de ese mapa, nunca del nombre que
manda el cliente. Tope de tamaño `PHOTO_MAX_UPLOAD_MB` (5 por defecto) → `413`.

En el front la foto se sube en **una segunda petición** después del alta/edición, porque el
`POST`/`PUT` de usuario es JSON y esta es multipart. Si la foto falla, el usuario ya quedó
guardado y el toast lo dice explícitamente en vez de fingir éxito.

---

## Académico — sub-secciones «Salones» y «Materias»

La consola de Académico está partida en dos pestañas (`AcademicView` → `SalonesView` /
`MateriasView`). **Salones** es la gestión completa: un bloque por grado con sus salones como
tarjetas, crear salón desde el propio grado, y un panel por salón con su lista de matriculados
para meter y sacar estudiantes.

Se pintan **los 11 grados aunque estén vacíos** — el admin necesita ver dónde falta crear salón,
no solo lo que ya existe —, pero los vacíos van compactados (`.sal-grade--empty`): con 11 grados
y pocos salones, si no, la pantalla es una columna de tarjetas idénticas que entierran las que sí
tienen contenido.

### `PUT /admin/subjects/{subject_id}` — renombrar materia

Cambia solo el nombre. `subject_id` no se toca, así que las asignaciones docente-salón
(`user_groups.subject_id`) siguen apuntando a la misma fila y el filtro "Mis estudiantes por
materia" no se entera. `409` si ya existe otra materia con ese nombre en la institución
(chequeo previo sobre `UNIQUE(institution_id, name)`, excluyéndose a sí misma).

En el front, cada tarjeta del catálogo **es un botón** que abre el renombrado; el lápiz se revela
en hover/foco, y queda fijo en dispositivos sin hover (`@media (hover: none)`) porque ahí no
habría forma de descubrirlo.

### `PUT /admin/groups/{group_id}` — renombrar

Cambia **solo el nombre** (`GroupUpdate`). No toca grado ni año a propósito: cambiar de grado
movería de grado a todos sus matriculados, que es otra operación. Como el `group_id` no cambia,
matrículas, `class_periods` y asignaciones docentes siguen apuntando al mismo salón y nada más se
entera.

`409` si ya hay un salón con ese nombre en el mismo grado y año — chequeo previo en el service
sobre la constraint `UNIQUE(grade_id, name, academic_year)`, para dar mensaje claro. Renombrar un
salón a su propio nombre **no** da conflicto (se excluye a sí mismo).

> **Cuidado con `Field(min_length=1)` en nombres.** Los `field_validator` corren **después** de las
> restricciones del `Field`, así que `"   "` pasa el `min_length` y un `.strip()` posterior lo deja
> en cadena vacía. Por eso `GroupCreate`, `GroupUpdate` y `SubjectCreate` usan el helper
> `_strip_required` de `schemas/admin.py`, que recorta **y** rechaza el vacío. Replicarlo en
> cualquier campo de texto obligatorio nuevo.

### `POST /admin/groups/{group_id}/students` — meter (o mover)

`student_groups` es `UNIQUE(student_id, academic_year)`: un estudiante vive en **un solo salón por
año**. Por eso agregar y mover son la misma operación — se reutiliza la fila del año en curso en
vez de crear otra, que chocaría con la constraint. Mismo tratamiento que `update_student_full`,
para que las dos puertas dejen los datos igual.

`409` solo si ya estaba en **ese mismo** salón. El front avisa antes: el resultado de búsqueda
muestra «se moverá desde Once A» cuando el estudiante ya tiene salón, para que mover nunca sea
una sorpresa.

### `DELETE /admin/groups/{group_id}/students/{student_id}` — sacar

`is_active = False` sobre la matrícula; **no borra la fila**, que es el histórico de en qué salón
estuvo ese año. Exige que la matrícula sea **de ese salón** (`get_student_group_in_group`): así un
`DELETE` con el salón equivocado da `404` en vez de desmatricular a alguien de otro sitio.

### `GET /admin/groups`

Devuelve además `grade_level` y `student_count` (matrículas activas de estudiantes activos). El
conteo va como subquery correlacionada y no como `GROUP BY`: con `GROUP BY` un salón vacío se
perdería, y son justo los que hay que ver para llenarlos.

---

## Académico: grados y salones

### `GET /admin/grades` — catálogo de solo lectura

**No existe `POST /admin/grades`.** Los grados son un catálogo fijo de los 11 niveles de básica y
media (`STANDARD_GRADES` en `app/core/grades.py`): los colegios públicos de Medellín tienen
siempre los mismos, así que darlos de alta a mano solo abría la puerta a erratas y a grados
duplicados por nombre — `grades.name` no tiene constraint de unicidad, solo la tiene `level`.

Los siembra la migración `a7c3e9f2b581` en cada institución existente, y `scripts/seed_base.py`
en las nuevas. `grades` lleva `institution_id`, así que no es una tabla global: cada institución
tiene sus propias 11 filas.

La consola de Académico ya no muestra ningún formulario de "Crear grado"; el desplegable de Grado
del alta de salones se llena desde este `GET`. Si algún día hay que añadir preescolar o
transición, se cambia `STANDARD_GRADES` y se escribe una migración que lo aplique — no se reabre
el alta manual.

### `POST /admin/subjects` / `GET /admin/subjects` — catálogo de materias
`SubjectCreate(name)`. Materia duplicada por nombre en la misma institución → `409`. Sin
`PUT`/`DELETE`, igual que grados/grupos: alta simple, no editable desde la API. Alimenta el
selector de materia de "Asignar docente a grupo" (abajo) y el filtro "materia" del módulo de
Aula del docente (`docs/students.md`).

### `POST /admin/groups` / `GET /admin/groups`
`GroupCreate(grade_id, name, academic_year)`. El grado debe existir en la institución (`404`
si no); grupo duplicado por (grado, nombre, año) → `409`. La respuesta trae `grade_name`
resuelto (join a `grades`) para no forzar un segundo fetch en el front.

### `POST /admin/student-groups` — matrícula standalone
`StudentGroupCreate(student_id, group_id, academic_year)`. Matricula a un estudiante
**ya existente** en un grupo — a diferencia de `POST /admin/students` (`docs/students.md`),
que matricula como parte del alta. Valida que el estudiante y el grupo existan en la
institución, y que el estudiante no tenga ya una matrícula ese año (`409` — `UNIQUE
(student_id, academic_year)` en `student_groups`). Usado para matricular a un estudiante que
ya existía antes de que el alta atómica incluyera este paso, o para cambiarlo de año.

---

## Horarios — rejilla semanal y docentes por salón

La consola está partida en dos pestañas porque responden preguntas distintas, y confundirlas era
el problema del diseño anterior:

- **Rejilla semanal** — el horario del salón: qué materia y qué docente en cada día y hora.
- **Docentes por salón** — `user_groups`. **Esta es la que decide qué clases ve un docente en
  «Mis clases de hoy»**: Asistencia une `ClassPeriod → UserGroup` por salón. Un docente que
  aparezca en la rejilla pero no aquí **no podrá tomar asistencia**.

### Materia y docente por bloque (migración `c5b9e2f47a13`)

`class_periods` tiene `subject_id` y `user_id`, ambos **nullable**: un horario a medio armar debe
poder guardarse. Antes la materia vivía duplicada en `class_periods.name` (texto libre que ya
divergía del catálogo) y el docente solo estaba a nivel de salón entero.

`name` sigue existiendo pero como **etiqueta del bloque** ("Primera hora", "Descanso"); la materia
sale del catálogo. La rejilla muestra `subject_name` y cae a `name` cuando no hay materia, para no
dejar en blanco los bloques anteriores a la migración.

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

- `POST`/`PUT`/`bulk` de bloques exigen `user_id` → `422` sin él.
- No se puede asignar un docente **desactivado** a un bloque → `409`.
- **No se puede desactivar a un docente que dicta bloques** → `409` con el conteo, pidiendo
  reasignarlos primero en la rejilla.

Al fijar un docente en un bloque se crea, si falta, su fila en `user_groups`. Sin ella vería la
clase en «Mis clases de hoy» (que ahora filtra por bloque) pero no a sus estudiantes en «Mis
estudiantes» (que sigue filtrando por salón).

### `POST /admin/class-periods/bulk`

Crea la jornada completa de un salón (periodos × días) en **una** petición. Sin esto, un horario de
6 periodos × 5 días eran 30 envíos de formulario.

Los (orden, día) que ya existan se **omiten**, no fallan: así se puede relanzar para rellenar
huecos al añadir un día o una hora, sin tocar lo que ya estaba. Devuelve `{created, skipped}`.

Declarado **antes** que `/class-periods/{cp_id}` en el router: Starlette resuelve por orden de
registro y, si no, "bulk" entraría como `{cp_id}` y daría 422 al no castear a UUID.

### Clases de duración variable (`span`)

No todas las clases duran lo mismo. `class_periods.span` dice cuántos periodos **consecutivos**
ocupa un bloque: `1` = normal, `2` = clase doble. Un bloque con `period_order = 2` y `span = 2`
ocupa el 2 y el 3, así que el orden 3 de ese día queda tomado y no admite otro bloque.

> **La `UNIQUE(group_id, period_order, day_of_week)` no basta con spans.** Esa clase doble no
> impediría crear otra en el orden 3. Por eso la migración `e9a3b7c2d418` añade un `EXCLUDE
> USING gist` sobre `int4range(period_order, period_order + span)` — requiere la extensión
> `btree_gist`. El service duplica la comprobación (`find_overlapping_period`) solo para dar un
> `409` legible («choca con «Matemáticas», que ocupa los órdenes 2 a 3 ese día») en vez de dejar
> que reviente la constraint.

En la rejilla el bloque se pinta con `rowSpan`, ocupando visualmente sus dos filas, y las celdas
que cubre no se renderizan. Ojo al calcular las filas visibles: los órdenes que una clase doble
**cubre sin empezar en ellos** también cuentan, o la fila 3 desaparecería. Y `existing_period_slots`
(el que usa la creación masiva para omitir lo ya existente) expande cada bloque a todos los órdenes
que ocupa, no solo al de inicio.

### `PUT` / `DELETE /admin/class-periods/{cp_id}`

El `PUT` no cambia `group_id` ni `day_of_week`: mover un bloque de salón o de día es recolocarlo,
y chocaría con `UNIQUE(group_id, period_order, day_of_week)`. Cambiar el orden sí se permite, con
chequeo previo de esa constraint → `409`.

El `DELETE` es **borrado real, no baja lógica**: un bloque es configuración, no histórico. Pero
`409` si ya tiene asistencia tomada — `attendance_records.class_period_id` es FK y esos registros
sí son histórico.

### `day_of_week` llega a 7, no a 5

El modelo declaraba `CHECK BETWEEN 1 AND 5` mientras la BD real tenía `1 AND 7`, y existen bloques
en sábado creados por API que el front nunca mostró. Se alineó el modelo a la BD (`c5b9e2f47a13`)
en vez de estrechar el CHECK y tener que borrar esas filas. La rejilla pinta Lun–Vie siempre y
añade Sáb/Dom **solo si esos días tienen bloques**, para no mostrar dos columnas vacías en el 99%
de los colegios.


### `POST /admin/class-periods` / `GET /admin/class-periods?group_id=`
`ClassPeriodCreate(group_id, name, period_order, start_time, end_time, day_of_week)`.
`day_of_week` 1–5 (lunes a viernes, sin fin de semana). Valida `start_time < end_time` y que
no exista ya un bloque con el mismo `(group_id, period_order, day_of_week)` (`409`).

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

## Roles

| Acción | Endpoint | Quién |
|---|---|---|
| Estadísticas | `GET /admin/stats` | `ADMIN` |
| Usuarios (alta/listar/detalle/edición) | `POST`/`GET`/`PUT /admin/users[/{id}]` | `ADMIN` |
| Grados, salones, materias (crear/listar) | `POST`/`GET /admin/grades`, `/admin/groups`, `/admin/subjects` | `ADMIN` |
| Matrícula standalone | `POST /admin/student-groups` | `ADMIN` |
| Alta/detalle/edición de estudiante | `POST`/`GET`/`PUT /admin/students[/{id}]` | `ADMIN` (ver `docs/students.md`) |
| Horarios (crear/listar) | `POST`/`GET /admin/class-periods` | `ADMIN` |
| Asignación docente-grupo | `POST`/`GET /admin/teacher-assignments` | `ADMIN` |

---

## Frontend

`AdminDashboard.jsx` — nav lateral con 5 secciones:

| Nav | Vista | Contenido |
|---|---|---|
| Resumen | `OverviewView` | `GET /admin/stats` en stat cards |
| Estudiantes | `StudentsView` | Ver `docs/students.md` |
| Personal | `StaffView` | Alta y listado de usuarios |
| Académico | `AcademicView` | Crear grado, crear grupo, matricular estudiante en grupo (standalone) |
| Horarios | `ScheduleView` | Bloques de horario (`class_periods`) + asignar docente a grupo |

Servicio: `web/src/services/admin.js` (`adminService`).

---

## Probarlo

```bash
docker compose up -d
docker compose exec api alembic upgrade head
docker compose exec -T postgres psql -U biga -d biga < scripts/seed_dev_users.sql
```

Credenciales del admin demo en `docs/runbook.md` §5.
