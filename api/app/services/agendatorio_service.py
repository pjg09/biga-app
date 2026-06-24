import logging
from datetime import date as PyDate
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.adapters.storage.s3 import S3StorageAdapter
from app.jobs.agendatorio_jobs import notify_discipline_record
from app.repositories.agendatorio_repository import AgendatorioRepository
from app.repositories.guardian_repository import GuardianRepository
from app.repositories.student_repository import StudentRepository, StudentSearchRow
from app.schemas.agendatorio import (
    ArticleCreate,
    ArticleResponse,
    ArticleUpdate,
    DisciplineRecordCreate,
    DisciplineRecordDetail,
    DisciplineRecordResponse,
)
from app.models.agendatorio import ConvivenciaArticle, DisciplineRecord

logger = logging.getLogger(__name__)


class AgendatorioService:
    def __init__(
        self,
        agendatorio_repo: AgendatorioRepository,
        student_repo: StudentRepository,
        guardian_repo: GuardianRepository,
        storage: S3StorageAdapter,
    ):
        self.agendatorio_repo = agendatorio_repo
        self.student_repo = student_repo
        self.guardian_repo = guardian_repo
        self.storage = storage

    # --- Artículos ---

    async def list_articles(self, institution_id: UUID) -> list[ConvivenciaArticle]:
        return await self.agendatorio_repo.list_articles(institution_id)

    async def create_article(self, data: ArticleCreate, institution_id: UUID) -> ConvivenciaArticle:
        existing = await self.agendatorio_repo.get_article_by_code(data.code, institution_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un artículo con el código '{data.code}'",
            )
        return await self.agendatorio_repo.create_article(data.model_dump(), institution_id)

    async def update_article(
        self, article_id: UUID, data: ArticleUpdate, institution_id: UUID
    ) -> ConvivenciaArticle:
        article = await self.agendatorio_repo.get_article(article_id, institution_id)
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artículo no encontrado")

        if data.code is not None and data.code != article.code:
            existing = await self.agendatorio_repo.get_article_by_code(data.code, institution_id)
            if existing and existing.id != article.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe un artículo con el código '{data.code}'",
                )

        return await self.agendatorio_repo.update_article(article, data.model_dump(exclude_unset=True))

    async def deactivate_article(self, article_id: UUID, institution_id: UUID) -> None:
        article = await self.agendatorio_repo.get_article(article_id, institution_id)
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artículo no encontrado")
        await self.agendatorio_repo.deactivate_article(article)

    # --- Búsqueda de estudiantes ---

    async def search_students(
        self,
        q: str,
        institution_id: UUID,
        group_id: UUID | None = None,
        grade_id: UUID | None = None,
    ) -> list[StudentSearchRow]:
        return await self.student_repo.search(
            q=q,
            institution_id=institution_id,
            group_id=group_id,
            grade_id=grade_id,
        )

    # --- Registros disciplinarios ---

    async def create_record(
        self,
        data: DisciplineRecordCreate,
        signature_bytes: bytes,
        institution_id: UUID,
        user_id: UUID,
    ) -> DisciplineRecord:
        # Validar artículos: deben existir en la institución y estar activos.
        # Responder 400 (no 404/403) para no revelar info de otros tenants.
        unique_article_ids = list(dict.fromkeys(data.article_ids))
        if not unique_article_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere al menos un artículo",
            )
        articles = await self.agendatorio_repo.get_articles_by_ids(unique_article_ids, institution_id)

        if len(articles) != len(unique_article_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uno o más artículos no son válidos para esta institución",
            )
        inactive = [a for a in articles if not a.is_active]
        if inactive:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uno o más artículos están inactivos",
            )

        # Subir firma a storage antes de escribir en BD.
        # Si storage falla, no se crea el registro.
        record_id = uuid4()
        key = f"signatures/{institution_id}/{record_id}.png"
        self.storage.upload(key, signature_bytes, "image/png")

        record = await self.agendatorio_repo.create_record(
            record_id=record_id,
            student_id=data.student_id,
            institution_id=institution_id,
            user_id=user_id,
            date=data.date,
            observations=data.observations,
            signature_url=key,
            article_ids=unique_article_ids,
        )

        # Encolar notificación. El job se encola después del flush implícito
        # para que el worker no lea el registro antes de que sea visible.
        guardian = await self.guardian_repo.get_primary(data.student_id)
        if guardian:
            notify_discipline_record.delay(str(record.id), str(institution_id))
        else:
            logger.error(
                "No se encontró acudiente primario para el estudiante %s al crear registro disciplinario %s",
                data.student_id,
                record.id,
            )

        return record

    async def list_records(
        self,
        institution_id: UUID,
        student_id: UUID | None = None,
        article_id: UUID | None = None,
        date_from: PyDate | None = None,
        date_to: PyDate | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[DisciplineRecord]:
        if date_from is not None and date_to is not None and date_from > date_to:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date_from no puede ser posterior a date_to",
            )
        if student_id is not None:
            student = await self.student_repo.get_by_id(student_id, institution_id)
            if not student:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estudiante no encontrado")
        return await self.agendatorio_repo.list_records(
            institution_id=institution_id,
            student_id=student_id,
            article_id=article_id,
            date_from=date_from,
            date_to=date_to,
            skip=skip,
            limit=limit,
        )

    async def get_record(self, record_id: UUID, institution_id: UUID) -> DisciplineRecordDetail:
        record, articles = await self.agendatorio_repo.get_record(record_id, institution_id)
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro no encontrado")
        return DisciplineRecordDetail(
            id=record.id,
            student_id=record.student_id,
            date=record.date,
            observations=record.observations,
            signature_url=self.storage.get_url(record.signature_url),
            articles=[ArticleResponse.model_validate(a) for a in articles],
            created_at=record.created_at,
        )
