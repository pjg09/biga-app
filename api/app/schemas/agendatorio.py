from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ArticleSeverity


class GradeOption(BaseModel):
    id: UUID
    name: str
    level: int

    model_config = {"from_attributes": True}


class GroupOption(BaseModel):
    id: UUID
    name: str
    grade_id: UUID
    grade_name: str


class ArticleCreate(BaseModel):
    code: str
    title: str
    description: str
    severity: ArticleSeverity


class ArticleUpdate(BaseModel):
    code: str | None = None
    title: str | None = None
    description: str | None = None
    severity: ArticleSeverity | None = None
    is_active: bool | None = None


class ArticleResponse(BaseModel):
    id: UUID
    code: str
    title: str
    description: str
    severity: ArticleSeverity
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DisciplineRecordCreate(BaseModel):
    student_id: UUID
    article_ids: list[UUID] = Field(min_length=1)
    observations: str
    date: date


class DisciplineRecordResponse(BaseModel):
    id: UUID
    student_id: UUID
    date: date
    observations: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ArticleBrief(BaseModel):
    code: str
    title: str
    severity: ArticleSeverity


class NoteCreate(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


class NoteResponse(BaseModel):
    id: UUID
    note: str
    author_name: str
    created_at: datetime


class MyRecordItem(BaseModel):
    """Fila del historial de convivencia del docente."""
    id: UUID
    student_id: UUID
    student_name: str
    grade_name: str | None
    group_name: str | None
    date: date
    observations: str
    articles: list[ArticleBrief]
    note_count: int
    archived: bool
    created_at: datetime


class DisciplineRecordDetail(BaseModel):
    id: UUID
    student_id: UUID
    student_name: str
    grade_name: str | None
    group_name: str | None
    date: date
    observations: str
    signature_url: str
    articles: list[ArticleResponse]
    recorded_by_name: str
    notes: list[NoteResponse]
    archived: bool
    created_at: datetime
