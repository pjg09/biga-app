from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.storage.s3 import S3StorageAdapter
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_storage_adapter
from app.models.user import User
from app.repositories.agendatorio_repository import AgendatorioRepository
from app.repositories.guardian_repository import GuardianRepository
from app.repositories.student_repository import StudentRepository
from app.schemas.agendatorio import (
    ArticleCreate,
    ArticleResponse,
    ArticleUpdate,
    DisciplineRecordCreate,
    DisciplineRecordDetail,
    DisciplineRecordResponse,
)
from app.services.agendatorio_service import AgendatorioService

router = APIRouter(prefix="/agendatorio", tags=["agendatorio"])


def get_agendatorio_service(
    db: AsyncSession = Depends(get_db),
    storage: S3StorageAdapter = Depends(get_storage_adapter),
) -> AgendatorioService:
    return AgendatorioService(
        agendatorio_repo=AgendatorioRepository(db),
        student_repo=StudentRepository(db),
        guardian_repo=GuardianRepository(db),
        storage=storage,
    )


# --- Artículos ---

@router.get("/articles", response_model=list[ArticleResponse])
async def list_articles(
    current_user: User = Depends(get_current_user),
    service: AgendatorioService = Depends(get_agendatorio_service),
):
    return await service.list_articles(current_user.institution_id)


@router.post("/articles", response_model=ArticleResponse, status_code=201)
async def create_article(
    data: ArticleCreate,
    current_user: User = Depends(get_current_user),
    service: AgendatorioService = Depends(get_agendatorio_service),
):
    return await service.create_article(data, current_user.institution_id)


@router.patch("/articles/{article_id}", response_model=ArticleResponse)
async def update_article(
    article_id: UUID,
    data: ArticleUpdate,
    current_user: User = Depends(get_current_user),
    service: AgendatorioService = Depends(get_agendatorio_service),
):
    return await service.update_article(article_id, data, current_user.institution_id)


@router.delete("/articles/{article_id}", status_code=204)
async def deactivate_article(
    article_id: UUID,
    current_user: User = Depends(get_current_user),
    service: AgendatorioService = Depends(get_agendatorio_service),
):
    await service.deactivate_article(article_id, current_user.institution_id)


# --- Registros disciplinarios ---

@router.post("/records", response_model=DisciplineRecordResponse, status_code=201)
async def create_record(
    data: str = Form(..., description="JSON con los campos del registro"),
    signature: UploadFile = File(..., description="PNG de la firma del estudiante"),
    current_user: User = Depends(get_current_user),
    service: AgendatorioService = Depends(get_agendatorio_service),
):
    record_data = DisciplineRecordCreate.model_validate_json(data)
    signature_bytes = await signature.read()
    return await service.create_record(
        data=record_data,
        signature_bytes=signature_bytes,
        institution_id=current_user.institution_id,
        user_id=current_user.id,
    )


@router.get("/records", response_model=list[DisciplineRecordResponse])
async def list_records(
    student_id: UUID | None = None,
    article_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: AgendatorioService = Depends(get_agendatorio_service),
):
    return await service.list_records(
        institution_id=current_user.institution_id,
        student_id=student_id,
        article_id=article_id,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )


@router.get("/records/{record_id}", response_model=DisciplineRecordDetail)
async def get_record(
    record_id: UUID,
    current_user: User = Depends(get_current_user),
    service: AgendatorioService = Depends(get_agendatorio_service),
):
    return await service.get_record(record_id, current_user.institution_id)
