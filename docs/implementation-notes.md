# BIGA — Notas de Implementación

Decisiones y restricciones no obvias que deben respetarse al construir cada capa.

---

## Aislamiento multi-tenant en Repositories

### El problema

Todas las tablas operativas tienen `institution_id`, pero el ORM no filtra por él automáticamente. No hay row-level security en PostgreSQL ni ningún mecanismo que lo fuerce a nivel de framework. La seguridad multi-tenant depende enteramente de que cada query en cada Repository incluya el filtro.

Un Repository que omita `WHERE institution_id = :id` expone registros de todas las instituciones al usuario autenticado. Este es el error de multi-tenancy más frecuente en este patrón y no tiene red de seguridad.

### La regla

**Todo método de Repository que acceda a una tabla operativa debe recibir `institution_id` como parámetro y usarlo en el WHERE. Sin excepción.**

Tablas operativas (todas las que tienen `institution_id`): `grades`, `groups`, `class_periods`, `users`, `user_groups`, `students`, `student_groups`, `guardians`, `pae_enrollments`, `pae_deliveries`, `attendance_records`, `attendance_tokens`, `attendance_justifications`, `convivencia_articles`, `discipline_records`, `discipline_record_notes`, `early_departures`, `notifications_log`, `import_jobs`.

### Patrón correcto

```python
class StudentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, student_id: UUID, institution_id: UUID) -> Student | None:
        result = await self.session.execute(
            select(Student).where(
                Student.id == student_id,
                Student.institution_id == institution_id,  # OBLIGATORIO
            )
        )
        return result.scalar_one_or_none()

    async def list_active(self, institution_id: UUID) -> list[Student]:
        result = await self.session.execute(
            select(Student).where(
                Student.institution_id == institution_id,  # OBLIGATORIO
                Student.is_active == True,
            )
        )
        return list(result.scalars().all())
```

### Patrón incorrecto

```python
# NUNCA hacer esto — expone datos de todas las instituciones
async def get_by_id(self, student_id: UUID) -> Student | None:
    result = await self.session.execute(
        select(Student).where(Student.id == student_id)
    )
    return result.scalar_one_or_none()
```

### De dónde viene `institution_id`

El `institution_id` llega desde el token JWT del usuario autenticado. El dependency de FastAPI lo extrae y lo pasa al Service, que lo pasa al Repository. Nunca debe tomarse de los parámetros de la request directamente.

```python
# En el dependency de auth (ya implementado en app/core/dependencies.py):
async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    user_id = decode_access_token(token)
    user = await UserRepository(db).get_by_id(UUID(user_id))  # excepción a la regla: resuelve el tenant
    return user  # user.institution_id es la fuente de verdad del tenant

# En el router:
@router.get("/students")
async def list_students(current_user: User = Depends(get_current_user), ...):
    return await student_service.list_active(institution_id=current_user.institution_id)
```

---

## Creación de estudiantes — acudiente primario obligatorio

### La regla

Todo estudiante debe tener exactamente un acudiente con `is_primary = True` desde el momento de su creación. No puede existir un `Student` en BD sin al menos un `Guardian` primario asociado.

### Enforcement

La constraint no se puede expresar en SQL de forma simple (cruza dos tablas). Se enforza en la capa de Service:

- `POST /students` debe recibir en el mismo request al menos un acudiente. El Service crea el `Student` y el/los `Guardian` en la misma transacción. Si no viene ningún acudiente, el endpoint retorna `422`.
- El Service valida que exactamente uno de los acudientes del request tenga `is_primary = True`.
- Al eliminar un acudiente, el Service debe verificar que el estudiante no quede sin acudiente primario. Si es el último o el único primario, la operación retorna `409`.

### Patrón de creación atómica

```python
async def create_student(self, student_data: StudentCreate, institution_id: UUID) -> Student:
    if not student_data.guardians:
        raise HTTPException(status_code=422, detail="Se requiere al menos un acudiente")
    primaries = [g for g in student_data.guardians if g.is_primary]
    if len(primaries) != 1:
        raise HTTPException(status_code=422, detail="Exactamente un acudiente debe ser primario")

    student = await self.student_repo.create(student_data, institution_id)
    for guardian_data in student_data.guardians:
        await self.guardian_repo.create(guardian_data, student_id=student.id)
    return student
    # get_db() hace commit al salir — student y guardians se persisten juntos
```

### Implicación en agendatorio

Si `create_record` no encuentra acudiente primario para un estudiante, es un estado inválido del sistema (nunca debería ocurrir si el invariante se cumple). El comportamiento correcto es: crear el registro disciplinario, loguear el error, y omitir la notificación — no bloquear al docente.

---

*Notas de implementación — BIGA APP | Mayo 2026*
