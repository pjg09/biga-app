# BIGA — Esquema de Base de Datos

> Documento de referencia para el modelo de datos del MVP.  
> Todo cambio al esquema debe reflejarse aquí antes de escribir la migración correspondiente.

---

## Decisiones de diseño

| Decisión | Comportamiento definido |
|---|---|
| Acudientes múltiples | Un estudiante puede tener varios acudientes registrados. Las notificaciones se envían únicamente al marcado como `is_primary = true`. |
| Horario de clases | El horario varía por día de la semana (`day_of_week`). Cada `class_period` es una combinación única de grupo + orden + día. |
| PAE en días sin servicio | El job de notificación PAE solo se ejecuta si existe al menos una entrega registrada ese día (`COUNT(pae_deliveries) > 0`). Si el PAE no operó, nadie abrió la app y el conteo es cero — el job no notifica. |
| Notificaciones por acudiente | Si un acudiente tiene dos estudiantes en la institución, recibe una notificación independiente por cada uno. No se agrupan. |
| Firma del estudiante | Se guarda como archivo PNG en object storage. La columna `signature_url` almacena la URL. No se guarda base64 en la base de datos. |
| Multi-tenancy | Todas las tablas operativas incluyen `institution_id`. El MVP puede arrancar con una sola institución sin cambios de esquema. |
| Leads de la landing | `demo_leads` es la **única** tabla sin `institution_id`, por decisión explícita. Un visitante que pide una demo todavía no pertenece a ninguna institución: forzar un tenant obligaría a inventar una institución "prospectos" que no representa nada real. Es una tabla pre-tenant, no operativa, y ningún flujo autenticado la lee. |
| Identificación PAE | `identification_method` registra si la entrega fue por documento o reconocimiento facial. El valor `FACIAL` queda reservado para fase 2. |

---

## Convenciones

- Todos los IDs son `UUID` generados en la aplicación, no `SERIAL`.
- `created_at` se registra en todas las tablas. Columnas de auditoría adicionales (`updated_at`) se agregan según necesidad real, no preventivamente.
- Los ENUMs se definen como tipos PostgreSQL nativos.
- Los campos `institution_id` en tablas hijas son denormalizados intencionalmente para evitar joins costosos en queries frecuentes.

---

## Extensiones de PostgreSQL

- `unaccent` (migración `d4a2c7e91b05`): habilita la búsqueda de estudiantes insensible a acentos. El repositorio envuelve columna y patrón en `unaccent(...)` en el `WHERE` (ej. `unaccent(nombre) ILIKE unaccent('%lopez%')` encuentra "López"). `ILIKE` cubre además el caso de mayúsculas.

---

## Tablas

### `institutions`

Raíz del modelo multi-tenant. Cada registro representa una institución educativa.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `name` | VARCHAR(255) | NOT NULL | Nombre oficial de la institución |
| `nit` | VARCHAR(20) | NOT NULL, UNIQUE | NIT de la institución |
| `address` | VARCHAR(255) | NOT NULL | |
| `city` | VARCHAR(100) | NOT NULL | |
| `pae_delivery_end_time` | TIME | NOT NULL | Hora de cierre del PAE. El sweep de notificación (`sweep_pae_no_claim`) se programa contra este valor, y `PAEService.register_delivery` la usa para **bloquear el registro de entregas** una vez pasada. |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

---

### `grades`

Grados académicos de una institución (Primero a Once).

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `institution_id` | UUID | NOT NULL, FK → institutions | |
| `name` | VARCHAR(50) | NOT NULL | Nombre visible: "Sexto", "Séptimo" |
| `level` | SMALLINT | NOT NULL | Valor numérico 1–11 |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**Restricciones adicionales:**
```sql
UNIQUE (institution_id, level)
```

---

### `groups`

Salones dentro de un grado (6A, 6B, etc.). Se crean por año académico.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `institution_id` | UUID | NOT NULL, FK → institutions | Denormalizado |
| `grade_id` | UUID | NOT NULL, FK → grades | |
| `name` | VARCHAR(10) | NOT NULL | "A", "B", "C" |
| `academic_year` | SMALLINT | NOT NULL | Año: 2026 |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**Restricciones adicionales:**
```sql
UNIQUE (grade_id, name, academic_year)
```

---

### `class_periods`

Bloques horarios de un salón. Define qué clase es "primera hora" por día de la semana, dato crítico para el trigger de notificación de inasistencia.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `institution_id` | UUID | NOT NULL, FK → institutions | Denormalizado |
| `group_id` | UUID | NOT NULL, FK → groups | |
| `name` | VARCHAR(100) | NOT NULL | "Primera hora", "Educación Física" |
| `period_order` | SMALLINT | NOT NULL | 1 = primera hora del día |
| `start_time` | TIME | NOT NULL | |
| `end_time` | TIME | NOT NULL | |
| `day_of_week` | SMALLINT | NOT NULL | 1 = Lunes, 5 = Viernes |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**Restricciones adicionales:**
```sql
UNIQUE (group_id, period_order, day_of_week)
CHECK (day_of_week BETWEEN 1 AND 5)
CHECK (period_order >= 1)
CHECK (start_time < end_time)
```

---

### `users`

Docentes de la institución. Único perfil operativo del MVP.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `institution_id` | UUID | NOT NULL, FK → institutions | |
| `document_number` | VARCHAR(20) | NOT NULL | |
| `first_name` | VARCHAR(100) | NOT NULL | |
| `last_name` | VARCHAR(100) | NOT NULL | |
| `email` | VARCHAR(255) | NOT NULL, UNIQUE | Usado para login |
| `hashed_password` | VARCHAR(255) | NOT NULL | bcrypt |
| `role` | ENUM | NOT NULL | `TEACHER`, `PAE_OPERATOR`, `ADMIN` |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**ENUMs:**
```sql
CREATE TYPE user_role AS ENUM ('TEACHER', 'PAE_OPERATOR', 'ADMIN');
```

---

### `user_groups`

Asignación de un docente a un salón para un año académico.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `user_id` | UUID | NOT NULL, FK → users | |
| `group_id` | UUID | NOT NULL, FK → groups | |
| `academic_year` | SMALLINT | NOT NULL | |

**Restricciones adicionales:**
```sql
UNIQUE (user_id, group_id, academic_year)
```

---

### `students`

Estudiantes de la institución. Referente pasivo del sistema: no tiene login.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `institution_id` | UUID | NOT NULL, FK → institutions | |
| `document_number` | VARCHAR(20) | NOT NULL | |
| `first_name` | VARCHAR(100) | NOT NULL | |
| `last_name` | VARCHAR(100) | NOT NULL | |
| `birth_date` | DATE | NOT NULL | |
| `photo_url` | VARCHAR(500) | NULLABLE | **Key** del objeto en storage (foto subida a MinIO vía `POST /students/{id}/photo`); se presigna al leer (`resolve_photo_url`). Por compatibilidad también acepta una URL externa (se deja pasar tal cual). Se usa para corroborar identidad en el flujo por documento y como referencia para reconocimiento facial (fase 2). |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**Restricciones adicionales:**
```sql
UNIQUE (institution_id, document_number)
```

---

### `student_groups`

Asignación de un estudiante a un salón por año académico. Un estudiante pertenece a un único salón por año.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `student_id` | UUID | NOT NULL, FK → students | |
| `group_id` | UUID | NOT NULL, FK → groups | |
| `academic_year` | SMALLINT | NOT NULL | |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | |

**Restricciones adicionales:**
```sql
UNIQUE (student_id, academic_year)
```

---

### `guardians`

Acudientes vinculados a un estudiante. Las notificaciones se envían al marcado como `is_primary`.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `student_id` | UUID | NOT NULL, FK → students | |
| `full_name` | VARCHAR(255) | NOT NULL | |
| `relationship` | ENUM | NOT NULL | `PADRE`, `MADRE`, `ACUDIENTE`, `OTRO` |
| `email` | VARCHAR(255) | NOT NULL | Destino de las notificaciones |
| `phone` | VARCHAR(20) | NULLABLE | |
| `is_primary` | BOOLEAN | NOT NULL, DEFAULT FALSE | Solo un acudiente puede ser primario por estudiante |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**ENUMs:**
```sql
CREATE TYPE guardian_relationship AS ENUM ('PADRE', 'MADRE', 'ACUDIENTE', 'OTRO');
```

**Restricciones adicionales:**
```sql
-- Garantiza que solo un acudiente sea primario por estudiante.
-- Se implementa con un índice parcial único en PostgreSQL:
CREATE UNIQUE INDEX one_primary_per_student
  ON guardians (student_id)
  WHERE is_primary = TRUE;
```

---

### `pae_enrollments`

Inscripción de un estudiante al programa PAE para un año académico. Define el "listado del día": cualquier estudiante con inscripción activa en el año vigente está habilitado para recibir PAE.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `student_id` | UUID | NOT NULL, FK → students | |
| `institution_id` | UUID | NOT NULL, FK → institutions | Denormalizado |
| `academic_year` | SMALLINT | NOT NULL | |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | |
| `enrolled_at` | TIMESTAMP | NOT NULL | Fijado explícitamente por la app (no server_default) para incluirlo en el hash. |
| `enrollment_hash` | VARCHAR(64) | NOT NULL | HMAC-SHA256 hex de la inscripción (capa 1 de la cadena de integridad). Clave nunca almacenada en BD. |

**Restricciones adicionales:**
```sql
UNIQUE (student_id, academic_year)
```

> `enrollment_hash` es la **capa 1** de la cadena de integridad del PAE. Firma `student_id : institution_id : academic_year : enrolled_at`. El `delivery_hash` de cada entrega encadena este valor (ver `pae_deliveries`), atando la entrega a la inscripción exacta que la habilitó. Si alguien fabrica o altera una inscripción directamente en la BD, su hash deja de coincidir y la auditoría (`GET /pae/audit`) lo marca; además `register_delivery` rechaza entregar contra una inscripción comprometida.

---

### `pae_deliveries`

Registro de cada entrega PAE realizada. La constraint `UNIQUE (student_id, delivery_date)` es la garantía de integridad referencial contra dobles entregas.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `student_id` | UUID | NOT NULL, FK → students | |
| `institution_id` | UUID | NOT NULL, FK → institutions | Denormalizado |
| `delivered_by_user_id` | UUID | NOT NULL, FK → users | Docente que confirmó la entrega |
| `delivery_date` | DATE | NOT NULL | |
| `identification_method` | ENUM | NOT NULL | `DOCUMENT` (MVP), `FACIAL` (fase 2) |
| `delivery_hash` | VARCHAR(64) | NOT NULL | HMAC-SHA256 hex de la entrega (capa 2 de la cadena). Encadena el `enrollment_hash`. Clave nunca almacenada en BD. |
| `created_at` | TIMESTAMP | NOT NULL | Fijado explícitamente por la app (no server_default) para incluirlo en el hash. |

**ENUMs:**
```sql
CREATE TYPE pae_identification_method AS ENUM ('DOCUMENT', 'FACIAL');
```

**Restricciones adicionales:**
```sql
UNIQUE (student_id, delivery_date)
```

> `delivery_hash` es la **capa 2** de la cadena de integridad. Firma `student_id : delivery_date : delivered_by_user_id : created_at : enrollment_hash`. Al incluir el `enrollment_hash` de la inscripción, cualquier manipulación de la inscripción **o** de la entrega rompe la verificación. La auditoría comprueba ambas capas por separado (`enrollment_hash_valid`, `delivery_hash_valid`) y reporta `hash_valid` como la conjunción de ambas.

**Lógica del job de notificación PAE:**
```
SI COUNT(pae_deliveries WHERE delivery_date = hoy AND institution_id = X) = 0:
    → No notificar. Se asume que el PAE no operó ese día.
SI COUNT > 0:
    → Notificar a los acudientes de estudiantes con pae_enrollments activo
      que no tienen registro en pae_deliveries para hoy.
```

---

### `attendance_records`

Un registro por estudiante por clase por día. El campo `status` puede actualizarse a `JUSTIFIED` cuando el acudiente completa el formulario de justificación.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `student_id` | UUID | NOT NULL, FK → students | |
| `group_id` | UUID | NOT NULL, FK → groups | |
| `class_period_id` | UUID | NOT NULL, FK → class_periods | |
| `institution_id` | UUID | NOT NULL, FK → institutions | Denormalizado |
| `recorded_by_user_id` | UUID | NOT NULL, FK → users | |
| `date` | DATE | NOT NULL | |
| `status` | ENUM | NOT NULL | `PRESENT`, `ABSENT`, `LATE`, `JUSTIFIED` |
| `absence_closed_at` | TIMESTAMP | NULLABLE | Caso cerrado por el docente en la sección "Inasistencias". **No oculta el registro**: sigue contando en el roster, en la toma de lista y en las estadísticas |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**ENUMs:**
```sql
CREATE TYPE attendance_status AS ENUM ('PRESENT', 'ABSENT', 'LATE', 'JUSTIFIED');
```

**Restricciones adicionales:**
```sql
UNIQUE (student_id, class_period_id, date)
```

**Trigger de notificación:** al tomar lista de la primera hora (`period_order = 1`), cada registro `ABSENT` encola una tarea Celery con `countdown = ATTENDANCE_GRACE_MINUTES` (default 50 min). Al disparar, la tarea relee el `status`: si sigue `ABSENT`, notifica al acudiente con un enlace de justificación de un solo uso; si el docente ya lo marcó `LATE` (llegó tarde), no notifica. La justificación del acudiente lo pasa a `JUSTIFIED`.

---

### `attendance_tokens`

Token de uso único vinculado a una inasistencia específica. Permite al acudiente justificar la ausencia sin necesidad de cuenta en el sistema.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `attendance_record_id` | UUID | NOT NULL, FK → attendance_records, UNIQUE | Un token por inasistencia |
| `token` | UUID | NOT NULL, UNIQUE | Se incluye en el enlace del correo |
| `expires_at` | TIMESTAMP | NOT NULL | Medianoche del día de la inasistencia |
| `used_at` | TIMESTAMP | NULLABLE | NULL = no utilizado aún |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**Regla de validación en la aplicación:**
Un token se considera válido únicamente si `NOW() < expires_at` AND `used_at IS NULL`. Un token expirado o ya utilizado se rechaza aunque sea criptográficamente correcto.

---

### `attendance_justifications`

Respuesta del acudiente al formulario de justificación de inasistencia.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `attendance_record_id` | UUID | NOT NULL, FK → attendance_records, UNIQUE | |
| `token_id` | UUID | NOT NULL, FK → attendance_tokens, UNIQUE | |
| `reason` | TEXT | NOT NULL | Texto libre ingresado por el acudiente |
| `attachment_key` | VARCHAR(500) | NULLABLE | **Key** del soporte en object storage. Se presigna al leer, nunca se guarda la URL |
| `attachment_filename` | VARCHAR(255) | NULLABLE | Nombre original del archivo, para mostrarlo y descargarlo con sentido |
| `attachment_content_type` | VARCHAR(100) | NULLABLE | `application/pdf`, `image/jpeg`, `image/png` o `image/webp` |
| `attachment_size_bytes` | INTEGER | NULLABLE | Tamaño real medido en el servidor, no el declarado por el cliente |
| `archived_at` | TIMESTAMP | NULLABLE | Caso cerrado por el docente. No borra nada: la excusa sigue siendo consultable |
| `submitted_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

> El soporte es **opcional**: las cuatro columnas van juntas (o las cuatro con valor, o las cuatro nulas). Una justificación sin adjunto sigue siendo válida.
>
> **Un soporte por justificación.** `attendance_record_id` ya es UNIQUE, así que hay como mucho una justificación por inasistencia y, por tanto, un archivo. Permitir varios exigiría una tabla hija `attendance_justification_attachments`; no se hizo porque el formulario del acudiente pide un solo documento.
>
> Se guarda la **key**, no la URL, igual que `students.photo_url`: las URLs presignadas caducan y guardarlas dejaría enlaces muertos en la BD. La key va en `justifications/{institution_id}/{attendance_record_id}.{ext}`.
>
> `archived_at` es "caso cerrado", el mismo mecanismo que `discipline_records.archived_at`: se oculta del panel por defecto pero **nunca se borra**. Una excusa es la respuesta de un acudiente a un reporte institucional; borrarla dejaría la inasistencia sin su descargo.

---

### `attendance_absence_notes`

Notas de seguimiento que el docente añade a una inasistencia **sin justificar**. Append-only, igual que las otras dos tablas de notas.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `attendance_record_id` | UUID | NOT NULL, FK → attendance_records | |
| `institution_id` | UUID | NOT NULL, FK → institutions | Denormalizado |
| `author_user_id` | UUID | NOT NULL, FK → users | |
| `note` | TEXT | NOT NULL | |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**Índices:**
```sql
CREATE INDEX idx_absence_notes_record ON attendance_absence_notes (attendance_record_id, created_at);
```

> La sección "Inasistencias" del docente lista los registros con `period_order = 1`, `status = ABSENT` y **sin fila en `attendance_justifications`**. El criterio de salida es la existencia de la justificación, no el estado del registro: en cuanto el acudiente usa el enlace, la inasistencia sale de aquí y aparece en Mensajes.
>
> Las notas **no se borran** cuando eso pasa. Quedan colgadas del `attendance_record`, así que el seguimiento previo del docente sigue siendo consultable aunque el caso se haya movido de sección.

---

### `attendance_justification_notes`

Notas de seguimiento que el docente añade a una excusa. **Append-only**, igual que `discipline_record_notes`: no hay endpoint de edición ni de borrado.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `justification_id` | UUID | NOT NULL, FK → attendance_justifications | |
| `institution_id` | UUID | NOT NULL, FK → institutions | Denormalizado, para filtrar por tenant sin join |
| `author_user_id` | UUID | NOT NULL, FK → users | |
| `note` | TEXT | NOT NULL | |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**Índices:**
```sql
CREATE INDEX idx_justification_notes_justification ON attendance_justification_notes (justification_id, created_at);
```

> Se guarda `author_user_id` y no solo el nombre: el nombre se resuelve por join al mostrar, así que si el docente cambia de apellido las notas antiguas siguen coherentes.

---

### `convivencia_articles`

Artículos del manual de convivencia de la institución. El docente selecciona de este listado al crear un registro en el agendatorio.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `institution_id` | UUID | NOT NULL, FK → institutions | |
| `code` | VARCHAR(20) | NOT NULL | "Art. 15", "Numeral 3.2" |
| `title` | VARCHAR(255) | NOT NULL | |
| `description` | TEXT | NOT NULL | Texto completo del artículo |
| `severity` | ENUM | NOT NULL | `LEVE`, `MODERADA`, `GRAVE` |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**ENUMs:**
```sql
CREATE TYPE article_severity AS ENUM ('LEVE', 'MODERADA', 'GRAVE');
```

**Restricciones adicionales:**
```sql
UNIQUE (institution_id, code)
```

---

### `discipline_records`

Registro en el agendatorio (libro de convivencia digital). Reemplaza el registro en papel.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `student_id` | UUID | NOT NULL, FK → students | |
| `institution_id` | UUID | NOT NULL, FK → institutions | Denormalizado |
| `recorded_by_user_id` | UUID | NOT NULL, FK → users | |
| `date` | DATE | NOT NULL | |
| `observations` | TEXT | NOT NULL | Descripción libre del hecho |
| `signature_url` | VARCHAR(500) | NOT NULL | URL del PNG de la firma en object storage |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |
| `archived_at` | TIMESTAMP | NULLABLE | Ocultar del panel del docente sin borrar. NULL = visible; con fecha = oculto. (migración `e5b3f8c210a7`) |

El registro firmado (artículos, observaciones, firma) es inmutable vía API. El seguimiento posterior se agrega como notas (ver `discipline_record_notes`); ocultarlo solo setea `archived_at`.

---

### `discipline_record_notes`

Notas de seguimiento append-only sobre un registro disciplinario (migración `e5b3f8c210a7`). El registro firmado nunca se modifica; el seguimiento queda como notas inmutables con autor y fecha.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `discipline_record_id` | UUID | NOT NULL, FK → discipline_records | |
| `institution_id` | UUID | NOT NULL, FK → institutions | Denormalizado |
| `author_user_id` | UUID | NOT NULL, FK → users | Docente que escribió la nota |
| `note` | TEXT | NOT NULL | |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**Índices:**
```sql
CREATE INDEX idx_record_notes_record ON discipline_record_notes (discipline_record_id, created_at);
```

---

### `discipline_record_articles`

Relación muchos-a-muchos entre un registro disciplinario y los artículos del manual de convivencia infringidos.

| Columna | Tipo | Restricciones |
|---|---|---|
| `discipline_record_id` | UUID | NOT NULL, FK → discipline_records |
| `article_id` | UUID | NOT NULL, FK → convivencia_articles |

**Restricciones adicionales:**
```sql
PRIMARY KEY (discipline_record_id, article_id)
```

---

### `early_departures`

Registro de retiro anticipado de un estudiante.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `student_id` | UUID | NOT NULL, FK → students | |
| `institution_id` | UUID | NOT NULL, FK → institutions | Denormalizado |
| `recorded_by_user_id` | UUID | NOT NULL, FK → users | |
| `departure_date` | DATE | NOT NULL | |
| `departure_time` | TIME | NOT NULL | |
| `reason` | TEXT | NULLABLE | |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

---

### `notifications_log`

Registro de cada intento de envío de correo. Permite trazabilidad completa y diagnóstico de fallos.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `institution_id` | UUID | NOT NULL, FK → institutions | |
| `type` | ENUM | NOT NULL | `PAE_NO_CLAIM`, `PAE_LATE_CLAIM_CORRECTION`, `ABSENCE_FIRST_HOUR`, `DISCIPLINE_RECORD`, `EARLY_DEPARTURE` |
| `student_id` | UUID | NOT NULL, FK → students | |
| `guardian_id` | UUID | NOT NULL, FK → guardians | |
| `email_to` | VARCHAR(255) | NOT NULL | Snapshot del email al momento del envío |
| `subject` | VARCHAR(255) | NOT NULL | |
| `status` | ENUM | NOT NULL, DEFAULT 'PENDING' | `PENDING`, `SENT`, `FAILED` |
| `error_message` | TEXT | NULLABLE | Detalle del error si `status = FAILED` |
| `sent_at` | TIMESTAMP | NULLABLE | |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**ENUMs:**
```sql
CREATE TYPE notification_type AS ENUM (
  'PAE_NO_CLAIM',
  'PAE_LATE_CLAIM_CORRECTION',
  'ABSENCE_FIRST_HOUR',
  'DISCIPLINE_RECORD',
  'EARLY_DEPARTURE'
);

CREATE TYPE notification_status AS ENUM ('PENDING', 'SENT', 'FAILED', 'SUPPRESSED');
```

> `email_to` se guarda como snapshot del correo en el momento del envío. Si el acudiente cambia su email después, el log mantiene el correo al que efectivamente se notificó.

---

### `import_jobs`

Estado de los procesos de carga masiva desde Excel. El cliente consulta este registro para saber si su importación terminó y cuántas filas fallaron.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `institution_id` | UUID | NOT NULL, FK → institutions | |
| `type` | ENUM | NOT NULL | `STUDENTS`, `PAE_ENROLLMENT`, `CONVIVENCIA_ARTICLES` |
| `file_url` | VARCHAR(500) | NOT NULL | URL del archivo original en storage |
| `status` | ENUM | NOT NULL, DEFAULT 'PENDING' | `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED` |
| `total_rows` | INTEGER | NULLABLE | Se actualiza al inicio del procesamiento |
| `processed_rows` | INTEGER | NOT NULL, DEFAULT 0 | |
| `error_rows` | INTEGER | NOT NULL, DEFAULT 0 | |
| `result_url` | VARCHAR(500) | NULLABLE | URL del reporte de errores descargable |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |
| `completed_at` | TIMESTAMP | NULLABLE | |

**ENUMs:**
```sql
CREATE TYPE import_job_type AS ENUM ('STUDENTS', 'PAE_ENROLLMENT', 'CONVIVENCIA_ARTICLES');
CREATE TYPE import_job_status AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED');
```

---

### `demo_leads`

Solicitudes de demo enviadas desde el formulario de la landing pública. **Tabla pre-tenant: no lleva `institution_id`** (ver "Decisiones de diseño"). El endpoint que la escribe es público, sin JWT.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `email` | VARCHAR(320) | NOT NULL | Normalizado a minúsculas y sin espacios al guardar |
| `source` | VARCHAR(50) | NOT NULL, DEFAULT 'LANDING_CTA' | Origen del lead, por si se añaden más formularios |
| `notification_status` | ENUM | NOT NULL, DEFAULT 'PENDING' | `PENDING`, `SENT`, `FAILED`, `SUPPRESSED` — reutiliza `notification_status` |
| `notification_error` | TEXT | NULLABLE | Detalle del fallo si `notification_status = FAILED` |
| `notified_at` | TIMESTAMP | NULLABLE | |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**Índices:**
```sql
CREATE INDEX idx_demo_leads_created ON demo_leads (created_at DESC);
CREATE INDEX idx_demo_leads_email_created ON demo_leads (email, created_at DESC);
```

> El lead **se persiste siempre**, aunque el correo de aviso falle. El envío es un efecto secundario asíncrono (job Celery); la fuente de verdad es esta tabla. El segundo índice soporta la supresión de avisos duplicados: si el mismo correo ya solicitó demo en las últimas 24 h, la fila se guarda igual, se marca `SUPPRESSED` y no se encola aviso. `SUPPRESSED` ≠ `PENDING`: el primero es "no se intentó a propósito", el segundo "encolado y sin resolver" — sin esa distinción, una fila atascada por un worker caído sería indistinguible de una supresión deliberada.
>
> No se registra en `notifications_log`: esa tabla exige `institution_id`, `student_id` y `guardian_id` NOT NULL, y un lead no tiene ninguno de los tres. El estado del envío vive en las columnas `notification_*` de esta misma tabla.

---

### `password_reset_otps`

Códigos de un solo uso para el flujo de recuperación de contraseña. Sin `institution_id`: el flujo ocurre **antes** de autenticarse, el usuario se resuelve por su correo (único en `users`) y el tenant se deriva del `user_id`.

| Columna | Tipo | Restricciones | Descripción |
|---|---|---|---|
| `id` | UUID | PK | |
| `user_id` | UUID | NOT NULL, FK → users | |
| `code_hash` | VARCHAR(255) | NOT NULL | bcrypt del código de 6 dígitos. **Nunca en claro** |
| `attempts` | SMALLINT | NOT NULL, DEFAULT 0 | Intentos fallidos; al llegar al máximo el código queda inservible |
| `expires_at` | TIMESTAMP | NOT NULL | |
| `consumed_at` | TIMESTAMP | NULLABLE | Se sella al validar el código |
| `reset_token` | UUID | NULLABLE, UNIQUE | Prueba de OTP validado; habilita el cambio de contraseña |
| `reset_token_expires_at` | TIMESTAMP | NULLABLE | |
| `reset_token_used_at` | TIMESTAMP | NULLABLE | Se sella al cambiar la contraseña |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**Índices:**
```sql
CREATE INDEX idx_password_reset_user  ON password_reset_otps (user_id, created_at);
CREATE INDEX idx_password_reset_token ON password_reset_otps (reset_token);
```

> El código se guarda con **bcrypt**, no con un hash rápido: seis dígitos son un millón de combinaciones y un SHA-256 filtrado se revierte en segundos.
>
> `reset_token` existe para que el tercer paso (cambiar la contraseña) no tenga que fiarse del cliente. Sin él, cualquiera podría llamar al endpoint de cambio con un correo ajeno afirmando haber validado el OTP. El token se emite en el servidor solo tras validar el código y vive pocos minutos.
>
> Pedir un código nuevo caduca los anteriores del mismo usuario: solo el último es válido.

---

## Índices recomendados

Más allá de los índices automáticos de PKs y UNIQUEs, estos índices cubren los queries más frecuentes del sistema:

```sql
-- PAE: listado diario y verificación de doble entrega
CREATE INDEX idx_pae_deliveries_date_institution ON pae_deliveries (institution_id, delivery_date);
CREATE INDEX idx_pae_enrollments_active ON pae_enrollments (institution_id, academic_year) WHERE is_active = TRUE;

-- Asistencia: historial por estudiante y búsqueda por fecha
CREATE INDEX idx_attendance_student_date ON attendance_records (student_id, date);
CREATE INDEX idx_attendance_group_date ON attendance_records (group_id, date);

-- Tokens: validación rápida por token
CREATE INDEX idx_attendance_tokens_token ON attendance_tokens (token);

-- Agendatorio: historial por estudiante
CREATE INDEX idx_discipline_student ON discipline_records (student_id, date);

-- Notificaciones: consulta de estado para reenvíos
CREATE INDEX idx_notifications_status ON notifications_log (institution_id, status, created_at);

-- Estudiantes: búsqueda por documento (flujo PAE alternativo)
CREATE INDEX idx_students_document ON students (institution_id, document_number);
```

---

## Relaciones — Resumen

```
institutions
  ├── grades → groups → class_periods
  ├── groups → user_groups → users
  ├── students
  │     ├── student_groups → groups
  │     ├── guardians
  │     ├── pae_enrollments
  │     ├── pae_deliveries
  │     ├── attendance_records → attendance_tokens → attendance_justifications
  │     ├── discipline_records → discipline_record_articles → convivencia_articles
  │     └── early_departures
  ├── convivencia_articles
  ├── notifications_log
  └── import_jobs
```

---

*Esquema de base de datos — BIGA APP | Versión 1.0 | Mayo 2026*
