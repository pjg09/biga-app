# Módulo Agendatorio (Convivencia) — Referencia funcional

> El libro de convivencia digital: registro disciplinario con firma del estudiante,
> notificación al acudiente, y el historial del docente con notas de seguimiento.
> Modelo de datos en `docs/database-schema.md`.

---

## Qué resuelve

- **Registro de convivencia**: el docente ubica al estudiante, selecciona los
  artículos del manual que incumplió, describe el hecho y captura la **firma del
  estudiante** (trazo en canvas → PNG a MinIO). Al guardar, se notifica al acudiente.
- **Historial del docente**: ver los registros que él creó, entrar al detalle,
  **agregar notas de seguimiento** (append-only) y **ocultar** un registro de su panel
  (sin borrarlo).

Opera personal de aula (autenticado, `get_current_user`). Como el operador PAE es
docente con funciones extra, la vista vive en `TeacherDashboard` y se reutiliza en
`PAEDashboard` (ver `docs/frontend.md`).

---

## Regla de integridad: el registro firmado es inmutable

El registro (`discipline_records`: artículos, observaciones, firma) **no se modifica
ni se borra vía API** — no hay `PUT`/`DELETE` de registros. El seguimiento posterior
se agrega como **notas append-only** (`discipline_record_notes`, con autor y fecha).
Ocultar del panel solo setea `archived_at` (NULL = visible), no borra nada — el dato
queda íntegro para auditoría.

> Esto es distinto de la cadena de doble hash del **PAE** (`docs/pae.md`): convivencia
> no firma con HMAC, su garantía es "no hay endpoints de mutación + notas inmutables".

---

## Flujo de registro paso a paso

```
1. Docente ubica al estudiante      GET /students/search?q=&grade_id=&group_id=
   (selectores grado/salón)         (grados/salones: GET /agendatorio/grades y /groups)

2. Carga el manual y elige artículos GET /agendatorio/articles
   (filtro por severidad + buscador por nombre: client-side)

3. Observaciones + firma en canvas   → PNG

4. Guarda                            POST /agendatorio/records  (multipart: data JSON + signature PNG)
   → sube la firma a MinIO (signatures/{institution}/{record}.png)
   → encola notify_discipline_record (correo al acudiente)
```

### Búsqueda de estudiante (grado / salón / nombre)

`GET /students/search` acepta `q` (**opcional**), `grade_id`, `group_id`. Con
grade/group se navega por grado/salón sin escribir. Es **insensible a acentos**
(extensión `unaccent`: `Lopez` encuentra `López`). Los selectores se llenan con
`GET /agendatorio/grades` y `GET /agendatorio/groups` (accesibles a **staff**). El
front usa el componente compartido `StudentSearch`.

---

## Historial del docente

- `GET /agendatorio/my-records` — solo los registros que **ese** docente creó
  (`recorded_by_user_id == current_user.id`). Params: `student_id` (filtrar por
  estudiante), `include_archived` (mostrar ocultos). Devuelve nombre del alumno,
  foto (`photo_url` presignado), grado/salón, artículos, conteo de notas y flag `archived`.
- `GET /agendatorio/records/{id}` — detalle enriquecido: alumno, foto (`photo_url`
  presignado), grado/salón, quién lo registró, artículos, firma (URL presignada),
  **notas** y `archived`.
- `POST /agendatorio/records/{id}/notes` — agrega una nota (append-only). Solo el dueño.
- `POST /agendatorio/records/{id}/archive` · `/unarchive` — oculta/muestra en el panel
  (setea/limpia `archived_at`). Solo el dueño; devuelve `204`.

---

## Endpoints

### Catálogo (staff — selectores de búsqueda)

| Método y ruta | Descripción |
|---|---|
| `GET /agendatorio/grades` | Grados de la institución |
| `GET /agendatorio/groups` | Grupos (con `grade_id`/`grade_name` para acotar por grado) |

### Artículos del manual

| Método y ruta | Descripción |
|---|---|
| `GET /agendatorio/articles` | Lista los artículos activos |
| `POST /agendatorio/articles` | Crea un artículo (`code`, `title`, `description`, `severity`) |
| `PATCH /agendatorio/articles/{id}` | Edita un artículo |
| `DELETE /agendatorio/articles/{id}` | Desactiva (soft delete, `is_active=false`) → `204` |

`severity` es el enum `article_severity`: `LEVE` · `MODERADA` · `GRAVE`.

### Registros disciplinarios

| Método y ruta | Descripción |
|---|---|
| `POST /agendatorio/records` | Crea un registro. **Multipart**: `data` (JSON `{student_id, article_ids[], observations, date}`) + `signature` (PNG) |
| `GET /agendatorio/records` | Registros de la institución (filtros: `student_id`, `article_id`, `date_from`, `date_to`, `skip`, `limit`) |
| `GET /agendatorio/my-records` | Registros del docente actual (`student_id`, `include_archived`) |
| `GET /agendatorio/records/{id}` | Detalle enriquecido (artículos, notas, firma presignada, archived) |
| `POST /agendatorio/records/{id}/notes` | Agrega nota (`{note}`) → `201` |
| `POST /agendatorio/records/{id}/archive` · `/unarchive` | Oculta / muestra en el panel → `204` |

---

## Notificación

`notify_discipline_record(record_id, institution_id)` se encola al guardar el registro
(job Celery, mismo patrón que asistencia: `run_db_job` + `DisciplineRecordNotifier` +
`EmailAdapter`). Notifica al acudiente primario que hay un nuevo registro. Un fallo de
correo se registra en `notifications_log` como `FAILED` y no relanza.

---

## Frontend

En `web/src/pages/TeacherDashboard.jsx` (reutilizado en `PAEDashboard`):

- **Convivencia** (`ConvivenciaView`) — `StudentSearch` (grado/salón/nombre) + selector
  de artículos con **filtro por severidad y buscador** (client-side) + observaciones +
  **firma en canvas**. Guarda vía `agendatorioService.createRecord` (multipart).
- **Historial** (`HistorialView`) — lista los registros propios (con `StudentSearch`
  como filtro y toggle "mostrar ocultos"); al abrir uno, `RecordDetail` muestra
  artículos, observaciones, firma, notas, permite agregar nota y ocultar/mostrar.

Servicio: `web/src/services/agendatorio.js`.

---

*Referencia funcional — Agendatorio / Convivencia | BIGA*
