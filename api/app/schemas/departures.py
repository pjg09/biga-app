from datetime import date as PyDate, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field


class DepartureCreate(BaseModel):
    student_id: UUID
    departure_time: time
    reason: str | None = Field(default=None, max_length=2000)


class DepartureResponse(BaseModel):
    id: UUID
    student_id: UUID
    student_name: str | None = None
    photo_url: str | None = None
    departure_date: PyDate
    departure_time: time
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
