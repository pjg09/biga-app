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
    GradeOption,
    GroupOption,
    MyRecordItem,
    NoteCreate,
    NoteResponse,
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


# --- Catálogo académico (para los selectores de búsqueda de estudiantes) ---

@router.get("/grades", response_model=list[GradeOption])
async def list_grades(
    current_user: User = Depends(get_current_user),
    service: AgendatorioService = Depends(get_agendatorio_service),
):
    return await service.list_grades(current_user.institution_id)


@router.get("/groups", response_model=list[GroupOption])
async def list_groups(
    current_user: User = Depends(get_current_user),
    service: AgendatorioService = Depends(get_agendatorio_service),
):
    return await service.list_groups(current_user.institution_id)


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


@router.get("/my-records", response_model=list[MyRecordItem])
async def list_my_records(
    student_id: UUID | None = None,
    include_archived: bool = False,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: AgendatorioService = Depends(get_agendatorio_service),
):
    return await service.list_my_records(
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        student_id=student_id,
        include_archived=include_archived,
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


@router.post("/records/{record_id}/notes", response_model=NoteResponse, status_code=201)
async def add_note(
    record_id: UUID,
    body: NoteCreate,
    current_user: User = Depends(get_current_user),
    service: AgendatorioService = Depends(get_agendatorio_service),
):
    return await service.add_note(
        record_id=record_id,
        user_id=current_user.id,
        institution_id=current_user.institution_id,
        note=body.note,
    )


@router.post("/records/{record_id}/archive", status_code=204)
async def archive_record(
    record_id: UUID,
    current_user: User = Depends(get_current_user),
    service: AgendatorioService = Depends(get_agendatorio_service),
):
    await service.set_record_archived(
        record_id=record_id, user_id=current_user.id,
        institution_id=current_user.institution_id, archived=True,
    )


@router.post("/records/{record_id}/unarchive", status_code=204)
async def unarchive_record(
    record_id: UUID,
    current_user: User = Depends(get_current_user),
    service: AgendatorioService = Depends(get_agendatorio_service),
):
    await service.set_record_archived(
        record_id=record_id, user_id=current_user.id,
        institution_id=current_user.institution_id, archived=False,
    )
