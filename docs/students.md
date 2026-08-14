# Módulo Estudiantes — Referencia funcional

Ciclo de vida del estudiante y sus acudientes: alta, matrícula a grado/salón, búsqueda
cross-módulo, foto de identificación y la regla de acudiente principal. Para el modelo de
datos ver `docs/database-schema.md`; para los patrones de arquitectura ver `docs/architecture.md`.
La gestión de grados/salones en sí (crearlos, no matricular en ellos) vive en `docs/admin.md`.

---

## Qué resuelve

Todo módulo del sistema (PAE, Asistencia, Convivencia) necesita identificar a un estudiante
y notificar a su acudiente. Este módulo es la fuente única de esos dos datos:

1. El registro del estudiante (documento, nombres, fecha de nacimiento, foto).
2. Sus acudientes, con exactamente uno marcado como **principal** — el destino de las
   notificaciones automáticas de todo el sistema (PAE, asistencia, convivencia).

La matrícula a grado/salón (`student_groups`) también se documenta acá, aunque
conceptualmente pertenece más a "Académico" (`docs/admin.md`), porque el alta de
estudiante la incluye en el mismo flujo atómico.

---

## Dos caminos para crear un estudiante

### `POST /students` — alta "pelada", cualquier rol autenticado

```json
// request
{ "document_number": "1002345678", "first_name": "Ana", "last_name": "Gómez",
  "birth_date": "2015-03-10", "photo_url": null }
```

Crea solo el `Student`, sin matrícula ni acudientes. Gateado con `get_current_user` sin
restricción de rol — cualquier usuario autenticado puede llamarlo. **Sin consumidor en el
front actualmente** (`StudentsView` usa el camino atómico de abajo desde que existe); sigue
vivo como endpoint simple, no lo elimines sin confirmar que nada externo lo usa.

### `POST /admin/students` — alta completa y atómica, solo ADMIN

```json
// request
{
  "document_number": "1002345678", "first_name": "Ana", "last_name": "Gómez",
  "birth_date": "2015-03-10",
  "group_id": "b3f1...-uuid-o-null",
  "guardians": [
    { "full_name": "Luisa Gómez", "relationship": "MADRE", "email": "luisa@example.com",
      "phone": "3001234567", "is_primary": true }
  ]
}
```

Crea `Student` + matrícula opcional en `student_groups` + uno o más `Guardian`, todo en una
sola transacción (`AdminManagementService.create_student_full`) — si algo falla a mitad de
camino, no queda un estudiante huérfano (rollback automático de `get_db()`).

Reglas de validación:
- `group_id` es opcional; si se pasa, debe existir en la institución (`404` si no).
- `student_groups` **no tiene columna `grade_id`** — el Grado es puramente un filtro de UI
  para acotar el `<select>` de Salón en el formulario, nunca llega al payload. La matrícula
  se guarda con `academic_year` del **año actual**, calculado en el servidor — no es
  elegible desde el formulario.
- Al menos un `guardian` es obligatorio, y **exactamente uno** debe tener `is_primary=true`
  — validado en `AdminStudentCreate` con un `model_validator` de Pydantic (regla de forma,
  sin dependencia de BD, por eso no se revalida en el service). Reforzado además por el
  índice parcial único `one_primary_per_student` en la tabla `guardians` (el respaldo a
  nivel BD, no el mecanismo principal — ver sección "Acudientes" abajo).
- Documento duplicado → `409`.

La foto **no** entra en esta transacción: sigue siendo un paso aparte y no-fatal después de
crear, vía `POST /students/{id}/photo`. Si falla, el estudiante ya quedó creado — el front
solo muestra un toast de error.

---

## Endpoints

### `GET /students`
"Mis estudiantes", acotado por rol:

| Rol | Qué ve |
|---|---|
| `TEACHER` / `PAE_OPERATOR` | Solo los estudiantes de los salones que tiene asignados en `user_groups` (por asignación docente-grupo, **no** por horario — da igual la hora de la clase) |
| `ADMIN` | La institución entera |

El recorte vive en `StudentService.list_students`, no en el front — cualquiera puede llamar
al endpoint a mano.

`grade_id`/`group_id` (opcionales) **solo filtran el listado del ADMIN** — el de
docente/operador PAE ya viene acotado a sus propios salones y los ignora. Implementado con
`LEFT JOIN` a `student_groups`/`groups`/`grades` en `StudentRepository.list_by_institution`
(no `INNER JOIN`: un estudiante sin matrícula activa debe seguir apareciendo, solo que sin
`grade_name`/`group_name`).

```json
[{ "id": "…", "document_number": "1010100001", "first_name": "Mariana", "last_name": "Gómez",
   "birth_date": "2014-03-12", "photo_url": "https://…", "is_active": true, "created_at": "…",
   "grade_name": "Once", "group_name": "A" }]
```

No confundir con `GET /students/search` (abajo), que **sigue alcanzando a toda la
institución** a propósito: convivencia debe poder registrar a cualquier estudiante, sea o
no de sus salones.

### `GET /students/search`
Búsqueda cross-módulo, usada por el componente `StudentSearch` (Convivencia, Historial) y
por Salidas tempranas. `q` es **opcional** — con `grade_id`/`group_id` se navega por
grado/salón sin escribir nombre. Insensible a acentos vía la extensión `unaccent` de
Postgres (`Lopez` encuentra `López`; migración `d4a2c7e91b05`). Devuelve como máximo **20
resultados** (`StudentRepository.search`, `limit=20` fijo, no configurable) — pensado para
autocompletar, **no** para listar la institución entera (para eso está `GET
/students?grade_id=&group_id=` desde el admin, sin tope).

```json
[{ "id": "…", "full_name": "Mariana Gómez", "document_number": "1010100001",
   "photo_url": "https://…", "group_name": "A", "grade_name": "Once" }]
```

Los selectores de grado/salón (tanto acá como en el filtro de `GET /students`) se llenan
con `GET /agendatorio/grades` y `GET /agendatorio/groups` — accesibles a **staff**
(cualquier rol autenticado), no solo admin.

### `POST /students/{id}/photo`
Sube la foto del estudiante a MinIO (multipart, igual que la firma del agendatorio).
`students.photo_url` guarda la **key**, no la URL. Todo servicio que la devuelve la
presigna con `resolve_photo_url(storage, key)` de `app/core/photos.py` (deja pasar URLs
`http(s)://` externas por compatibilidad). Por eso `PAEService`/`AttendanceService`/
`StudentService` reciben el `S3StorageAdapter` inyectado.

**Para exponer `photo_url` en un endpoint de lista/detalle nuevo:** (1) agregar el campo al
Row/dataclass del repo y al schema de respuesta, (2) `select(Student.photo_url)` en la
query + mapearlo, (3) presignar con `resolve_photo_url(self.storage, key)` en el service
(que debe recibir `S3StorageAdapter` vía `Depends(get_storage_adapter)`). Sin migración —
solo lee `students.photo_url`. El front renderiza `<StudentPhoto src={x.photo_url}>` con
fallback a avatar de iniciales.

---

## Acudientes (`guardians`)

No existe un CRUD independiente de acudientes — hoy solo se crean como parte de `POST
/admin/students` (`GuardianRepository.create`). Campos: `full_name`, `relationship`
(`PADRE`/`MADRE`/`ACUDIENTE`/`OTRO`), `email` (`EmailStr`, valida formato — es el destino de
las notificaciones automáticas de PAE/asistencia/convivencia), `phone` (opcional),
`is_primary`.

**Solo puede haber un acudiente principal por estudiante** — `guardians` tiene un índice
único parcial:
```sql
CREATE UNIQUE INDEX one_primary_per_student ON guardians (student_id) WHERE is_primary = TRUE;
```

`GuardianRepository.get_primary(student_id)` es el único punto de lectura que usan los
Notifiers de todo el sistema para saber a quién avisar.

---

## Frontend

`StudentsView` (`web/src/pages/PAEDashboard.jsx`, vive ahí por historia) la usa **solo**
`AdminDashboard`. No confundir con `TeacherStudentsView`, que es lo que monta `PAEDashboard`
para el operador PAE: el operador PAE es un docente con funciones extra, así que su módulo
de Aula es literalmente el del docente, sin alta de estudiante ni matrícula.

El modal de alta (`.dash__modal--wide`, más ancho que el resto de modales de la app, con
scroll interno) tiene 3 secciones:

1. **Datos personales** — documento, nombres, apellidos, fecha de nacimiento, foto (con
   preview de miniatura vía `URL.createObjectURL`, revocado al cambiar/quitar/cerrar).
2. **Matrícula** (opcional) — Grado y Salón. Grado es puramente un filtro de UI (no viaja al
   backend); Salón es obligatorio si se elige Grado.
3. **Acudientes** — lista repetible (agregar/quitar, mínimo 1), radio "Primario" mutuamente
   excluyente (solo visible con 2+ acudientes; con 1 solo, es primario por default sin
   selector visible).

El grado/salón del modal (`form.gradeId`/`form.group_id`) es estado **separado** del filtro
de la tabla de abajo (`gradeId`/`groupId`, nivel de componente) — ambos reusan el mismo
fetch de `adminService.listGrades`/`listGroups`, sin duplicarlo.

Tras crear con éxito, se recarga la tabla completa (`load()`) en vez de un push optimista:
la respuesta de `POST /admin/students` no trae `grade_name`/`group_name`.

Servicios: `web/src/services/students.js`, `web/src/services/admin.js`.

---

## Probarlo

```bash
docker compose up -d
docker compose exec api alembic upgrade head
docker compose exec -T postgres psql -U biga -d biga < scripts/seed_dev_users.sql
```

Credenciales de los usuarios demo (incluido el admin) en `docs/databaseDev.md`.
