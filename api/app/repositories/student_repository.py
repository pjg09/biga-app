from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grade import Grade
from app.models.group import Group
from app.models.student import Student
from app.models.student_group import StudentGroup


@dataclass
class StudentSearchRow:
    id: UUID
    full_name: str
    document_number: str
    photo_url: str | None
    group_name: str | None
    grade_name: str | None


class StudentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, student_id: UUID, institution_id: UUID) -> Student | None:
        result = await self.session.execute(
            select(Student).where(
                Student.id == student_id,
                Student.institution_id == institution_id,
                Student.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        q: str,
        institution_id: UUID,
        group_id: UUID | None = None,
        grade_id: UUID | None = None,
        limit: int = 20,
    ) -> list[StudentSearchRow]:
        stmt = (
            select(
                Student.id,
                func.concat(Student.first_name, " ", Student.last_name).label("full_name"),
                Student.document_number,
                Student.photo_url,
                Group.name.label("group_name"),
                Grade.name.label("grade_name"),
            )
            .outerjoin(
                StudentGroup,
                (StudentGroup.student_id == Student.id) & (StudentGroup.is_active == True),
            )
            .outerjoin(Group, Group.id == StudentGroup.group_id)
            .outerjoin(Grade, Grade.id == Group.grade_id)
            .where(
                Student.institution_id == institution_id,
                Student.is_active == True,
                or_(
                    func.concat(Student.first_name, " ", Student.last_name).ilike(f"%{q}%"),
                    Student.document_number.ilike(f"%{q}%"),
                ),
            )
            .limit(limit)
        )

        if group_id:
            stmt = stmt.where(StudentGroup.group_id == group_id)
        if grade_id:
            stmt = stmt.where(Group.grade_id == grade_id)

        result = await self.session.execute(stmt)
        return [
            StudentSearchRow(
                id=row.id,
                full_name=row.full_name,
                document_number=row.document_number,
                photo_url=row.photo_url,
                group_name=row.group_name,
                grade_name=row.grade_name,
            )
            for row in result
        ]
