from datetime import date as PyDate, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import AttendanceStatus


class AttendanceStudentItem(BaseModel):
    student_id: UUID
    document_number: str
    first_name: str
    last_name: str
    photo_url: str | None
    status: AttendanceStatus | None  # estado ya registrado hoy, o None si no se ha tomado
    record_id: UUID | None = None    # id del registro de hoy (para marcar llegada)


class FirstClassResponse(BaseModel):
    has_class: bool
    class_period_id: UUID | None = None
    group_id: UUID | None = None
    group_name: str | None = None
    grade_name: str | None = None
    period_name: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    date: PyDate
    already_taken: bool = False
    students: list[AttendanceStudentItem] = []


class AttendanceEntry(BaseModel):
    student_id: UUID
    status: AttendanceStatus


class AttendanceSubmit(BaseModel):
    class_period_id: UUID
    entries: list[AttendanceEntry] = Field(min_length=1)


class AttendanceRecordResponse(BaseModel):
    id: UUID
    student_id: UUID
    class_period_id: UUID
    date: PyDate
    status: AttendanceStatus
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Justificación pública (sin autenticación, el token es la autorización) ---

class JustificationInfo(BaseModel):
    valid: bool
    student_name: str | None = None
    date: PyDate | None = None
    group_name: str | None = None
    already_justified: bool = False
    message: str | None = None


class JustificationSubmit(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


# --- Horario del docente ---

class ScheduleItem(BaseModel):
    class_period_id: UUID
    day_of_week: int
    period_order: int
    name: str
    start_time: time
    end_time: time
    group_name: str
    grade_name: str


# --- Mensajes: excusas enviadas por los acudientes ---

class JustificationMessage(BaseModel):
    record_id: UUID
    student_name: str
    group_name: str | None
    date: PyDate
    reason: str
    submitted_at: datetime
