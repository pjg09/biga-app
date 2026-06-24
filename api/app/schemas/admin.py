from datetime import date as PyDate, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import UserRole


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


class UserGroupResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_name: str | None = None
    group_id: UUID
    academic_year: int

    model_config = {"from_attributes": True}
