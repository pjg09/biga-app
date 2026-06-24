from datetime import date as PyDate
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agendatorio import ConvivenciaArticle, DisciplineRecord, DisciplineRecordArticle


class AgendatorioRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Artículos ---

    async def list_articles(self, institution_id: UUID) -> list[ConvivenciaArticle]:
        result = await self.session.execute(
            select(ConvivenciaArticle)
            .where(
                ConvivenciaArticle.institution_id == institution_id,
                ConvivenciaArticle.is_active == True,
            )
            .order_by(ConvivenciaArticle.code)
        )
        return list(result.scalars().all())

    async def get_article(self, article_id: UUID, institution_id: UUID) -> ConvivenciaArticle | None:
        result = await self.session.execute(
            select(ConvivenciaArticle).where(
                ConvivenciaArticle.id == article_id,
                ConvivenciaArticle.institution_id == institution_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_article_by_code(self, code: str, institution_id: UUID) -> ConvivenciaArticle | None:
        result = await self.session.execute(
            select(ConvivenciaArticle).where(
                ConvivenciaArticle.code == code,
                ConvivenciaArticle.institution_id == institution_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_articles_by_ids(
        self, article_ids: list[UUID], institution_id: UUID
    ) -> list[ConvivenciaArticle]:
        result = await self.session.execute(
            select(ConvivenciaArticle).where(
                ConvivenciaArticle.id.in_(article_ids),
                ConvivenciaArticle.institution_id == institution_id,
            )
        )
        return list(result.scalars().all())

    async def create_article(self, data: dict, institution_id: UUID) -> ConvivenciaArticle:
        article = ConvivenciaArticle(**data, institution_id=institution_id)
        self.session.add(article)
        await self.session.flush()
        await self.session.refresh(article)
        return article

    async def update_article(self, article: ConvivenciaArticle, data: dict) -> ConvivenciaArticle:
        for key, value in data.items():
            setattr(article, key, value)
        await self.session.flush()
        return article

    async def deactivate_article(self, article: ConvivenciaArticle) -> None:
        article.is_active = False
        await self.session.flush()

    # --- Registros ---

    async def create_record(
        self,
        record_id: UUID,
        student_id: UUID,
        institution_id: UUID,
        user_id: UUID,
        date: PyDate,
        observations: str,
        signature_url: str,
        article_ids: list[UUID],
    ) -> DisciplineRecord:
        record = DisciplineRecord(
            id=record_id,
            student_id=student_id,
            institution_id=institution_id,
            recorded_by_user_id=user_id,
            date=date,
            observations=observations,
            signature_url=signature_url,
        )
        self.session.add(record)
        for article_id in article_ids:
            self.session.add(
                DisciplineRecordArticle(
                    discipline_record_id=record_id,
                    article_id=article_id,
                )
            )
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get_record(
        self, record_id: UUID, institution_id: UUID
    ) -> tuple[DisciplineRecord | None, list[ConvivenciaArticle]]:
        record_result = await self.session.execute(
            select(DisciplineRecord).where(
                DisciplineRecord.id == record_id,
                DisciplineRecord.institution_id == institution_id,
            )
        )
        record = record_result.scalar_one_or_none()
        if not record:
            return None, []

        articles_result = await self.session.execute(
            select(ConvivenciaArticle)
            .join(
                DisciplineRecordArticle,
                DisciplineRecordArticle.article_id == ConvivenciaArticle.id,
            )
            .where(DisciplineRecordArticle.discipline_record_id == record_id)
        )
        return record, list(articles_result.scalars().all())

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
        query = select(DisciplineRecord).where(DisciplineRecord.institution_id == institution_id)
        if student_id is not None:
            query = query.where(DisciplineRecord.student_id == student_id)
        if date_from is not None:
            query = query.where(DisciplineRecord.date >= date_from)
        if date_to is not None:
            query = query.where(DisciplineRecord.date <= date_to)
        if article_id is not None:
            query = query.join(
                DisciplineRecordArticle,
                DisciplineRecordArticle.discipline_record_id == DisciplineRecord.id,
            ).where(DisciplineRecordArticle.article_id == article_id)

        query = query.order_by(DisciplineRecord.date.desc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())
