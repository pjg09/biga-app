from dataclasses import dataclass
from datetime import date as PyDate
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.departure import EarlyDeparture
from app.models.student import Student


@dataclass
class DepartureContext:
    departure: EarlyDeparture
    student: Student


class DepartureRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, departure: EarlyDeparture) -> EarlyDeparture:
        self.session.add(departure)
        await self.session.flush()
        await self.session.refresh(departure)
        return departure

    async def list_for_date(
        self,
        institution_id: UUID,
        date: PyDate,
    ) -> list[tuple[EarlyDeparture, str, str | None]]:
        from sqlalchemy import func

        result = await self.session.execute(
            select(
                EarlyDeparture,
                func.concat(Student.first_name, " ", Student.last_name),
                Student.photo_url,
            )
            .join(Student, Student.id == EarlyDeparture.student_id)
            .where(
                EarlyDeparture.institution_id == institution_id,
                EarlyDeparture.departure_date == date,
            )
            .order_by(EarlyDeparture.departure_time.desc())
        )
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def get_context(self, departure_id: UUID) -> DepartureContext | None:
        result = await self.session.execute(
            select(EarlyDeparture, Student)
            .join(Student, Student.id == EarlyDeparture.student_id)
            .where(EarlyDeparture.id == departure_id)
        )
        row = result.first()
        if not row:
            return None
        return DepartureContext(departure=row[0], student=row[1])
