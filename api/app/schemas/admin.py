from datetime import date as PyDate, datetime, time
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.enums import GuardianRelationship, UserRole
from app.schemas.guardian import GuardianCreate, GuardianResponse


def _strip_required(v: str) -> str:
    """Recorta y rechaza lo que quede vacío.

    `Field(min_length=1)` NO basta: los validadores corren **después** de las
    restricciones del Field, así que "   " pasa el min_length y luego un
    `.strip()` posterior lo deja en cadena vacía. Hay que comprobarlo aquí.
    """
    v = v.strip()
    if not v:
        raise ValueError("No puede estar vacío")
    return v


class AdminStats(BaseModel):
    # Generado para el día y semana actuales.
    date: PyDate

    # Población
    students_active: int
    staff_total: int
    teachers: int
    pae_operators: int

    # PAE
    pae_enrolled: int
    pae_delivered_today: int
    pae_delivered_week: int
    pae_claim_rate: float  # % de inscritos que reclamaron hoy (0-100)

    # Asistencia (hoy)
    attendance_present_today: int
    attendance_absent_today: int
    attendance_late_today: int
    attendance_justified_today: int
    attendance_rate_today: float  # % presentes+tardanzas sobre registros de hoy

    # Salidas tempranas (hoy)
    departures_today: int

    # Convivencia (infracciones por gravedad, histórico)
    discipline_records: int
    discipline_leve: int
    discipline_moderada: int
    discipline_grave: int

    # Notificaciones (histórico)
    notifications_sent: int
    notifications_failed: int
    notifications_pending: int


# ── Gestión: Personal (usuarios) ──────────────────────────────────────

# El admin no fija ni cambia contraseñas: al crear, el service genera una
# temporal y se la envía al usuario por correo; para cambiarla está el flujo
# público de `/auth/password-reset`. Por eso ni `AdminUserCreate` ni
# `AdminUserUpdate` aceptan `password` — si lo aceptaran, un admin podría fijar
# la contraseña de otra persona y entrar como ella.
class AdminUserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    document_number: str = Field(min_length=3, max_length=20)
    email: str = Field(min_length=5, max_length=255)
    role: UserRole


class AdminUserUpdate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    document_number: str = Field(min_length=3, max_length=20)
    email: str = Field(min_length=5, max_length=255)
    role: UserRole


class AdminUserResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    document_number: str
    email: str
    role: UserRole
    is_active: bool
    photo_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Gestión: Académico ────────────────────────────────────────────────

class GradeResponse(BaseModel):
    id: UUID
    name: str
    level: int

    model_config = {"from_attributes": True}


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return _strip_required(v)


class SubjectUpdate(BaseModel):
    """Solo el nombre. `subject_id` no cambia, así que las asignaciones
    docente-salón que la referencian siguen apuntando a la misma materia."""
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return _strip_required(v)


class SubjectResponse(BaseModel):
    id: UUID
    name: str

    model_config = {"from_attributes": True}


class GroupCreate(BaseModel):
    grade_id: UUID
    name: str = Field(min_length=1, max_length=10)
    academic_year: int = Field(ge=2000, le=2100)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return _strip_required(v)


class GroupResponse(BaseModel):
    id: UUID
    grade_id: UUID
    grade_name: str | None = None
    grade_level: int | None = None
    name: str
    academic_year: int
    # Matrículas activas de estudiantes activos. Lo calcula el repo con un
    # subselect para no disparar una consulta por salón desde el front.
    student_count: int = 0

    model_config = {"from_attributes": True}


class GroupUpdate(BaseModel):
    """Solo el nombre. Cambiar de grado sería mover el salón entero — y con él
    el grado de todos sus matriculados —, que es otra operación distinta."""
    name: str = Field(min_length=1, max_length=10)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return _strip_required(v)


class GroupStudentAdd(BaseModel):
    student_id: UUID


class StudentGroupCreate(BaseModel):
    student_id: UUID
    group_id: UUID
    academic_year: int = Field(ge=2000, le=2100)


class StudentGroupResponse(BaseModel):
    id: UUID
    student_id: UUID
    group_id: UUID
    academic_year: int
    is_active: bool

    model_config = {"from_attributes": True}


# --- Alta completa de estudiante (estudiante + matrícula opcional + acudientes) ---

class AdminStudentCreate(BaseModel):
    document_number: str = Field(min_length=3, max_length=20)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    birth_date: PyDate
    # `student_groups` no tiene grade_id: el grado es un filtro de UI para acotar
    # el <select> de salón, nunca llega hasta acá.
    group_id: UUID | None = None
    # Inscribe al PAE del año vigente en la misma transacción del alta.
    is_pae_enrolled: bool = False
    guardians: list[GuardianCreate] = Field(min_length=1)

    @field_validator("document_number", "first_name", "last_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

    @field_validator("birth_date")
    @classmethod
    def birth_date_not_future(cls, v: PyDate) -> PyDate:
        if v > PyDate.today():
            raise ValueError("birth_date no puede estar en el futuro")
        return v

    @model_validator(mode="after")
    def exactly_one_primary(self) -> "AdminStudentCreate":
        if sum(1 for g in self.guardians if g.is_primary) != 1:
            raise ValueError("Debe haber exactamente un acudiente marcado como primario")
        return self


class AdminGuardianUpdate(BaseModel):
    # None = acudiente nuevo (se crea). Con valor = acudiente existente (se
    # actualiza in-place; nunca se borra y recrea, ver docs/students.md — un
    # acudiente puede tener notificaciones históricas con FK a su id).
    id: UUID | None = None
    full_name: str = Field(min_length=1, max_length=255)
    relationship: GuardianRelationship
    email: EmailStr = Field(max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    is_primary: bool = False

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class AdminStudentUpdate(BaseModel):
    document_number: str = Field(min_length=3, max_length=20)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    birth_date: PyDate
    group_id: UUID | None = None
    is_pae_enrolled: bool = False
    guardians: list[AdminGuardianUpdate] = Field(min_length=1)

    @field_validator("document_number", "first_name", "last_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

    @field_validator("birth_date")
    @classmethod
    def birth_date_not_future(cls, v: PyDate) -> PyDate:
        if v > PyDate.today():
            raise ValueError("birth_date no puede estar en el futuro")
        return v

    @model_validator(mode="after")
    def exactly_one_primary(self) -> "AdminStudentUpdate":
        if sum(1 for g in self.guardians if g.is_primary) != 1:
            raise ValueError("Debe haber exactamente un acudiente marcado como primario")
        return self


class AdminStudentDetailResponse(BaseModel):
    id: UUID
    document_number: str
    first_name: str
    last_name: str
    birth_date: PyDate
    photo_url: str | None
    is_active: bool
    grade_id: UUID | None = None
    grade_name: str | None = None
    group_id: UUID | None = None
    group_name: str | None = None
    is_pae_enrolled: bool
    guardians: list[GuardianResponse]

    model_config = {"from_attributes": True}


# ── Gestión: Horarios ─────────────────────────────────────────────────

class _ClassPeriodFields(BaseModel):
    """Campos comunes de un bloque. `name` es la etiqueta ("Primera hora",
    "Descanso"); la materia va en `subject_id`, del catálogo. Antes se usaba
    `name` para ambas cosas y ya divergía del catálogo."""
    name: str = Field(min_length=1, max_length=100)
    period_order: int = Field(ge=1)
    # Periodos consecutivos que ocupa. 2 = clase doble.
    span: int = Field(default=1, ge=1, le=12)
    start_time: time
    end_time: time
    subject_id: UUID | None = None
    # Obligatorio: todo bloque tiene docente. Ver el modelo y la migración
    # `d6c1f8a390b4` — sin docente nadie toma lista en ese bloque.
    user_id: UUID

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return _strip_required(v)

    @model_validator(mode="after")
    def end_after_start(self):
        # Duplica el CHECK de la BD para dar 422 con mensaje en vez de un 500.
        if self.start_time >= self.end_time:
            raise ValueError("La hora de fin debe ser posterior a la de inicio")
        return self


class ClassPeriodCreate(_ClassPeriodFields):
    group_id: UUID
    day_of_week: int = Field(ge=1, le=7)


class ClassPeriodUpdate(_ClassPeriodFields):
    """No incluye `group_id` ni `day_of_week`: mover un bloque de salón o de día
    es recolocarlo, no editarlo, y chocaría con UNIQUE(group, orden, día)."""


class ClassPeriodBulkCreate(BaseModel):
    """Crea la jornada completa de un salón en una sola petición.

    Sin esto, un horario de 6 periodos × 5 días son 30 envíos de formulario.
    Los bloques que ya existan para ese (salón, orden, día) se **omiten**, no
    fallan: así se puede reejecutar para rellenar huecos.
    """
    group_id: UUID
    days: list[int] = Field(min_length=1)
    periods: list[_ClassPeriodFields] = Field(min_length=1)

    @field_validator("days")
    @classmethod
    def valid_days(cls, v: list[int]) -> list[int]:
        if any(d < 1 or d > 7 for d in v):
            raise ValueError("Los días deben estar entre 1 (lunes) y 7 (domingo)")
        return sorted(set(v))

    @model_validator(mode="after")
    def unique_orders(self):
        orders = [p.period_order for p in self.periods]
        if len(orders) != len(set(orders)):
            raise ValueError("Hay dos bloques con el mismo orden")
        return self


class ClassPeriodBulkResult(BaseModel):
    created: int
    skipped: int


class ClassPeriodResponse(BaseModel):
    id: UUID
    group_id: UUID
    name: str
    period_order: int
    start_time: time
    end_time: time
    day_of_week: int
    span: int = 1
    subject_id: UUID | None = None
    subject_name: str | None = None
    user_id: UUID | None = None
    teacher_name: str | None = None

    model_config = {"from_attributes": True}


class UserGroupCreate(BaseModel):
    user_id: UUID
    group_id: UUID
    academic_year: int = Field(ge=2000, le=2100)
    subject_id: UUID | None = None


class UserGroupResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_name: str | None = None
    group_id: UUID
    academic_year: int
    subject_id: UUID | None = None
    subject_name: str | None = None

    model_config = {"from_attributes": True}
