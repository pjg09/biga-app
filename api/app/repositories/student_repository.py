from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student import Student


class StudentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_document(
        self,
        institution_id: UUID,
        document_number: str,
    ) -> Student | None:
        result = await self.session.execute(
            select(Student).where(
                Student.institution_id == institution_id,
                Student.document_number == document_number,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self,
        institution_id: UUID,
        student_id: UUID,
    ) -> Student | None:
        result = await self.session.execute(
            select(Student).where(
                Student.id == student_id,
                Student.institution_id == institution_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_institution(
        self,
        institution_id: UUID,
    ) -> list[Student]:
        result = await self.session.execute(
            select(Student)
            .where(
                Student.institution_id == institution_id,
                Student.is_active == True,
            )
            .order_by(Student.last_name, Student.first_name)
        )
        return list(result.scalars().all())

    async def create(self, student: Student) -> Student:
        self.session.add(student)
        await self.session.flush()
        await self.session.refresh(student)
        return student
