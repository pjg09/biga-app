from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grade import Grade
from app.models.group import Group
from app.models.student import Student
from app.models.student_group import StudentGroup
from app.models.user_group import UserGroup


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

    async def get_by_id(self, student_id: UUID, institution_id: UUID) -> Student | None:
        result = await self.session.execute(
            select(Student).where(
                Student.id == student_id,
                Student.institution_id == institution_id,
                Student.is_active == True,
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

    async def list_for_teacher(
        self,
        institution_id: UUID,
        user_id: UUID,
        academic_year: int,
    ) -> list[Student]:
        """Estudiantes de los salones asignados al docente en `user_groups`.

        El filtro es por **asignación docente-grupo**, no por horario: da igual
        que la clase sea primera hora o la última, y un docente sin ninguna
        clase hoy sigue viendo a sus estudiantes.

        No necesita `DISTINCT`: `student_groups` es UNIQUE(student_id,
        academic_year) y `user_groups` es UNIQUE(user_id, group_id,
        academic_year), así que ningún estudiante puede aparecer dos veces.
        """
        result = await self.session.execute(
            select(Student)
            .join(
                StudentGroup,
                (StudentGroup.student_id == Student.id) & (StudentGroup.is_active == True),
            )
            .join(UserGroup, UserGroup.group_id == StudentGroup.group_id)
            .where(
                Student.institution_id == institution_id,
                Student.is_active == True,
                StudentGroup.academic_year == academic_year,
                UserGroup.user_id == user_id,
                UserGroup.academic_year == academic_year,
            )
            .order_by(Student.last_name, Student.first_name)
        )
        return list(result.scalars().all())

    async def create(self, student: Student) -> Student:
        self.session.add(student)
        await self.session.flush()
        await self.session.refresh(student)
        return student

    async def update_photo(self, student: Student, key: str) -> Student:
        student.photo_url = key
        await self.session.flush()
        return student

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
            )
            .order_by(Student.last_name, Student.first_name)
            .limit(limit)
        )

        term = (q or "").strip()
        if term:
            # Búsqueda insensible a acentos: unaccent() sobre columna y patrón
            # (ej. "Lopez" encuentra "López"). ILIKE cubre el caso de mayúsculas.
            pattern = func.unaccent(f"%{term}%")
            stmt = stmt.where(
                or_(
                    func.unaccent(func.concat(Student.first_name, " ", Student.last_name)).ilike(pattern),
                    func.unaccent(Student.document_number).ilike(pattern),
                )
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
