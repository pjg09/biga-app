# Módulo Asistencia y Salidas tempranas — Referencia funcional

> Cómo funcionan la toma de asistencia clase a clase, las tardanzas, la
> justificación por enlace y las salidas anticipadas, tal como están
> implementados. Modelo de datos en `docs/database-schema.md`.

---

## Qué resuelve

- **Asistencia clase a clase**: el docente toma lista en **cualquier** clase del
  día, no solo la primera hora. Todas se registran para historial. **Solo en la
  primera hora** (`period_order = 1`) los estudiantes ausentes disparan al acudiente
  un correo de inasistencia con un enlace para justificarla; las clases 2–N se
  registran sin correo.
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
1. Docente abre Asistencia          GET  /attendance/today
   → lista todas sus clases de hoy (con badge already_taken e is_first_hour)

2. Elige una clase                   GET  /attendance/classes/{class_period_id}
   → roster del grupo + estado de hoy

3. Marca presente/ausente y guarda   POST /attendance
   → SOLO si es primera hora (period_order=1): por cada ABSENT encola
     notify_absence_first_hour con countdown = ATTENDANCE_GRACE_MINUTES (default 50 min).
     Clases 2–N: se registran sin encolar nada.

4a. El estudiante llega tarde        POST /attendance/records/{id}/arrived
    → ABSENT pasa a LATE; cuando la tarea dispare verá LATE y no notifica

4b. Pasa la ventana y sigue ausente  (la tarea Celery dispara)
    → relee el estado: sigue ABSENT → crea token + envía correo al acudiente

5. El acudiente abre el enlace       GET  /attendance/justify/{token}
   y envía la excusa                 POST /attendance/justify/{token}
   → el registro pasa a JUSTIFIED
```

### Cómo se resuelven "las clases de hoy"

`AttendanceRepository.get_teacher_classes_for_day` filtra
**`class_periods.user_id == docente`** (el docente **del bloque**, no del salón),
`day_of_week = hoy` y `Group.academic_year` — ordenadas por `start_time`.

> **Cambió en la migración `d6c1f8a390b4`.** Antes unía `user_groups`
> (docente↔salón), así que un docente asignado a Once A veía **las seis horas**
> del día como suyas aunque solo dictara dos. Ahora `class_periods.user_id` es
> `NOT NULL` y las **cuatro** consultas de `attendance_repository` filtran por
> bloque, incluida `teacher_owns_class_period`, que es la autorización al
> registrar asistencia: tomar lista en un bloque ajeno da `404`.
>
> `class_periods` no tiene año propio, así que hay que unir `Group` y filtrar
> `Group.academic_year`; sin eso reaparecerían bloques de años anteriores.
>
> Que todo bloque tenga docente es lo que hace segura esta mitad: sin él, nadie
> tomaría lista ahí y en primera hora la notificación al acudiente no se
> enviaría nunca. Ver las guardas en `docs/schedule.md`.

**El fin de semana no está excluido.** La consulta filtra por el `isoweekday()`
de hoy (1..7) y no hay ningún punto de control por día en el backend: si un salón
tiene bloques en sábado, aparecen. Habilitado a propósito para el QA de los
product owners — ver el bloque `TEMPORAL` de `TODO.md`.

La UNIQUE `(student_id, class_period_id, date)` permite un registro por
estudiante por clase por día. **La notificación se encola solo cuando
`period_order == 1`.**

> **Zona horaria:** los contenedores fijan `TZ=America/Bogota` (y `postgres` además por flag). Sin eso
> corren en UTC y `date.today()` adelanta un día entre las 19:00 y medianoche hora Colombia, escribiendo
> la fecha equivocada en `attendance_records`. No era un problema de presentación: el dato entraba mal.

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

### Soporte adjunto (2026-08-14)

El acudiente puede adjuntar **un** PDF o imagen (JPG/PNG/WEBP) hasta `JUSTIFICATION_MAX_UPLOAD_MB` (5).

- El endpoint pasa a ser **multipart**, no JSON: `reason` como `Form`, `attachment` como `UploadFile`
  opcional.
- El archivo va al bucket en `justifications/{institution_id}/{attendance_record_id}.{ext}`; en la BD se
  guarda la **key**, no la URL (las presignadas caducan). Metadatos en las columnas `attachment_*`.
- La **extensión sale de la tabla blanca de content-types, nunca del nombre del cliente**, y el nombre
  original se sanea (`_safe_filename`) porque acaba en un atributo `download` del navegador del docente.
- Se sube al bucket **antes** de escribir en la BD: si la transacción revierte queda un objeto huérfano,
  que es preferible a una fila apuntando a un archivo inexistente.
- Los intentos rechazados (tipo o tamaño inválidos) **no consumen el token**: el acudiente puede corregir.

Al ser un endpoint público, el tope de tamaño y la lista blanca son la única defensa. No relajarlos.

---

## Seguimiento del docente: Inasistencias y Mensajes (2026-08-14)

Dos secciones de **Seguimiento**, con el mismo patrón que el Historial de convivencia: filtro por
estudiante, filas clicables, detalle, notas append-only y cierre de caso reversible. Ambas están
también en el dashboard del operador PAE.

### Inasistencias — lo que nadie justificó

Criterio: `period_order = 1` + `status = ABSENT` + **sin fila en `attendance_justifications`**.

- El criterio de salida es la **existencia de la justificación**, no el estado del registro: en cuanto
  el acudiente usa el enlace, el caso desaparece de aquí y aparece en Mensajes.
- `LATE` queda fuera a propósito: el estudiante sí llegó.
- Badge **"Aviso enviado" / "Sin aviso"** según exista el `attendance_token`, que es lo que crea el
  notifier al mandar el correo. Responde a "¿el acudiente se enteró siquiera?".
- Cierre reversible en `attendance_records.absence_closed_at` — **no** se llama `archived_at` porque el
  registro sigue contando en el roster, en la toma de lista y en las estadísticas; lo único que se
  cierra es el seguimiento.
- Notas en `attendance_absence_notes`. **Sobreviven** si el caso pasa a Mensajes: cuelgan del
  `attendance_record`, no de la justificación.

| Método y ruta | Descripción |
|---|---|
| `GET /attendance/absences` | `student_id`, `include_closed`, `skip`, `limit` |
| `GET /attendance/absences/{record_id}` | Detalle. Accesible aunque el caso esté cerrado |
| `POST /attendance/absences/{record_id}/notes` | Body `{ note }` |
| `POST /attendance/absences/{record_id}/archive` · `/unarchive` | Cerrar / reabrir |

### Mensajes — las excusas recibidas

Cierre en `attendance_justifications.archived_at`, notas en `attendance_justification_notes`.

| Método y ruta | Descripción |
|---|---|
| `GET /attendance/justifications` | `student_id`, `include_archived`, `skip`, `limit` |
| `GET /attendance/justifications/{id}` | Detalle con soporte y notas |
| `POST /attendance/justifications/{id}/notes` | Body `{ note }` |
| `POST /attendance/justifications/{id}/archive` · `/unarchive` | Cerrar / reabrir |

En ambas el aislamiento es **doble**: por institución y por `recorded_by_user_id`. Un docente solo ve
los casos de las inasistencias que él reportó.

> `attendance_justifications` **no denormaliza `institution_id`**: el tenant se valida con join a
> `attendance_records`. Tenerlo presente al escribir queries nuevas sobre esa tabla.

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
| `GET /attendance/today` | Todas las clases del docente hoy (con `already_taken` e `is_first_hour`) |
| `GET /attendance/classes/{class_period_id}` | Roster + estado de hoy de una clase específica |
| `POST /attendance` | Toma de lista. Body `{ class_period_id, entries:[{student_id, status}] }` |
| `POST /attendance/records/{record_id}/arrived` | Marca `ABSENT` → `LATE` (llegó tarde) |
| `GET /attendance/schedule` | Horario semanal del docente (sus `class_periods`) |
| `GET /attendance/justifications` | Excusas enviadas por los acudientes para los registros de este docente (incluye `photo_url` presignado) |

`GET /attendance/classes/{class_period_id}` (ejemplo):
```json
{ "class_period_id": "…", "group_name": "A", "grade_name": "Once",
  "period_name": "Primera hora", "period_order": 1, "is_first_hour": true,
  "start_time": "07:00:00", "end_time": "07:50:00",
  "date": "2026-06-24", "already_taken": false,
  "students": [ { "student_id":"…", "document_number":"1010100001",
    "first_name":"Mariana", "last_name":"Gómez", "photo_url":null,
    "status": null, "record_id": null } ] }
```

`POST /attendance` — validaciones:
- status solo `PRESENT` o `ABSENT` → si no, `400`.
- la clase debe pertenecer al docente → `404`.
- no se puede haber tomado ya hoy (por clase) → `409`.
- las entradas deben cubrir **exactamente** al grupo → `400`.

(Ya **no** se exige `period_order = 1`: se toma lista de cualquier clase. La
notificación solo se encola en primera hora.)

`POST /attendance/records/{record_id}/arrived`: `404` si no existe ·
`409` si el registro no está `ABSENT` (idempotente si ya es `LATE`).

### Justificación (público, sin JWT)

| Método y ruta | Descripción |
|---|---|
| `GET /attendance/justify/{token}` | Info para mostrar en la página (validez, estudiante, fecha) |
| `POST /attendance/justify/{token}` | **multipart**: `reason` (Form) + `attachment` (File, opcional). Registra la justificación → `JUSTIFIED` |

`GET` responde siempre `200` con `valid` y un `message` describiendo el estado
(válido, expirado, ya justificado, inválido). `POST`: `404` token inválido ·
`409` ya justificada · `410` expirado · `400` formato de adjunto no admitido · `413` adjunto > 5 MB.

### Salidas tempranas (rol docente / operador PAE — `require_staff`)

| Método y ruta | Descripción |
|---|---|
| `POST /departures` | Body `{ student_id, departure_time, reason? }`. Crea y notifica |
| `GET /departures` | Salidas de hoy **registradas por el usuario autenticado** (`recorded_by_user_id`), no toda la institución. Incluye `student_name`, `photo_url` presignado |

---

## Jobs y notificaciones

Las tareas Celery son síncronas pero la BD es async. `app/jobs/runner.py::run_db_job`
levanta un engine `NullPool` propio por tarea, hace commit/rollback y lo descarta.

| Tarea | Encolada por | Cuándo dispara |
|-------|--------------|----------------|
| `notify_absence_first_hour(record_id)` | `submit_attendance` por cada `ABSENT`, **solo si `period_order == 1`** | `countdown = ATTENDANCE_GRACE_MINUTES * 60` |
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

- **Asistencia** — selector de las clases del día; al abrir una, se toma lista con
  dos botones Presente/Ausente (sin preseleccionar; "Guardar" deshabilitado hasta
  marcar a todos). Si ya se tomó, muestra estados y botón "Llegó (tardanza)" en los
  ausentes. Etiqueta "1ª hora" y aviso "sin notificación" en las demás clases.
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
| `ATTENDANCE_GRACE_MINUTES` | `50` | Minutos de gracia antes de notificar. **Bajado a `2` en el `.env` local desde 2026-08-14 para pruebas — revertir antes de producción** (ver `runbook.md`). |
| `JUSTIFICATION_MAX_UPLOAD_MB` | `5` | Tope del soporte que adjunta el acudiente. |
| `FRONTEND_URL` | `http://localhost:5173` | Base de los enlaces de justificación que van en el correo. |

---

## Probarlo

```bash
docker compose up -d                      # incluye worker + beat
docker compose exec api alembic upgrade head
docker compose exec -T postgres psql -U biga -d biga < scripts/seed_dev_users.sql
```

Pon `ATTENDANCE_GRACE_MINUTES=1` en `.env` para no esperar 50 minutos. Login como
`teacher@iedemo.edu.co` / `password123` → **Asistencia** (grupo 11A, horario
completo sembrado lun–vie) → abre la **primera hora** → marca un ausente → guarda.
~1 minuto después el worker procesa la notificación; toma el enlace
`/justificar/{token}` de los logs del worker y ábrelo para justificar. (Tomar lista
de una clase que no sea primera hora **no** genera correo.)

---

*Referencia funcional — Asistencia y Salidas tempranas | BIGA*
