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

`AdminStudentCreate` también acepta `is_pae_enrolled: bool = false` — si viene en `true`, la
misma transacción inscribe al estudiante en el PAE del año vigente (calcula
`enrollment_hash` igual que `PAEService.enroll_student`, ver `docs/pae.md`). Es la única
forma de inscribir al PAE desde el alta; el flujo viejo de una columna "PAE" separada en la
tabla con botón "Inscribir" se retiró — ahora es un switch dentro de este mismo formulario
(y del de edición, abajo).

### `GET /admin/students/{id}` / `PUT /admin/students/{id}` — detalle y edición, solo ADMIN

`GET` devuelve la ficha completa para la consola de admin: los mismos campos que la lista
más `grade_id`/`group_id` **en crudo** (no solo los nombres) y `guardians[].id` — el
formulario de edición los necesita para preseleccionar `<select>` y para que `PUT` sepa qué
acudiente es cuál. También trae `is_pae_enrolled` (`true` si existe una fila en
`pae_enrollments` para el año vigente con `is_active=true`).

```json
{ "id": "…", "document_number": "…", "first_name": "…", "last_name": "…", "birth_date": "…",
  "photo_url": "https://…", "is_active": true,
  "grade_id": "…", "grade_name": "Once", "group_id": "…", "group_name": "A",
  "is_pae_enrolled": true,
  "guardians": [{ "id": "…", "full_name": "…", "relationship": "MADRE", "email": "…",
                  "phone": null, "is_primary": true }] }
```

`PUT` (`AdminStudentUpdate`) es la contraparte de `POST /admin/students`, misma transacción
atómica (`AdminManagementService.update_student_full`), mismas reglas de validación
(documento único, exactamente un acudiente primario, `group_id` debe existir). Diferencias
por ser una edición y no un alta:

- **Matrícula**: si ya existe una fila en `student_groups` para el año vigente, se actualiza
  su `group_id` in-place; si no existe y se manda `group_id`, se crea. Si se manda
  `group_id: null` y había una matrícula activa, se pone `is_active=false` (no se borra la
  fila — mismo patrón de "ocultar sin borrar" del resto del sistema).
- **Acudientes, reconciliados por `id`**: cada item de `guardians[]` con `id` existente se
  actualiza in-place; sin `id`, se crea. Un acudiente que existía pero no viene en el payload
  se intenta borrar — **excepto si tiene notificaciones históricas** (`notifications_log.
  guardian_id` es FK `NOT NULL` sin `ON DELETE`): en ese caso el endpoint responde `409` con
  el nombre del acudiente, y el borrado nunca se intenta (la verificación es previa —
  `GuardianRepository.has_notifications` — porque un `DELETE` que falla a mitad de la
  transacción deja la sesión async inutilizable para el resto del request).
- **`is_pae_enrolled`**: alterna la inscripción PAE del año vigente.
  - `true` sin inscripción previa → crea una (igual que en el alta).
  - `true` con una inscripción existente pero `is_active=false` → la reactiva (pone
    `is_active=true` en la misma fila; **no** crea una nueva — `UNIQUE(student_id,
    academic_year)` lo impediría).
  - `false` con inscripción activa → la desactiva (`is_active=false`).
  - En ningún caso se tocan `student_id`/`institution_id`/`academic_year`/`enrolled_at`/
    `enrollment_hash` — esos son de solo lectura tras crearse, es la regla crítica del PAE
    (`docs/pae.md`). `is_active` es la única columna de estado, existía en el schema desde
    el principio pero no tenía ningún endpoint que la escribiera hasta ahora.

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
docente/operador PAE ya viene acotado a sus propios salones y los ignora (el filtro de
grado/salón/materia de "Mis estudiantes" se resuelve en el front sobre la lista ya
acotada, ver más abajo). Implementado con `LEFT JOIN` a `student_groups`/`groups`/`grades`
en `StudentRepository.list_by_institution` (no `INNER JOIN`: un estudiante sin matrícula
activa debe seguir apareciendo, solo que sin `grade_name`/`group_name`).

```json
[{ "id": "…", "document_number": "1010100001", "first_name": "Mariana", "last_name": "Gómez",
   "birth_date": "2014-03-12", "photo_url": "https://…", "is_active": true, "created_at": "…",
   "grade_name": "Once", "group_name": "A" }]
```

El listado de docente/operador PAE (`StudentRepository.list_for_teacher`) también trae
`grade_name`/`group_name`, más `subject`: el nombre de la materia (catálogo `subjects`, vía
`user_groups.subject_id` — ver `docs/database-schema.md` y `docs/schedule.md`) que **ese**
docente dicta en **ese** salón. `outerjoin` a `subjects`: `subject_id` es nullable (una
asignación docente-salón puede no tener materia cargada), y el estudiante debe seguir
apareciendo en el listado aunque `subject` salga `null`. A diferencia del admin, el join
a `grades`/`groups` acá es `INNER` (no `LEFT`): el listado ya viene acotado a salones con
asignación docente-grupo, así que grado/salón siempre existen.

No confundir con `GET /students/search` (abajo), que **sigue alcanzando a toda la
institución** a propósito: convivencia debe poder registrar a cualquier estudiante, sea o
no de sus salones.

### `GET /students/{id}` — ficha de detalle (solo `TEACHER`/`PAE_OPERATOR`)
Ficha completa de un estudiante del módulo de Aula: los mismos campos de `GET /students`
más `guardians` (todos los acudientes del estudiante, principal primero — `is_primary`
marca cuál). Mismo recorte que el listado: 404 si el estudiante no está en un salón
asignado a este usuario (`StudentRepository.get_for_teacher`), 403 si el rol es `ADMIN` —
no es un endpoint de gestión, no expone la institución entera.

Declarado **después** de `GET /students/search` en `routers/students.py` a propósito:
Starlette resuelve rutas por orden de registro, no por especificidad — si `/{student_id}`
fuera el primer `GET` de un solo segmento, `/students/search` haría match ahí tratando
"search" como un UUID inválido (422) y nunca llegaría a `search_students`.

```json
{ "id": "…", "document_number": "1010100001", "first_name": "Mariana", "last_name": "Gómez",
  "birth_date": "2014-03-12", "photo_url": "https://…", "is_active": true, "created_at": "…",
  "grade_name": "Once", "group_name": "A", "subject": "Matemáticas",
  "guardians": [{ "id": "…", "full_name": "…", "relationship": "MADRE", "email": "…",
                  "phone": "…", "is_primary": true }] }
```

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

El modal de alta/edición (`.dash__modal--wide`, más ancho que el resto de modales de la app,
con scroll interno) tiene 4 secciones — el mismo formulario sirve para las dos cosas,
`editingId` (`null` = alta) decide el título, el texto del botón y si se llama
`createStudentFull`/`updateStudentFull`:

1. **Datos personales** — documento, nombres, apellidos, fecha de nacimiento, foto (con
   preview de miniatura vía `URL.createObjectURL`, revocado al cambiar/quitar/cerrar).
2. **Matrícula** (opcional) — Grado y Salón. Grado es puramente un filtro de UI (no viaja al
   backend); Salón es obligatorio si se elige Grado.
3. **PAE** — switch "Inscrito en el PAE del año vigente" (`.dash__switch`, componente CSS
   reusable en `dashboard.css`). Reemplaza al viejo botón "Inscribir en PAE" de la tabla: ya
   no hay columna "PAE" en el listado, la inscripción se marca desde acá tanto al crear como
   al editar.
4. **Acudientes** — lista repetible (agregar/quitar, mínimo 1), radio "Primario" mutuamente
   excluyente (solo visible con 2+ acudientes; con 1 solo, es primario por default sin
   selector visible). Al editar, cada fila carga con su `id` (oculto, viaja en el estado del
   form); al crear, `id` es siempre `null`.

El grado/salón del modal (`form.gradeId`/`form.group_id`) es estado **separado** del filtro
de la tabla de abajo (`gradeId`/`groupId`, nivel de componente) — ambos reusan el mismo
fetch de `adminService.listGrades`/`listGroups`, sin duplicarlo.

Tras crear/editar con éxito, se recarga la tabla completa (`load()`) en vez de un push
optimista: la respuesta no trae `grade_name`/`group_name`.

### Ficha de detalle

Cada fila de la tabla es clicable (ícono "ver ficha" en la primera columna, oculto en
móvil — mismo patrón que la ficha de "Mis estudiantes" del docente/PAE, ver
`TeacherStudentsView` en `web/src/pages/TeacherDashboard.jsx` y reusa sus clases CSS
`.stu-detail__*`). Al hacer click se pide `GET /admin/students/{id}` y se muestra foto
(con zoom), nombre, documento, estado, grado, salón, badge de estado PAE y la lista de
acudientes. Un botón "Editar" abre el modal de arriba precargado con `AdminGuardianUpdate[]`
(guardando los `id` para el reconcile) y `is_pae_enrolled` en el estado actual.

Servicios: `web/src/services/students.js`, `web/src/services/admin.js`.

---

## Probarlo

```bash
docker compose up -d
docker compose exec api alembic upgrade head
docker compose exec -T postgres psql -U biga -d biga < scripts/seed_dev_users.sql
```

**Baja de un estudiante**: el botón «Eliminar» del formulario de edición es una **baja lógica**
(`is_active = false`), nunca un borrado — el histórico de convivencia, asistencia, justificaciones y
PAE sigue apuntando a su `student_id`. Basta con apagar esa columna para que desaparezca de
listados, búsqueda y rosters, porque todas esas consultas ya la filtran. Detalle y reactivación
(`include_inactive`) en `docs/admin.md`.

Credenciales de los usuarios demo (incluido el admin) en `docs/runbook.md` §5.

---

## Foto del estudiante

Foto del estudiante: se **sube a MinIO** vía `POST /students/{id}/photo` (multipart), igual que la firma del agendatorio. `students.photo_url` guarda la **key** (no la URL); todo servicio que la devuelve la presigna con `resolve_photo_url(storage, ...)` de `app/core/photos.py` (deja pasar URLs `http(s)://` externas por compat). Por eso `PAEService`/`AttendanceService`/`StudentService` reciben el `S3StorageAdapter` inyectado.

Para exponer `photo_url` en un endpoint de **lista/detalle nuevo** (de cualquier módulo, no solo estudiantes): (1) agregar el campo al Row/dataclass del repo y al schema de respuesta, (2) `select(Student.photo_url)` en la query + mapearlo, (3) presignar con `resolve_photo_url(self.storage, key)` en el service (que debe recibir `S3StorageAdapter` vía `Depends(get_storage_adapter)`). Sin migración (solo lee `students.photo_url`). El front renderiza `<StudentPhoto src={x.photo_url}>` con fallback a avatar de iniciales.
