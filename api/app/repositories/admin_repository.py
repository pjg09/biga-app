from datetime import date as PyDate
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agendatorio import ConvivenciaArticle, DisciplineRecord, DisciplineRecordArticle
from app.models.attendance import AttendanceRecord
from app.models.departure import EarlyDeparture
from app.models.notification import NotificationLog
from app.models.pae import PAEDelivery, PAEEnrollment
from app.models.student import Student
from app.models.user import User


class AdminRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _scalar_count(self, stmt) -> int:
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def count_active_students(self, institution_id: UUID) -> int:
        return await self._scalar_count(
            select(func.count()).select_from(Student).where(
                Student.institution_id == institution_id,
                Student.is_active == True,
            )
        )

    async def count_users_by_role(self, institution_id: UUID) -> dict[str, int]:
        result = await self.session.execute(
            select(User.role, func.count())
            .where(User.institution_id == institution_id, User.is_active == True)
            .group_by(User.role)
        )
        return {str(row[0].value if hasattr(row[0], "value") else row[0]): row[1] for row in result.all()}

    async def count_pae_enrolled(self, institution_id: UUID, academic_year: int) -> int:
        return await self._scalar_count(
            select(func.count()).select_from(PAEEnrollment).where(
                PAEEnrollment.institution_id == institution_id,
                PAEEnrollment.academic_year == academic_year,
                PAEEnrollment.is_active == True,
            )
        )

    async def count_pae_deliveries_between(
        self, institution_id: UUID, start: PyDate, end: PyDate
    ) -> int:
        return await self._scalar_count(
            select(func.count()).select_from(PAEDelivery).where(
                PAEDelivery.institution_id == institution_id,
                PAEDelivery.delivery_date >= start,
                PAEDelivery.delivery_date <= end,
            )
        )

    async def attendance_counts_today(self, institution_id: UUID, day: PyDate) -> dict[str, int]:
        result = await self.session.execute(
            select(AttendanceRecord.status, func.count())
            .where(
                AttendanceRecord.institution_id == institution_id,
                AttendanceRecord.date == day,
            )
            .group_by(AttendanceRecord.status)
        )
        return {str(row[0].value if hasattr(row[0], "value") else row[0]): row[1] for row in result.all()}

    async def count_departures_today(self, institution_id: UUID, day: PyDate) -> int:
        return await self._scalar_count(
            select(func.count()).select_from(EarlyDeparture).where(
                EarlyDeparture.institution_id == institution_id,
                EarlyDeparture.departure_date == day,
            )
        )

    async def count_discipline_records(self, institution_id: UUID) -> int:
        return await self._scalar_count(
            select(func.count()).select_from(DisciplineRecord).where(
                DisciplineRecord.institution_id == institution_id,
            )
        )

    async def discipline_severity_counts(self, institution_id: UUID) -> dict[str, int]:
        result = await self.session.execute(
            select(ConvivenciaArticle.severity, func.count())
            .join(DisciplineRecordArticle, DisciplineRecordArticle.article_id == ConvivenciaArticle.id)
            .join(DisciplineRecord, DisciplineRecord.id == DisciplineRecordArticle.discipline_record_id)
            .where(DisciplineRecord.institution_id == institution_id)
            .group_by(ConvivenciaArticle.severity)
        )
        return {str(row[0].value if hasattr(row[0], "value") else row[0]): row[1] for row in result.all()}

    async def notification_counts(self, institution_id: UUID) -> dict[str, int]:
        result = await self.session.execute(
            select(NotificationLog.status, func.count())
            .where(NotificationLog.institution_id == institution_id)
            .group_by(NotificationLog.status)
        )
        return {str(row[0].value if hasattr(row[0], "value") else row[0]): row[1] for row in result.all()}
