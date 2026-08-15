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

### `POST /admin/users`
Crea un usuario (`TEACHER`/`PAE_OPERATOR`/`ADMIN`) con contraseña ya hasheada (`hash_password`,
bcrypt directo — ver pitfall de `passlib` en `CLAUDE.md`). `document_number` es obligatorio y
único por institución (`UNIQUE(institution_id, document_number)`, migración `e2f9c6a1d4b7`,
mismo patrón que `students.document_number`) — `409` si ya existe, igual que `email` (única
globalmente, no por institución, porque es el login).

### `GET /admin/users`
Lista completa de la institución, ordenada por rol y nombre.

### `GET /admin/users/{id}` / `PUT /admin/users/{id}`
Ficha de detalle y edición — mismo patrón que `GET`/`PUT /admin/students/{id}` (`docs/students.md`):
la consola de Personal tiene un botón "+ Agregar miembro del personal" que abre el alta en un
modal aparte, y cada fila abre una ficha de solo lectura con un botón "Editar" que reabre el
mismo modal precargado.

`AdminUserUpdate` tiene los mismos campos que `AdminUserCreate` **excepto** que `password` es
opcional: vacío u omitido no toca la contraseña actual; si viene, reemplaza el hash (mismo
mínimo de 8 caracteres). El formulario del front lo refleja con el placeholder "dejar en blanco
para no cambiarla" y sin `required` en modo edición. Duplicado de `email` o `document_number` →
`409` (excluyendo al propio usuario en ambos casos, para poder editar sin cambiarlos).

---

## Académico: grados y salones

### `POST /admin/grades` / `GET /admin/grades`
`GradeCreate(name, level)`, `level` entre 1 y 11. Un grado duplicado por `level` en la
misma institución → `409`.

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

Credenciales del admin demo en `docs/databaseDev.md`.
