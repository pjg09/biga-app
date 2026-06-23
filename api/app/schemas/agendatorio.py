from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ArticleSeverity


class ArticleCreate(BaseModel):
    code: str
    title: str
    description: str
    severity: ArticleSeverity


class ArticleUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: ArticleSeverity | None = None


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


class DisciplineRecordDetail(BaseModel):
    id: UUID
    student_id: UUID
    date: date
    observations: str
    signature_url: str
    articles: list[ArticleResponse]
    created_at: datetime
