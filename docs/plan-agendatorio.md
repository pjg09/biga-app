# Plan de implementación — Módulo Agendatorio

> Documento de trabajo. Marcar cada ítem con `[x]` al completarlo.

---

## Contexto

El agendatorio es el libro de convivencia digital. Reemplaza el registro en papel donde los docentes reportan faltas disciplinarias de estudiantes. Cada registro incluye los artículos del manual de convivencia infringidos, observaciones libres y la firma digital del estudiante capturada en pantalla táctil.

**Tablas involucradas** (ya migradas):
- `convivencia_articles` — catálogo de artículos del manual por institución
- `discipline_records` — el registro propiamente dicho
- `discipline_record_articles` — M2M entre registros y artículos

**Archivos ya existentes** que se reutilizan sin modificar:
- `app/models/agendatorio.py` — modelos ORM `ConvivenciaArticle`, `DisciplineRecord`, `DisciplineRecordArticle`
- `app/adapters/storage/` — `StorageAdapter` Protocol + `S3StorageAdapter`
- `app/core/dependencies.py` — `get_current_user`
- `app/jobs/departure_jobs.py` — referencia del patrón de jobs

---

## Endpoints a implementar

```
# Manual de convivencia
GET    /agendatorio/articles                    Lista artículos activos (scope: institución)
POST   /agendatorio/articles                    Crea artículo
PATCH  /agendatorio/articles/{article_id}       Actualiza artículo (incluye `code` e `is_active` — reactivación)
DELETE /agendatorio/articles/{article_id}       Desactiva artículo (soft delete)

# Búsqueda de estudiantes (compartido con PAE)
GET    /students/search?q=&group_id=&grade_id=  Busca estudiantes por nombre o documento

# Registros disciplinarios
POST   /agendatorio/records                     Crea registro (multipart: JSON + archivo PNG)
GET    /agendatorio/records                     Lista registros (paginado). Filtros opcionales: student_id, article_id, date_from, date_to
GET    /agendatorio/records/{record_id}         Detalle de un registro con artículos
```

---

## Decisiones de diseño

### Firma del estudiante
- El frontend envía un `multipart/form-data` con dos partes: `data` (JSON con los campos del registro) y `signature` (archivo PNG capturado del canvas).
- El Service sube el PNG a storage **antes** de escribir en BD. Si storage falla, no se crea el registro. Si BD falla después del upload, el archivo queda huérfano en storage — aceptable para el MVP.
- El key en storage sigue el patrón: `signatures/{institution_id}/{record_id}.png`

### Validación de artículos
- El Service valida que todos los `article_id` del request pertenezcan a la misma institución del usuario autenticado y estén activos. Un artículo de otra institución en la lista es `400`, no `403` — no revelar información de tenants.
- Se requiere al menos un artículo. Un registro sin artículo infringido no tiene sentido.

### Encolado del job de notificación
- El job `notify_discipline_record` se encola con `.delay(record_id)` **después** del commit implícito que hace `get_db()`. Si se encola antes, el worker puede intentar leer el registro antes de que sea visible.

### Estudiante sin acudiente primario
- Por regla de negocio, todo estudiante debe tener exactamente un acudiente primario (`is_primary = True`). Este invariante se enforza en la capa de Service al crear/modificar estudiantes — ver `docs/implementation-notes.md`.
- En `create_record`, si por alguna razón no existe acudiente primario (estado inválido), se registra un error en el log y **no** se encola el job. El registro disciplinario se crea igual — es un estado inesperado del sistema, no un error del docente.

### `student_repository.py` es compartido
- Se crea como módulo independiente (no "del agendatorio"). PAE lo va a reutilizar. Contiene: `search`, `get_by_id`, `get_by_document`.

### Endpoint de búsqueda de estudiantes — router propio
- `GET /students/search` vive en `app/routers/students.py` (no dentro de `agendatorio.py`).
- Razón: PAE necesita el mismo endpoint. Colocarlo en el router de agendatorio obligaría a duplicarlo o moverlo cuando llegue PAE.

### Paginación
- Offset-based con parámetros `skip: int = 0` y `limit: int = 20` (máximo 100). Simple para el MVP.

### Edición y reactivación de artículos
- `PATCH /agendatorio/articles/{article_id}` permite modificar `code`, `title`, `description`, `severity` e `is_active`. No hay endpoint dedicado de reactivación: `is_active: true` por este mismo PATCH reactiva un artículo desactivado.
- Cambiar `code` a uno ya usado por otro artículo de la institución (activo o inactivo) devuelve `409`. La unicidad de `code` aplica también a artículos inactivos (ya validado en `create_article` vía `get_article_by_code`), así que reactivar un artículo no puede generar un código duplicado.

### Listado de registros — filtros
- `student_id` ahora es opcional. Sin él, `GET /agendatorio/records` devuelve los registros de toda la institución (vista de coordinación), siempre filtrados por `institution_id`.
- Filtros adicionales opcionales: `article_id` (registros que incluyen ese artículo), `date_from`/`date_to` (rango de fechas, inclusive). `date_from > date_to` es `400`.
- Si se envía `student_id`, se sigue validando que el estudiante exista en la institución (`404` si no).

---

## Checklist de implementación

### Fase 1 — Schemas Pydantic ✅
- [x] `app/schemas/agendatorio.py`
- [x] `app/schemas/students.py`

### Fase 2 — Repositories ✅
- [x] `app/repositories/student_repository.py` — `search`, `get_by_id`
- [x] `app/repositories/guardian_repository.py` — `get_primary`
- [x] `app/repositories/agendatorio_repository.py` — artículos + registros; `signature_url` almacena la key de storage (no la URL presignada)

### Fase 3 — Dependency de Storage ✅
- [x] `get_storage_adapter()` en `app/core/dependencies.py`

### Fase 4 — Service ✅
- [x] `app/services/agendatorio_service.py` — flujo completo incluyendo validación de artículos, upload a storage, encolado del job y manejo del caso de acudiente ausente

### Fase 5 — Job de notificación ✅
- [x] `app/jobs/agendatorio_jobs.py` — stub (`pass`)
- [x] Implementar `notify_discipline_record`:
  - [x] Sesión de BD propia (`AsyncSessionLocal`, no `get_db()`)
  - [x] Cargar registro + estudiante + acudiente primario
  - [x] Enviar email via `EmailAdapter`
  - [x] Escribir en `notifications_log` (`SENT` o `FAILED`) — `app/repositories/notification_repository.py` (nuevo)
  - [x] En excepción: `status = FAILED`, no relanzar

### Fase 6 — Router ✅
- [x] `app/routers/agendatorio.py` — 7 endpoints
- [x] `app/routers/students.py` — `GET /students/search` en router propio
- [x] Registrado en `app/main.py`

### Fase 7 — Tests ⏳ PENDIENTE
- [x] `tests/unit/test_agendatorio_service.py`
  - [x] `create_record` falla si `article_ids` está vacío (requirió agregar el chequeo explícito en el Service — antes solo lo cubría `Field(min_length=1)` del schema)
  - [x] `create_record` falla si algún `article_id` no pertenece a la institución
  - [x] `create_record` falla si algún `article_id` está inactivo
  - [x] `create_record` exitoso encola el job cuando hay acudiente primario
  - [x] `create_record` exitoso NO encola job cuando no hay acudiente primario
  - [x] `create_record` no persiste nada si `storage.upload` lanza excepción
  - [x] `deactivate_article` lanza 404 si el artículo no existe en la institución
- [x] `tests/unit/test_agendatorio_jobs.py` (no estaba en el checklist original, agregado por la lógica de ramas de `notify_discipline_record`)
- [ ] `tests/unit/test_agendatorio_repository.py`
  - [ ] `create_record` inserta el registro y las filas M2M correctamente
  - [ ] `list_records` filtra por `institution_id` y `student_id`
  - [ ] `list_articles` no devuelve artículos inactivos
  - **Pendiente de decisión**: estos tests requieren una sesión real contra Postgres (no se pueden mockear con sentido). No existe infraestructura de fixtures de BD para tests todavía — ver `tests/integration/` (vacío). Definir antes de implementar.

---

## Orden sugerido de ejecución

1. Schemas → validan el contrato antes de tocar BD
2. `student_repository.py` + `guardian_repository.py` → dependencias del service
3. `agendatorio_repository.py`
4. Dependency de storage en `dependencies.py`
5. `agendatorio_service.py`
6. `agendatorio_jobs.py`
7. `agendatorio_router.py` + registro en `main.py`
8. Tests

---

## Riesgos y puntos de atención

| Riesgo | Mitigación |
|--------|-----------|
| El job lee el registro antes del commit | Encolar siempre después del `await session.flush()` o confiar en el auto-commit de `get_db()` al salir del scope |
| Archivo de firma huérfano si falla el commit | Aceptado en MVP. En fase 2 se puede implementar cleanup periódico |
| `article_ids` de otra institución expone datos | Validar en service con query filtrado por `institution_id` — nunca asumir que el ID es válido por existir |
| `student_repository.py` modificado por PAE en paralelo | Coordinar: los métodos `get_by_id` y `search` son de solo lectura. PAE puede agregar métodos pero no modificar los existentes |
| Estudiante sin acudiente primario en `create_record` | Estado inválido por regla de negocio. Loguear, omitir notificación, no bloquear el registro |

---

*Plan — Módulo Agendatorio | Mayo 2026*
