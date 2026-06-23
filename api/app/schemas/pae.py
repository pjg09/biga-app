from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import PAEIdentificationMethod


class PAEStudentListItem(BaseModel):
    student_id: UUID
    document_number: str
    first_name: str
    last_name: str
    photo_url: str | None
    delivered: bool

    model_config = {"from_attributes": True}


class PAEDeliveryCreate(BaseModel):
    student_id: UUID
    identification_method: PAEIdentificationMethod = PAEIdentificationMethod.DOCUMENT


class PAEEnrollmentCreate(BaseModel):
    student_id: UUID


class PAEEnrollmentResponse(BaseModel):
    id: UUID
    student_id: UUID
    institution_id: UUID
    academic_year: int
    is_active: bool
    enrolled_at: datetime

    model_config = {"from_attributes": True}


class PAEWeeklyReportItem(BaseModel):
    delivery_date: date
    count: int


class PAEWeeklyReportResponse(BaseModel):
    week_start: date
    week_end: date
    total: int
    items: list[PAEWeeklyReportItem]


class PAEDeliveryResponse(BaseModel):
    id: UUID
    student_id: UUID
    institution_id: UUID
    delivered_by_user_id: UUID
    delivery_date: date
    identification_method: PAEIdentificationMethod
    created_at: datetime

    model_config = {"from_attributes": True}


class PAEAuditItem(BaseModel):
    delivery_id: UUID
    student_id: UUID
    delivery_date: date
    delivered_by_user_id: UUID
    enrollment_hash_valid: bool
    delivery_hash_valid: bool
    hash_valid: bool


class PAEAuditResponse(BaseModel):
    total: int
    tampered: int
    records: list[PAEAuditItem]
