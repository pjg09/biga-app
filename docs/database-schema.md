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
| Identificación PAE | `identification_method` registra si la entrega fue por documento o reconocimiento facial. El valor `FACIAL` queda reservado para fase 2. |

---

## Convenciones

- Todos los IDs son `UUID` generados en la aplicación, no `SERIAL`.
- `created_at` se registra en todas las tablas. Columnas de auditoría adicionales (`updated_at`) se agregan según necesidad real, no preventivamente.
- Los ENUMs se definen como tipos PostgreSQL nativos.
- Los campos `institution_id` en tablas hijas son denormalizados intencionalmente para evitar joins costosos en queries frecuentes.

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
| `pae_delivery_end_time` | TIME | NOT NULL | Hora de cierre del PAE. El job de notificación se programa contra este valor. |
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
| `role` | ENUM | NOT NULL | `TEACHER`, `PAE_OPERATOR` |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT TRUE | |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**ENUMs:**
```sql
CREATE TYPE user_role AS ENUM ('TEACHER', 'PAE_OPERATOR');
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
| `photo_url` | VARCHAR(500) | NULLABLE | URL en object storage. Se usa para corroborar identidad en el flujo por documento y como referencia para reconocimiento facial (fase 2). |
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
| `enrolled_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**Restricciones adicionales:**
```sql
UNIQUE (student_id, academic_year)
```

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
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**ENUMs:**
```sql
CREATE TYPE pae_identification_method AS ENUM ('DOCUMENT', 'FACIAL');
```

**Restricciones adicionales:**
```sql
UNIQUE (student_id, delivery_date)
```

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
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

**ENUMs:**
```sql
CREATE TYPE attendance_status AS ENUM ('PRESENT', 'ABSENT', 'LATE', 'JUSTIFIED');
```

**Restricciones adicionales:**
```sql
UNIQUE (student_id, class_period_id, date)
```

**Trigger de notificación:** se activa cuando `status = ABSENT` y el `class_period` tiene `period_order = 1` para el `day_of_week` correspondiente a `date`.

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
| `submitted_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | |

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
| `type` | ENUM | NOT NULL | `PAE_NO_CLAIM`, `ABSENCE_FIRST_HOUR`, `DISCIPLINE_RECORD`, `EARLY_DEPARTURE` |
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
  'ABSENCE_FIRST_HOUR',
  'DISCIPLINE_RECORD',
  'EARLY_DEPARTURE'
);

CREATE TYPE notification_status AS ENUM ('PENDING', 'SENT', 'FAILED');
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
