# Módulo Asistencia y Salidas tempranas — Referencia funcional

> Cómo funcionan la toma de asistencia de primera hora, las tardanzas, la
> justificación por enlace y las salidas anticipadas, tal como están
> implementados. Modelo de datos en `docs/database-schema.md`.

---

## Qué resuelve

- **Asistencia de primera hora**: el docente toma lista en su primera clase del
  día. Los estudiantes que no llegan reciben (por su acudiente) un correo de
  inasistencia con un enlace para justificarla.
- **Tardanzas**: si el estudiante aparece dentro de una ventana de gracia, el
  docente lo marca como tardanza y **no** se envía el correo.
- **Salidas tempranas**: el docente registra que un estudiante se retira antes y
  el acudiente recibe un correo informativo inmediato.

Ambos módulos los opera personal de aula: `TEACHER` **y** `PAE_OPERATOR` (el
operador PAE es un docente con funciones extra del PAE). El acceso se controla con
`require_staff` (`app/core/dependencies.py`), que admite ambos roles. Los
endpoints de justificación son **públicos**.

---

## Estados de un registro de asistencia

`attendance_records.status` (enum `attendance_status`):

| Estado | Significado | Cómo se llega |
|--------|-------------|---------------|
| `PRESENT` | Presente | El docente lo marca al tomar lista |
| `ABSENT` | Ausente | El docente lo marca al tomar lista → se programa la notificación |
| `LATE` | Tardanza (llegó tarde, pero asistió) | El docente marca "Llegó" dentro de la ventana de gracia |
| `JUSTIFIED` | Inasistencia justificada | El acudiente envía la justificación por el enlace |

Solo `PRESENT` y `ABSENT` se aceptan **al tomar lista**. `LATE` y `JUSTIFIED` son
transiciones posteriores.

---

## Flujo de asistencia paso a paso

```
1. Docente abre Asistencia          GET  /attendance/first-class/today
   → el sistema resuelve su primera hora (period_order=1) de hoy + el listado del grupo

2. Marca presente/ausente y guarda  POST /attendance/first-class
   → por cada ABSENT encola notify_absence_first_hour con
     countdown = ATTENDANCE_GRACE_MINUTES (default 50 min)

3a. El estudiante llega tarde        POST /attendance/records/{id}/arrived
    → ABSENT pasa a LATE; cuando la tarea dispare verá LATE y no notifica

3b. Pasa la ventana y sigue ausente  (la tarea Celery dispara)
    → relee el estado: sigue ABSENT → crea token + envía correo al acudiente

4. El acudiente abre el enlace       GET  /attendance/justify/{token}
   y envía la excusa                 POST /attendance/justify/{token}
   → el registro pasa a JUSTIFIED
```

### Cómo se resuelve "la primera clase del día"

`AttendanceRepository.get_teacher_first_period` une
`user_groups` (docente↔grupo) → `class_periods` filtrando
`period_order = 1` y `day_of_week = hoy`, y toma la de menor `start_time`. Si es
fin de semana o el docente no tiene primera hora asignada, el endpoint responde
`has_class = false`.

### Por qué la notificación es diferida y idempotente

- Se encola con `countdown` (la ventana de gracia), no de inmediato. Cuando la
  tarea dispara, **relee** el `status`: si ya es `LATE`/`PRESENT`/`JUSTIFIED`, no
  hace nada.
- Idempotencia: hay **un token por registro** (`UNIQUE` en `attendance_tokens`).
  Si ya existe token, la tarea asume que ya se notificó y no reenvía.
- Si el estudiante no tiene acudiente primario, se registra un error en el log y
  no se notifica (no se puede escribir `notifications_log` sin `guardian_id`).

---

## Justificación por enlace de un solo uso

El correo de inasistencia contiene `FRONTEND_URL/justificar/{token}`:

- `attendance_tokens`: `token` (UUID no adivinable), `expires_at` (medianoche del
  día siguiente a la inasistencia), `used_at`.
- Los endpoints `GET/POST /attendance/justify/{token}` **no requieren JWT**: el
  token UUID es la autorización. Un token inválido, expirado o ya usado se rechaza
  aunque sea sintácticamente correcto.
- Al justificar: se crea `attendance_justifications`, se marca el token como usado
  y el registro pasa a `JUSTIFIED`.

---

## Salidas tempranas

```
Docente registra la salida   POST /departures   { student_id, departure_time, reason? }
  → crea early_departures
  → encola notify_early_departure (correo informativo, sin token)
Docente ve las salidas de hoy GET  /departures
```

---

## Endpoints

### Asistencia (rol docente / operador PAE — `require_staff`)

| Método y ruta | Descripción |
|---|---|
| `GET /attendance/first-class/today` | Primera hora del docente hoy + listado + si ya se tomó |
| `POST /attendance/first-class` | Toma de lista. Body `{ class_period_id, entries:[{student_id, status}] }` |
| `POST /attendance/records/{record_id}/arrived` | Marca `ABSENT` → `LATE` (llegó tarde) |
| `GET /attendance/schedule` | Horario semanal del docente (sus `class_periods`) |
| `GET /attendance/justifications` | Excusas enviadas por los acudientes para los registros de este docente |

`GET /attendance/first-class/today` (ejemplo):
```json
{ "has_class": true, "class_period_id": "…", "group_name": "A", "grade_name": "Once",
  "period_name": "Primera hora", "start_time": "07:00:00", "end_time": "07:50:00",
  "date": "2026-06-24", "already_taken": false,
  "students": [ { "student_id":"…", "document_number":"1010100001",
    "first_name":"Mariana", "last_name":"Gómez", "photo_url":null,
    "status": null, "record_id": null } ] }
```

`POST /attendance/first-class` — validaciones:
- status solo `PRESENT` o `ABSENT` → si no, `400`.
- la clase debe pertenecer al docente → `404`.
- debe ser `period_order = 1` → `400`.
- no se puede haber tomado ya hoy → `409`.
- las entradas deben cubrir **exactamente** al grupo → `400`.

`POST /attendance/records/{record_id}/arrived`: `404` si no existe ·
`409` si el registro no está `ABSENT` (idempotente si ya es `LATE`).

### Justificación (público, sin JWT)

| Método y ruta | Descripción |
|---|---|
| `GET /attendance/justify/{token}` | Info para mostrar en la página (validez, estudiante, fecha) |
| `POST /attendance/justify/{token}` | Body `{ reason }`. Registra la justificación → `JUSTIFIED` |

`GET` responde siempre `200` con `valid` y un `message` describiendo el estado
(válido, expirado, ya justificado, inválido). `POST`: `404` token inválido ·
`409` ya justificada · `410` expirado.

### Salidas tempranas (rol docente / operador PAE — `require_staff`)

| Método y ruta | Descripción |
|---|---|
| `POST /departures` | Body `{ student_id, departure_time, reason? }`. Crea y notifica |
| `GET /departures` | Salidas de hoy (incluye `student_name`) |

---

## Jobs y notificaciones

Las tareas Celery son síncronas pero la BD es async. `app/jobs/runner.py::run_db_job`
levanta un engine `NullPool` propio por tarea, hace commit/rollback y lo descarta.

| Tarea | Encolada por | Cuándo dispara |
|-------|--------------|----------------|
| `notify_absence_first_hour(record_id)` | `submit_attendance` por cada `ABSENT` | `countdown = ATTENDANCE_GRACE_MINUTES * 60` |
| `notify_early_departure(departure_id)` | `create_departure` | `countdown = 10s` (evita carrera con el commit del request) |

Cada tarea arma su notifier (`AttendanceNotifier` / `DepartureNotifier`) con la
sesión del runner y un `EmailAdapter` (`ResendEmailAdapter`). Un fallo de correo
se registra en `notifications_log` como `FAILED` y **no** relanza.

> Sin una API key real de Resend el correo no sale, pero el **enlace de
> justificación queda logueado** en el worker (`docker compose logs -f worker`)
> para poder probar el flujo completo.

`docker-compose.yml` ya levanta los servicios `worker` y `beat`.

---

## Frontend

Las vistas viven en `web/src/pages/TeacherDashboard.jsx` y se exportan para
reutilizarse también en `PAEDashboard.jsx` (el operador PAE es docente+):

- **Asistencia** — carga la primera clase, toggle Presente/Ausente por estudiante,
  guardar; si ya se tomó, muestra estados y botón "Llegó (tardanza)" en los ausentes.
- **Salidas tempranas** — busca estudiante (`GET /students/search`), hora y motivo,
  registra y notifica; lista las salidas del día.
- **Horario** — grilla semanal desde `GET /attendance/schedule`.
- **Mensajes** — excusas de los acudientes desde `GET /attendance/justifications`.
- **Convivencia** — registro de agendatorio con firma en canvas.

`web/src/pages/JustifyPage.jsx` — página **pública** en `/justificar/:token`
(sin login) donde el acudiente escribe la excusa.

Servicios: `web/src/services/attendance.js`, `web/src/services/departures.js`.

---

## Configuración

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ATTENDANCE_GRACE_MINUTES` | `50` | Minutos de gracia antes de notificar la inasistencia. Bajar a `1` en dev para probar sin esperar. |
| `FRONTEND_URL` | `http://localhost:5173` | Base de los enlaces de justificación que van en el correo. |

---

## Probarlo

```bash
docker compose up -d                      # incluye worker + beat
docker compose exec api alembic upgrade head
docker compose exec -T postgres psql -U biga -d biga < scripts/seed_dev_users.sql
```

Pon `ATTENDANCE_GRACE_MINUTES=1` en `.env` para no esperar 50 minutos. Login como
`teacher@iedemo.edu.co` / `password123` → **Asistencia** (grupo 11A, primera hora
sembrada lun–vie) → marca un ausente → guarda. ~1 minuto después el worker procesa
la notificación; toma el enlace `/justificar/{token}` de los logs del worker y
ábrelo para justificar.

---

*Referencia funcional — Asistencia y Salidas tempranas | BIGA*
