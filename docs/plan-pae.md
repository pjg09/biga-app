# Plan de implementación — Módulo PAE

> ⚠️ **Documento histórico y desactualizado.** El módulo PAE ya está implementado,
> pero con un diseño distinto al de este plan (request por `student_id` en vez de
> `document_number`, cadena de doble hash de integridad, endpoints
> `/pae/students/today`, `/pae/enrollments`, `/pae/report/weekly`, `/pae/audit`).
> La documentación funcional vigente está en **`docs/pae.md`**. Este archivo se
> conserva solo como referencia del plan original.

---

## Contexto

El módulo PAE registra la entrega diaria del Programa de Alimentación Escolar. El docente o operador PAE identifica al estudiante por número de documento (MVP) y registra la entrega. Al cierre del horario PAE, un job Celery notifica a los acudientes de estudiantes inscritos que no recibieron su almuerzo ese día.

**Tablas involucradas** (ya migradas):
- `pae_enrollments` — inscripción de un estudiante al PAE por año académico
- `pae_deliveries` — registro de cada entrega realizada

**Archivos ya existentes que se reutilizan sin modificar:**
- `app/models/pae.py` — `PAEEnrollment`, `PAEDelivery`
- `app/models/enums.py` — `PAEIdentificationMethod` (`DOCUMENT`, `FACIAL`)
- `app/repositories/student_repository.py` — `get_by_id`, `search` (agregar `get_by_document`)
- `app/repositories/guardian_repository.py` — `get_primary`
- `app/routers/students.py` — `GET /students/search` ya registrado en `main.py`, no tocar
- `app/core/dependencies.py` — `get_current_user`

---

## Endpoints a implementar

```
POST   /pae/deliveries                   Registra una entrega PAE
GET    /pae/deliveries?date=&group_id=   Lista entregas del día (para marcar presentes)
GET    /pae/enrollments?group_id=        Lista estudiantes inscritos en PAE de un grupo
```

---

## Decisiones de diseño

### Patrón Strategy para identificación

El módulo usa el patrón Strategy definido en `docs/architecture.md`. En MVP solo existe `DocumentSearchStrategy`. La estructura debe permitir agregar `FacialRecognitionStrategy` en fase 2 sin modificar `PAEService`.

```python
from typing import Protocol
from app.models.student import Student

class PAEIdentificationStrategy(Protocol):
    async def identify(self, input_data: dict, institution_id: UUID) -> Student:
        ...

class DocumentSearchStrategy:
    def __init__(self, student_repo: StudentRepository):
        self.student_repo = student_repo

    async def identify(self, input_data: dict, institution_id: UUID) -> Student:
        student = await self.student_repo.get_by_document(
            input_data["document_number"], institution_id
        )
        if not student:
            raise HTTPException(404, "Estudiante no encontrado")
        return student
```

`PAEService` recibe la estrategia como dependencia inyectada, no la instancia internamente.

### Doble entrega

`pae_deliveries` tiene `UNIQUE (student_id, delivery_date)`. Si el operador intenta registrar una segunda entrega el mismo día, la BD lanza `UniqueViolationError`. El service debe capturarla y devolver `409 Conflict` con mensaje claro.

### Lógica del job de notificación

El job `notify_pae_no_claim` se programa contra `institution.pae_delivery_end_time`. Solo notifica si hubo al menos una entrega ese día:

```
SI COUNT(pae_deliveries WHERE delivery_date = hoy AND institution_id = X) = 0
    → No notificar. Se asume que el PAE no operó ese día.
SI COUNT > 0
    → Notificar acudientes de estudiantes con pae_enrollment activo (is_active=True,
      academic_year=año vigente) que no tienen delivery registrado hoy.
```

### `get_by_document` en StudentRepository

Agregar este método al repository existente — no crear uno nuevo:

```python
async def get_by_document(self, document_number: str, institution_id: UUID) -> Student | None:
    result = await self.session.execute(
        select(Student).where(
            Student.document_number == document_number,
            Student.institution_id == institution_id,
            Student.is_active == True,
        )
    )
    return result.scalar_one_or_none()
```

---

## Checklist de implementación

### Fase 1 — Schemas Pydantic
- [ ] `app/schemas/pae.py`
  - [ ] `PAEDeliveryCreate` — `document_number` (MVP), `delivery_date`
  - [ ] `PAEDeliveryResponse` — `id`, `student_id`, `delivery_date`, `identification_method`, `created_at`
  - [ ] `PAEEnrollmentResponse` — `id`, `student_id`, `academic_year`, `is_active`

### Fase 2 — Repositories
- [ ] Agregar `get_by_document(document_number, institution_id)` en `app/repositories/student_repository.py`
- [ ] `app/repositories/pae_repository.py`
  - [ ] `get_enrollment(student_id, academic_year, institution_id)` — verifica que el estudiante está inscrito en PAE
  - [ ] `get_delivery_today(student_id, delivery_date, institution_id)` — verifica doble entrega
  - [ ] `create_delivery(student_id, user_id, delivery_date, identification_method, institution_id)`
  - [ ] `list_deliveries(delivery_date, institution_id, group_id?)` — entregas del día
  - [ ] `list_enrollments(institution_id, academic_year, group_id?)` — inscritos activos
  - [ ] `count_deliveries_today(delivery_date, institution_id)` — para el job

### Fase 3 — Strategy
- [ ] `app/services/pae_identification.py`
  - [ ] `PAEIdentificationStrategy` Protocol
  - [ ] `DocumentSearchStrategy` — implementación MVP

### Fase 4 — Service
- [ ] `app/services/pae_service.py`
  - [ ] `register_delivery(data, institution_id, user_id)`:
    - Identifica al estudiante via strategy
    - Verifica inscripción PAE activa en el año vigente → 400 si no está inscrito
    - Crea entrega → captura UniqueViolationError → 409 si ya fue entregado hoy
    - Encola job (stub) si aplica
  - [ ] `list_deliveries(delivery_date, institution_id, group_id?)`
  - [ ] `list_enrollments(institution_id, academic_year, group_id?)`

### Fase 5 — Job de notificación ⏳ PENDIENTE (igual que agendatorio)
- [ ] `app/jobs/pae_jobs.py` — stub ya existe (`notify_pae_no_claim`)
- [ ] Implementar lógica completa cuando se integre el email

### Fase 6 — Router
- [ ] `app/routers/pae.py`
  - [ ] `POST /pae/deliveries`
  - [ ] `GET /pae/deliveries`
  - [ ] `GET /pae/enrollments`
- [ ] Registrar en `app/main.py`

### Fase 7 — Tests
- [ ] `tests/unit/test_pae_service.py`
  - [ ] `register_delivery` falla si el estudiante no está inscrito en PAE
  - [ ] `register_delivery` devuelve 409 si ya hay entrega hoy para ese estudiante
  - [ ] `register_delivery` exitoso con `DocumentSearchStrategy` mockeada
  - [ ] `DocumentSearchStrategy` devuelve 404 si el documento no existe

---

## Orden sugerido de ejecución

1. `get_by_document` en `student_repository.py`
2. Schemas
3. `pae_repository.py`
4. Strategy (`pae_identification.py`)
5. `pae_service.py`
6. `pae_jobs.py` (stub)
7. `pae_router.py` + registro en `main.py`
8. Tests

---

## Riesgos y puntos de atención

| Riesgo | Mitigación |
|--------|-----------|
| Doble entrega el mismo día | `UNIQUE (student_id, delivery_date)` en BD + capturar `UniqueViolationError` → 409 |
| Estudiante no inscrito en PAE | Verificar `pae_enrollments` antes de crear entrega → 400 |
| Job notifica en día sin servicio PAE | Verificar `COUNT(deliveries hoy) > 0` antes de notificar |
| `get_by_document` modificado por otro módulo | Es de solo lectura, safe para reutilizar |
| `pae_delivery_end_time` por institución | El scheduler de Celery beat debe leer ese campo para programar el job |

---

*Plan — Módulo PAE | Mayo 2026*
