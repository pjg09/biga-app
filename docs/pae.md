# Módulo PAE — Referencia funcional

> Cómo funciona el Programa de Alimentación Escolar (PAE) en BIGA, tal como está
> implementado. Para el modelo de datos ver `docs/database-schema.md`; para los
> patrones de arquitectura ver `docs/architecture.md`.

---

## Qué resuelve

El PAE registra la **entrega diaria del almuerzo escolar**. Un operador PAE:

1. Inscribe a los estudiantes al programa para el año académico.
2. Cada día ve el listado de inscritos y marca a quién le entregó el almuerzo.
3. El sistema garantiza que cada registro sea **a prueba de manipulación** y que
   **nadie reciba doble entrega** el mismo día.

El rol que opera el módulo es `PAE_OPERATOR`. Todos los endpoints lo exigen
(`require_pae_operator`); un `TEACHER` recibe `403`.

---

## Integridad: doble hash encadenado

Inscripciones y entregas son un **libro contable**: una vez creadas, los campos que
entran en el hash no se editan ni se borran por API (`pae_enrollments` no tiene
`PUT`/`PATCH`/`DELETE` propio). Cada registro se firma con HMAC-SHA256 usando
`PAE_SIGNING_SECRET`, que **nunca vive en la base de datos**.

Excepción explícita: `pae_enrollments.is_active` (booleano de estado, **no** entra en el
hash) se puede alternar desde `PUT /admin/students/{id}` — el switch "Inscrito en el PAE"
del formulario de edición del admin (`docs/students.md`). No es un endpoint de
`/pae/enrollments`; vive en el flujo de edición del estudiante y reutiliza
`compute_enrollment_hash` sin recalcularlo. Desactivar/reactivar nunca toca `student_id`,
`institution_id`, `academic_year`, `enrolled_at` ni `enrollment_hash` — por eso no rompe la
regla de arriba, y `GET /pae/audit` (que recalcula ambas capas desde esos campos) sigue
dando `hash_valid=true` sobre las entregas de un estudiante cuya inscripción se desactivó y
reactivó después.

| Capa | Campo | Qué firma |
|------|-------|-----------|
| 1 | `pae_enrollments.enrollment_hash` | `student_id : institution_id : academic_year : enrolled_at` |
| 2 | `pae_deliveries.delivery_hash` | `student_id : delivery_date : delivered_by_user_id : created_at : enrollment_hash` |

La capa 2 **incluye el hash de la inscripción**, encadenando cada entrega a la
inscripción exacta que la habilitó. Consecuencias:

- Alterar una inscripción (p. ej. cambiar el `academic_year` en la BD) invalida
  su `enrollment_hash` **y** el `delivery_hash` de todas sus entregas.
- Reescribir una entrega (fecha, estudiante, operador) invalida su `delivery_hash`.
- Borrar una inscripción deja huérfanas sus entregas → la auditoría lo detecta.
- Quien tenga acceso de escritura directo a Postgres no puede regenerar hashes
  válidos sin la clave secreta.

> No es `SHA(SHA(x))`. El valor está en **encadenar** dos firmas HMAC con clave
> secreta sobre datos distintos pero dependientes. Funciones en
> `app/core/security.py`: `compute_enrollment_hash`, `compute_delivery_hash` y
> sus `verify_*`.

Los campos `enrolled_at` y `created_at` se fijan **en la aplicación** (no
`server_default`) porque entran en el hash. No cambiarlos a `server_default` sin
ajustar el cálculo.

---

## Flujo completo

```
1. Operador registra estudiante         POST /students            (módulo students)
2. Operador inscribe al PAE             POST /pae/enrollments      → enrollment_hash (capa 1)
3. Cada día: ve el listado              GET  /pae/students/today
4. Marca la entrega                     POST /pae/deliveries       → verifica capa 1, escribe capa 2
5. Reporte semanal                      GET  /pae/report/weekly
6. Auditoría de integridad              GET  /pae/audit            → recomputa ambas capas
```

Al registrar una entrega (`POST /pae/deliveries`) el service:

1. Identifica al estudiante mediante la **Strategy** (`DocumentSearchStrategy` en
   MVP; `FacialRecognitionStrategy` reservada para fase 2, hoy devuelve `501`).
2. Verifica que tenga **inscripción activa** en el año vigente → `422` si no.
3. **Verifica la capa 1**: si el `enrollment_hash` no coincide, la inscripción
   fue manipulada → `409` y no entrega.
4. Verifica que no haya **entrega previa hoy** (`UNIQUE (student_id, delivery_date)`)
   → `409`.
5. Calcula el `delivery_hash` encadenando el `enrollment_hash` y persiste.

---

## Endpoints

Todos bajo el prefijo `/pae`, todos requieren rol `PAE_OPERATOR`. El
`institution_id` y el `delivered_by_user_id` salen del JWT, nunca del request.

### `GET /pae/students/today`
Listado del día: estudiantes con inscripción activa en el año vigente y si ya
recibieron entrega hoy.
```json
[
  { "student_id": "…", "document_number": "1010100001", "first_name": "Mariana",
    "last_name": "Gómez", "photo_url": null, "delivered": false }
]
```

### `GET /pae/delivery-window`
Hora de cierre del PAE de la institución (`institutions.pae_delivery_end_time`),
para que el front calcule la cuenta regresiva y sepa cuándo cerrar la tabla.
Accesible a PAE_OPERATOR o ADMIN, igual que el listado del día.
```json
{ "delivery_end_time": "12:00:00" }
```

### `POST /pae/enrollments` — **solo ADMIN** (`require_admin`)
Inscribe a un estudiante al PAE del año vigente. Genera el `enrollment_hash`.

> **Regla de dominio (2026-08-13):** el operador PAE **no matricula a nadie**. Opera el programa —toma
> el listado, ve métricas, consulta matriculados— pero admitir a un estudiante al PAE es una decisión
> administrativa. Antes este endpoint admitía `PAE_OPERATOR`.
```json
// request
{ "student_id": "…" }
```
Errores: `404` estudiante inexistente en la institución · `409` ya inscrito este año.

### `POST /pae/deliveries`
Registra la entrega del día.
```json
// request
{ "student_id": "…", "identification_method": "DOCUMENT" }
```
Errores: `404` estudiante no encontrado · `422` no inscrito en el PAE ·
`409` inscripción comprometida (hash inválido) · `409` ya recibió entrega hoy.

### `GET /pae/report/weekly`
Conteo de entregas de la semana actual (lunes a viernes).
```json
{ "week_start": "2026-06-22", "week_end": "2026-06-26", "total": 12,
  "items": [ { "delivery_date": "2026-06-22", "count": 4 }, … ] }
```

### `GET /pae/audit`
Recomputa ambas capas de hash de todas las entregas y reporta manipulaciones.
```json
{ "total": 20, "tampered": 1, "records": [
  { "delivery_id": "…", "student_id": "…", "delivery_date": "2026-06-23",
    "delivered_by_user_id": "…", "enrollment_hash_valid": true,
    "delivery_hash_valid": false, "hash_valid": false } ] }
```
`hash_valid` es la conjunción de ambas capas. `tampered` cuenta los registros con
la cadena rota.

---

## Roles

| Acción | Endpoint | Quién |
|---|---|---|
| Listado del día | `GET /pae/students/today` | PAE_OPERATOR o ADMIN |
| Hora de cierre | `GET /pae/delivery-window` | PAE_OPERATOR o ADMIN |
| Registrar entrega | `POST /pae/deliveries` | Solo PAE_OPERATOR |
| Reporte semanal / auditoría | `GET /pae/report/weekly`, `/pae/audit` | Solo PAE_OPERATOR |
| **Matricular al PAE** | `POST /pae/enrollments` | **Solo ADMIN** |

Los módulos de **Aula** del operador PAE (Asistencia, Estudiantes, Horario, Salidas) son literalmente
los del docente: `PAEDashboard` monta `TeacherStudentsView`, no `StudentsView`. Su listado de
"Mis estudiantes" está acotado a sus salones igual que el de cualquier docente.

Desajuste conocido: el ADMIN puede matricular pero **no** accede a `/pae/report/weekly` ni `/pae/audit`,
que siguen restringidos al operador.

## Frontend

`web/src/pages/PAEDashboard.jsx` (rol PAE_OPERATOR, ruta `/dashboard/pae`):

- **Registro PAE** — listado del día, búsqueda, modal de confirmación de entrega
  (muestra la foto para corroborar identidad; click en la foto la abre ampliada
  en un lightbox).
- **Reporte semanal** — conectado a `GET /pae/report/weekly` (datos reales). Se llamaba
  "Reporte diario" en el nav aunque el contenido siempre fue semanal (Lun-Vie); renombrado
  2026-08-14 para que el nombre no mienta sobre el contenido.
- **Matriculados** — inscritos del PAE.
- **Estudiantes** — alta de estudiante (con matrícula y acudientes) e inscripción al PAE.
  Vive en `PAEDashboard.jsx` por historia, pero la usa **solo** `AdminDashboard` — ver el
  detalle completo del componente `StudentsView` en `docs/students.md`.

Además, el operador PAE es un docente con funciones extra: `PAEDashboard` reutiliza
las vistas de aula de `TeacherDashboard` (Asistencia, Convivencia, Historial, etc.).

Servicios: `web/src/services/pae.js`, `web/src/services/students.js`.

---

## Notificación de no-reclamo y bloqueo por hora de corte

`institution.pae_delivery_end_time` es la hora de cierre del PAE, **por
institución**. Dos mecanismos dependen de ella:

1. **Bloqueo de registro tardío** (`PAEService.register_delivery`): si
   `datetime.now().time() >= pae_delivery_end_time`, el registro de una
   entrega se rechaza con `403`. El operador PAE no puede marcar entregas
   después del corte.
2. **Sweep de no-reclamo** (`app/jobs/pae_jobs.py::sweep_pae_no_claim`, beat
   cada 15 min, todo el día): para cada institución cuyo corte ya pasó,
   encola `notify_pae_no_claim`. Ese job cuenta las entregas del día — si hay
   0, asume que el PAE no operó (feriado) y no notifica; si hay ≥1, notifica
   por correo a los acudientes de inscritos activos **sin** entrega y **sin**
   notificación previa hoy (idempotente: correr el sweep varias veces la
   tarde no duplica correos).

**Por qué el bloqueo existe:** antes de agregarlo, el registro de una entrega
no tenía restricción horaria, así que un operador podía marcar tarde a un
estudiante (fila, olvido) después de que el sweep ya lo hubiera evaluado y
notificado como "no reclamó" — el acudiente se quedaba con un correo
incorrecto sin ninguna corrección. El bloqueo elimina esa carrera en
operación normal: nadie puede registrar una entrega después del corte, así
que el sweep nunca ve el estado cambiar bajo sus pies.

**Reflejo en el front (`PAERegisterView`, `PAEDashboard.jsx`):** una 4ª stat
card muestra la cuenta regresiva hasta el corte (`GET /pae/delivery-window` +
tick de 1s vía `setInterval`, todo cliente); pasada la hora, muestra la hora a
la que cerró. La determinación de "cerrado" es puramente visual — la comparo
contra `new Date()` del navegador, asumiendo mismo huso horario que el
servidor (América/Bogotá, app de una sola zona horaria). El bloqueo real lo
sigue haciendo el backend en `register_delivery`; si el reloj del cliente
está desincronizado, la UI puede tardar unos segundos en reflejarlo pero el
`403` del backend es la autoridad. Pasado el corte, la tabla del listado del
día pierde la columna de acción y el badge amarillo pasa de "Pendiente" a
"No reclamado" (ya no hay nada pendiente, el día cerró).

**Red de seguridad — `notify_pae_late_claim_correction`:** si pese al
bloqueo llega a registrarse una entrega para un estudiante que ya tiene una
notificación `PAE_NO_CLAIM` de hoy (único camino: un ADMIN adelanta y luego
vuelve a abrir `pae_delivery_end_time` en el mismo día), `register_delivery`
encola este job, que le manda al acudiente un correo aclaratorio y lo deja
logueado como `NotificationType.PAE_LATE_CLAIM_CORRECTION`. En operación
normal no debería dispararse nunca — es un catch para el caso borde de
cambiar la hora de corte a mitad del día, no el mecanismo principal.

---

## Configuración

| Variable | Descripción |
|----------|-------------|
| `PAE_SIGNING_SECRET` | Clave HMAC de la cadena de integridad. Mínimo 32 caracteres. **Nunca** en la BD. |

---

## Probarlo

```bash
docker compose up -d
docker compose exec api alembic upgrade head
docker compose exec -T postgres psql -U biga -d biga < scripts/seed_dev_users.sql
```

Login como `pae@iedemo.edu.co` / `password123` → **Estudiantes** →
"Inscribir en PAE" → **Registro PAE** muestra el listado del día → confirmar
entrega. La inscripción se hace desde la app (no por SQL) porque el
`enrollment_hash` depende de la clave secreta y del timestamp.

---

*Referencia funcional — Módulo PAE | BIGA*


---

## Envío de los avisos de no reclamo — un correo, una tarea

`sweep_pae_no_claim` (beat, cada 15 min) encola `notify_pae_no_claim` por institución cuya hora
de cierre ya pasó. Ese job **ya no envía**: prepara y reparte.

1. Si hubo **0 entregas** ese día no hace nada (el PAE no operó; notificar sería un falso
   positivo a todas las familias).
2. Por cada inscrito sin ración y con acudiente primario, crea la fila de `notifications_log`
   en estado **PENDING** y encola `send_pae_no_claim_email` con `countdown = i × notification_spacing_seconds`.
3. `send_pae_no_claim_email` **relee el estado** antes de enviar: si el estudiante reclamó
   mientras esperaba turno, la marca `SUPPRESSED` (no se intentó a propósito) en vez de mandar
   un correo falso. Si ya no está `PENDING`, no hace nada — no hay segundo correo a la familia.

### Por qué así

Con el bucle anterior —un job por institución que enviaba todo seguido— el proveedor rechazó
**12 de 14** avisos con `550 Too many emails per second`. Un `FAILED` no se reintenta ni tiene
pantalla de reenvío: esos 12 se perdían.

Las tres piezas son necesarias y distintas:

| Pieza | Qué resuelve |
|---|---|
| `countdown` escalonado | Reparte la salida inicial del lote |
| `rate_limit` en la tarea | **Coordina entre tareas**, incluidos los reintentos, que el countdown ignora |
| `RetryingEmailAdapter` | Absorbe el rechazo puntual con backoff exponencial + jitter |

> El PENDING al encolar es lo que hace idempotente al barrido: con 300 inscritos los últimos
> correos salen minutos después, y sin esa marca el barrido de los 15 minutos siguientes los
> volvería a encolar.

Mismo escalonado en Asistencia (`attendance_service`): 30 ausencias de primera hora se encolaban
con el **mismo** `countdown` y salían en ráfaga.
