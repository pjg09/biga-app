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

Movidas a **`docs/statistics.md`**: `GET /admin/stats` (foto del día) y `/admin/stats/*`
(series históricas, alertas accionables y ranking de estudiantes en riesgo).

---

## PAE — inscritos (`/admin/pae/enrollments`)

Sección propia en Gestión: quiénes están admitidos al programa este año, con salón, fecha de
ingreso y última ración reclamada. **Solo ADMIN**, igual que `POST /pae/enrollments`: el
operador del PAE *opera* el programa —toma el listado del día y entrega— pero no decide quién
entra (ver `docs/pae.md`).

| Endpoint | Qué hace |
|---|---|
| `GET /admin/pae/enrollments?include_inactive=` | Listado + contadores (activos, de baja, nunca reclamaron) |
| `POST /admin/pae/enrollments` | Inscribe a un estudiante existente **o reactiva** su inscripción |
| `DELETE /admin/pae/enrollments/{student_id}` | Baja lógica de la inscripción |
| `POST /admin/pae/enrollments/{student_id}/reactivate` | Alta de una inscripción dada de baja |

### Por qué no reutiliza `POST /pae/enrollments`

El del módulo PAE responde **409 ante cualquier inscripción existente del año**, incluida una
dada de baja. Es la semántica correcta para un alta puntual e inservible para una consola,
donde reinscribir a alguien que salió del programa es una operación normal. El de admin
distingue: si la inscripción existe y está activa → `409`; si existe dada de baja → la
**reactiva**.

### La fila nunca se recrea ni se borra — regla crítica

Reinscribir **no** emite una firma nueva: se enciende `is_active` sobre la fila existente.
`enrolled_at` y `enrollment_hash` son la capa 1 de la cadena de integridad del PAE y las
entregas encadenan su hash con ellos (capa 2), así que:

- recrear la inscripción borraría la fecha real de ingreso al programa e invalidaría la
  auditoría de todo lo que ese estudiante ya reclamó;
- borrarla haría lo mismo.

`is_active` es el único campo fuera del hash, y por eso es el único que estas pantallas tocan —
la misma excepción que ya usaba el switch «Inscrito en el PAE» de la ficha del estudiante.

Otras dos guardas: un estudiante **dado de baja** no puede inscribirse (`409`, se pide
reactivarlo primero en Estudiantes), y la columna «Nunca» en última ración marca al inscrito
que no ha reclamado ni una vez — el caso que hay que revisar uno por uno.

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

## Horarios

Movidos a **`docs/schedule.md`**: calendario semanal proporcional al tiempo, `period_order`
derivado, los dos `EXCLUDE` (salón y docente) y la asignación docente-salón de `user_groups`.

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
