# Módulo Admin — Referencia funcional

Consola de gestión institucional: estadísticas, personal, académico (grados/salones),
horarios y solicitudes comerciales de la landing. Todo bajo el prefijo `/admin`, todo
gateado con `require_admin` salvo donde se indique lo contrario. El alta de estudiante con
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
bcrypt directo — ver pitfall de `passlib` en `CLAUDE.md`). Sin chequeo de unicidad de
`document_number`, solo de `email` (`409` si ya existe).

### `GET /admin/users`
Lista completa de la institución, ordenada por rol y nombre.

---

## Académico: grados y salones

### `POST /admin/grades` / `GET /admin/grades`
`GradeCreate(name, level)`, `level` entre 1 y 11. Un grado duplicado por `level` en la
misma institución → `409`.

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
`UserGroupCreate(user_id, group_id, academic_year)` — asigna un docente a un salón para un
año. Esta tabla (`user_groups`) es la que usa `StudentService.list_students` para acotar
"Mis estudiantes" de `TEACHER`/`PAE_OPERATOR` (ver `docs/students.md`), y la que determina
qué salones ve un docente en Horario/Asistencia — **no** el horario de clases en sí
(`class_periods`), que es una tabla distinta.

---

## Solicitudes comerciales (`demo_leads`)

### `GET /admin/leads`
```
GET /admin/leads?status=PENDING&limit=50&offset=0
```

Lee las solicitudes de demo que llegan del formulario público de la landing (`POST /leads`,
sin autenticación). **Caso especial de aislamiento**: `demo_leads` es la única tabla del
sistema sin `institution_id` — un visitante que pide una demo no pertenece a ninguna
institución todavía, así que no hay tenant que filtrar en el `WHERE`.

El aislamiento lo da `require_leads_reader` (no un filtro de query): exige `ADMIN` **y**
estar en la lista blanca `LEADS_ADMIN_EMAILS` (env var). Con esa lista vacía, **cualquier
ADMIN de cualquier institución ve todos los leads de todos los demás** — solo sostenible
mientras haya una única institución real en la BD. Hay que llenar `LEADS_ADMIN_EMAILS` antes
de dar de alta a una segunda institución, o reemplazar el mecanismo por un rol de
superusuario real.

El estado de envío del aviso interno (a `LEADS_NOTIFY_EMAIL`) vive en columnas
`notification_*` propias de `demo_leads`, no en `notifications_log` (esa tabla exige
`institution_id`/`student_id`/`guardian_id` `NOT NULL`, y un lead no tiene ninguno de los
tres). El endpoint público de creación (`POST /leads`) tiene rate limit por IP en Redis; si
Redis cae, deja pasar la petición en vez de perder el lead.

---

## Roles

| Acción | Endpoint | Quién |
|---|---|---|
| Estadísticas | `GET /admin/stats` | `ADMIN` |
| Usuarios (crear/listar) | `POST`/`GET /admin/users` | `ADMIN` |
| Grados, salones (crear/listar) | `POST`/`GET /admin/grades`, `/admin/groups` | `ADMIN` |
| Matrícula standalone | `POST /admin/student-groups` | `ADMIN` |
| Alta completa de estudiante | `POST /admin/students` | `ADMIN` (ver `docs/students.md`) |
| Horarios (crear/listar) | `POST`/`GET /admin/class-periods` | `ADMIN` |
| Asignación docente-grupo | `POST`/`GET /admin/teacher-assignments` | `ADMIN` |
| Solicitudes de demo | `GET /admin/leads` | `ADMIN` + `LEADS_ADMIN_EMAILS` |

---

## Frontend

`AdminDashboard.jsx` — nav lateral con 6 secciones:

| Nav | Vista | Contenido |
|---|---|---|
| Resumen | `OverviewView` | `GET /admin/stats` en stat cards |
| Estudiantes | `StudentsView` | Ver `docs/students.md` |
| Personal | `StaffView` | Alta y listado de usuarios |
| Académico | `AcademicView` | Crear grado, crear grupo, matricular estudiante en grupo (standalone) |
| Horarios | `ScheduleView` | Bloques de horario (`class_periods`) + asignar docente a grupo |
| Solicitudes | `LeadsView` | Bandeja de leads de la landing, filtrable por `status` |

Servicio: `web/src/services/admin.js` (`adminService`).

---

## Probarlo

```bash
docker compose up -d
docker compose exec api alembic upgrade head
docker compose exec -T postgres psql -U biga -d biga < scripts/seed_dev_users.sql
```

Credenciales del admin demo en `docs/databaseDev.md`.
