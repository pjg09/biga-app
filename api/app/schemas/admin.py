from datetime import date as PyDate, datetime, time
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models.enums import GuardianRelationship, UserRole
from app.schemas.guardian import GuardianCreate, GuardianResponse


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

class AdminUserCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    document_number: str = Field(min_length=3, max_length=20)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole


class AdminUserUpdate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    document_number: str = Field(min_length=3, max_length=20)
    email: str = Field(min_length=5, max_length=255)
    role: UserRole
    # Vacío/None = no cambiar la contraseña actual. Si viene, mismo mínimo que al crear.
    password: str | None = Field(default=None, max_length=128)

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str | None) -> str | None:
        v = (v or "").strip() or None
        if v is not None and len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v


class AdminUserResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    document_number: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Gestión: Académico ────────────────────────────────────────────────

class GradeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    level: int = Field(ge=1, le=11)


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
        return v.strip()


class SubjectResponse(BaseModel):
    id: UUID
    name: str

    model_config = {"from_attributes": True}


class GroupCreate(BaseModel):
    grade_id: UUID
    name: str = Field(min_length=1, max_length=10)
    academic_year: int = Field(ge=2000, le=2100)


class GroupResponse(BaseModel):
    id: UUID
    grade_id: UUID
    grade_name: str | None = None
    name: str
    academic_year: int

    model_config = {"from_attributes": True}


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

class ClassPeriodCreate(BaseModel):
    group_id: UUID
    name: str = Field(min_length=1, max_length=100)
    period_order: int = Field(ge=1)
    start_time: time
    end_time: time
    day_of_week: int = Field(ge=1, le=5)


class ClassPeriodResponse(BaseModel):
    id: UUID
    group_id: UUID
    name: str
    period_order: int
    start_time: time
    end_time: time
    day_of_week: int

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
