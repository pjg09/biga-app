from uuid import UUID

from pydantic import BaseModel


class StudentSearchResult(BaseModel):
    id: UUID
    full_name: str
    document_number: str
    photo_url: str | None
    group_name: str | None
    grade_name: str | None
