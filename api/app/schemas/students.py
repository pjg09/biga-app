from datetime import date as PyDate, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class StudentSearchResult(BaseModel):
    id: UUID
    full_name: str
    document_number: str
    photo_url: str | None
    group_name: str | None
    grade_name: str | None


class StudentCreate(BaseModel):
    document_number: str = Field(min_length=3, max_length=20)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    birth_date: PyDate
    photo_url: str | None = Field(default=None, max_length=500)

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


class StudentResponse(BaseModel):
    id: UUID
    document_number: str
    first_name: str
    last_name: str
    birth_date: PyDate
    photo_url: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
