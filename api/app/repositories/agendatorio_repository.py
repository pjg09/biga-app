from dataclasses import dataclass
from datetime import date as PyDate, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agendatorio import (
    ConvivenciaArticle,
    DisciplineRecord,
    DisciplineRecordArticle,
    DisciplineRecordNote,
)
from app.models.grade import Grade
from app.models.group import Group
from app.models.student import Student
from app.models.student_group import StudentGroup
from app.models.user import User


@dataclass
class MyRecordRow:
    record: DisciplineRecord
    student_name: str
    grade_name: str | None
    group_name: str | None


@dataclass
class RecordMeta:
    record: DisciplineRecord
    student_name: str
    grade_name: str | None
    group_name: str | None
    recorded_by_name: str


class AgendatorioRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Catálogo académico (grados/grupos) para los selectores de búsqueda ---

    async def list_grades(self, institution_id: UUID) -> list[Grade]:
        result = await self.session.execute(
            select(Grade).where(Grade.institution_id == institution_id).order_by(Grade.level)
        )
        return list(result.scalars().all())

    async def list_groups(self, institution_id: UUID) -> list[tuple[Group, str]]:
        result = await self.session.execute(
            select(Group, Grade.name)
            .join(Grade, Grade.id == Group.grade_id)
            .where(Group.institution_id == institution_id)
            .order_by(Grade.level, Group.name)
        )
        return [(row[0], row[1]) for row in result.all()]

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

    # --- Historial del docente (registros propios, notas, ocultar) ---

    async def list_my_records(
        self,
        user_id: UUID,
        institution_id: UUID,
        student_id: UUID | None,
        include_archived: bool,
        skip: int,
        limit: int,
    ) -> list[MyRecordRow]:
        stmt = (
            select(
                DisciplineRecord,
                func.concat(Student.first_name, " ", Student.last_name),
                Grade.name,
                Group.name,
            )
            .join(Student, Student.id == DisciplineRecord.student_id)
            .outerjoin(
                StudentGroup,
                (StudentGroup.student_id == Student.id) & (StudentGroup.is_active == True),
            )
            .outerjoin(Group, Group.id == StudentGroup.group_id)
            .outerjoin(Grade, Grade.id == Group.grade_id)
            .where(
                DisciplineRecord.institution_id == institution_id,
                DisciplineRecord.recorded_by_user_id == user_id,
            )
        )
        if student_id is not None:
            stmt = stmt.where(DisciplineRecord.student_id == student_id)
        if not include_archived:
            stmt = stmt.where(DisciplineRecord.archived_at.is_(None))
        stmt = (
            stmt.order_by(DisciplineRecord.date.desc(), DisciplineRecord.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [
            MyRecordRow(record=row[0], student_name=row[1], grade_name=row[2], group_name=row[3])
            for row in result.all()
        ]

    async def articles_by_records(
        self, record_ids: list[UUID]
    ) -> dict[UUID, list[ConvivenciaArticle]]:
        if not record_ids:
            return {}
        result = await self.session.execute(
            select(DisciplineRecordArticle.discipline_record_id, ConvivenciaArticle)
            .join(ConvivenciaArticle, ConvivenciaArticle.id == DisciplineRecordArticle.article_id)
            .where(DisciplineRecordArticle.discipline_record_id.in_(record_ids))
            .order_by(ConvivenciaArticle.code)
        )
        out: dict[UUID, list[ConvivenciaArticle]] = {}
        for record_id, article in result.all():
            out.setdefault(record_id, []).append(article)
        return out

    async def note_counts(self, record_ids: list[UUID]) -> dict[UUID, int]:
        if not record_ids:
            return {}
        result = await self.session.execute(
            select(DisciplineRecordNote.discipline_record_id, func.count())
            .where(DisciplineRecordNote.discipline_record_id.in_(record_ids))
            .group_by(DisciplineRecordNote.discipline_record_id)
        )
        return {row[0]: row[1] for row in result.all()}

    async def get_record_owned(
        self, record_id: UUID, user_id: UUID, institution_id: UUID
    ) -> DisciplineRecord | None:
        result = await self.session.execute(
            select(DisciplineRecord).where(
                DisciplineRecord.id == record_id,
                DisciplineRecord.institution_id == institution_id,
                DisciplineRecord.recorded_by_user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_record_meta(self, record_id: UUID, institution_id: UUID) -> RecordMeta | None:
        result = await self.session.execute(
            select(
                DisciplineRecord,
                func.concat(Student.first_name, " ", Student.last_name),
                Grade.name,
                Group.name,
                func.concat(User.first_name, " ", User.last_name),
            )
            .join(Student, Student.id == DisciplineRecord.student_id)
            .join(User, User.id == DisciplineRecord.recorded_by_user_id)
            .outerjoin(
                StudentGroup,
                (StudentGroup.student_id == Student.id) & (StudentGroup.is_active == True),
            )
            .outerjoin(Group, Group.id == StudentGroup.group_id)
            .outerjoin(Grade, Grade.id == Group.grade_id)
            .where(
                DisciplineRecord.id == record_id,
                DisciplineRecord.institution_id == institution_id,
            )
        )
        row = result.first()
        if not row:
            return None
        return RecordMeta(
            record=row[0], student_name=row[1], grade_name=row[2],
            group_name=row[3], recorded_by_name=row[4],
        )

    async def list_notes(self, record_id: UUID) -> list[tuple[DisciplineRecordNote, str]]:
        result = await self.session.execute(
            select(DisciplineRecordNote, func.concat(User.first_name, " ", User.last_name))
            .join(User, User.id == DisciplineRecordNote.author_user_id)
            .where(DisciplineRecordNote.discipline_record_id == record_id)
            .order_by(DisciplineRecordNote.created_at.asc())
        )
        return [(row[0], row[1]) for row in result.all()]

    async def add_note(self, note: DisciplineRecordNote) -> DisciplineRecordNote:
        self.session.add(note)
        await self.session.flush()
        return note

    async def get_user_name(self, user_id: UUID) -> str | None:
        result = await self.session.execute(
            select(func.concat(User.first_name, " ", User.last_name)).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def set_archived(self, record: DisciplineRecord, archived_at: datetime | None) -> DisciplineRecord:
        record.archived_at = archived_at
        await self.session.flush()
        return record
