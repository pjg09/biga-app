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

Inscripciones y entregas son un **libro contable**: una vez creadas no se editan
ni se borran por API (no hay `PUT`/`PATCH`/`DELETE`). Cada registro se firma con
HMAC-SHA256 usando `PAE_SIGNING_SECRET`, que **nunca vive en la base de datos**.

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

### `POST /pae/enrollments`
Inscribe a un estudiante al PAE del año vigente. Genera el `enrollment_hash`.
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

## Frontend

`web/src/pages/PAEDashboard.jsx` (rol PAE_OPERATOR, ruta `/dashboard/pae`):

- **Registro PAE** — listado del día, búsqueda, modal de confirmación de entrega
  (muestra la foto para corroborar identidad; click en la foto la abre ampliada
  en un lightbox).
- **Reporte diario** — conectado a `GET /pae/report/weekly` (datos reales).
- **Matriculados** — inscritos del PAE.
- **Estudiantes** — registrar estudiante (`POST /students`) con **subida de foto a
  MinIO** (file picker → `POST /students/{id}/photo`; se guarda la key y se presigna
  al leer, ver `app/core/photos.py`) e **inscribir al PAE** (`POST /pae/enrollments`)
  por estudiante.

Además, el operador PAE es un docente con funciones extra: `PAEDashboard` reutiliza
las vistas de aula de `TeacherDashboard` (Asistencia, Convivencia, Historial, etc.).

Servicios: `web/src/services/pae.js`, `web/src/services/students.js`.

---

## Notificación de no-reclamo (pendiente)

El job `app/jobs/pae_jobs.py::notify_pae_no_claim` es todavía un **stub**. La
lógica prevista (ver `docs/database-schema.md`): al cierre de
`institution.pae_delivery_end_time`, si hubo ≥1 entrega ese día, notificar a los
acudientes de inscritos activos **sin** entrega registrada. Si no hubo ninguna
entrega, se asume que el PAE no operó y no se notifica. Cuando se implemente,
seguirá el mismo patrón de jobs que asistencia (`run_db_job` + notifier +
`notifications_log`).

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
