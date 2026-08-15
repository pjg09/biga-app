from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grade import Grade
from app.models.group import Group
from app.models.student import Student
from app.models.student_group import StudentGroup
from app.models.subject import Subject
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

    async def get_by_id(
        self, student_id: UUID, institution_id: UUID, include_inactive: bool = False
    ) -> Student | None:
        # `include_inactive` solo lo usa la reactivación desde la consola del
        # admin: para volver a activar a alguien hay que poder leerlo primero.
        stmt = select(Student).where(
            Student.id == student_id,
            Student.institution_id == institution_id,
        )
        if not include_inactive:
            stmt = stmt.where(Student.is_active == True)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_institution(
        self,
        institution_id: UUID,
        grade_id: UUID | None = None,
        group_id: UUID | None = None,
        include_inactive: bool = False,
    ) -> list[tuple[Student, str | None, str | None]]:
        # LEFT JOIN (no INNER): un estudiante sin matrícula activa debe seguir
        # apareciendo en el listado del admin, solo que sin grado/salón. El
        # mismo patrón de join que `search()`, pero sin su `limit` — este
        # método alimenta el listado completo de gestión, no un autocompletado.
        stmt = (
            select(Student, Group.name, Grade.name)
            .outerjoin(
                StudentGroup,
                (StudentGroup.student_id == Student.id) & (StudentGroup.is_active == True),
            )
            .outerjoin(Group, Group.id == StudentGroup.group_id)
            .outerjoin(Grade, Grade.id == Group.grade_id)
            .where(Student.institution_id == institution_id)
            .order_by(Student.last_name, Student.first_name)
        )
        if not include_inactive:
            stmt = stmt.where(Student.is_active == True)
        if grade_id:
            stmt = stmt.where(Group.grade_id == grade_id)
        if group_id:
            stmt = stmt.where(StudentGroup.group_id == group_id)

        result = await self.session.execute(stmt)
        return [(row[0], row[2], row[1]) for row in result]  # (student, grade_name, group_name)

    async def list_for_teacher(
        self,
        institution_id: UUID,
        user_id: UUID,
        academic_year: int,
    ) -> list[tuple[Student, str | None, str | None, str | None]]:
        """Estudiantes de los salones asignados al docente en `user_groups`.

        El filtro es por **asignación docente-grupo**, no por horario: da igual
        que la clase sea primera hora o la última, y un docente sin ninguna
        clase hoy sigue viendo a sus estudiantes.

        No necesita `DISTINCT`: `student_groups` es UNIQUE(student_id,
        academic_year) y `user_groups` es UNIQUE(user_id, group_id,
        academic_year), así que ningún estudiante puede aparecer dos veces.

        Devuelve también `grade_name`/`group_name` (join informativo, no de
        aislamiento) y `subject`: el nombre de la materia (catálogo `subjects`,
        vía `user_groups.subject_id`) que ESTE docente dicta en ESE salón,
        para el filtro "materia" y la ficha de detalle del módulo de Aula.
        `outerjoin` porque `subject_id` es nullable — sin materia asignada,
        el estudiante igual debe aparecer en el listado.
        """
        result = await self.session.execute(
            select(Student, Grade.name, Group.name, Subject.name)
            .join(
                StudentGroup,
                (StudentGroup.student_id == Student.id) & (StudentGroup.is_active == True),
            )
            .join(UserGroup, UserGroup.group_id == StudentGroup.group_id)
            .join(Group, Group.id == StudentGroup.group_id)
            .join(Grade, Grade.id == Group.grade_id)
            .outerjoin(Subject, Subject.id == UserGroup.subject_id)
            .where(
                Student.institution_id == institution_id,
                Student.is_active == True,
                StudentGroup.academic_year == academic_year,
                UserGroup.user_id == user_id,
                UserGroup.academic_year == academic_year,
            )
            .order_by(Student.last_name, Student.first_name)
        )
        return [(row[0], row[1], row[2], row[3]) for row in result]  # (student, grade_name, group_name, subject)

    async def get_for_teacher(
        self,
        student_id: UUID,
        institution_id: UUID,
        user_id: UUID,
        academic_year: int,
    ) -> tuple[Student, str | None, str | None, str | None] | None:
        """Igual que `list_for_teacher` pero para un único estudiante (ficha de detalle).

        Mismo join/aislamiento: si el estudiante no está en un salón asignado
        a este docente, devuelve None (no distingue "no existe" de "no es tuyo",
        igual que `get_by_id`).
        """
        result = await self.session.execute(
            select(Student, Grade.name, Group.name, Subject.name)
            .join(
                StudentGroup,
                (StudentGroup.student_id == Student.id) & (StudentGroup.is_active == True),
            )
            .join(UserGroup, UserGroup.group_id == StudentGroup.group_id)
            .join(Group, Group.id == StudentGroup.group_id)
            .join(Grade, Grade.id == Group.grade_id)
            .outerjoin(Subject, Subject.id == UserGroup.subject_id)
            .where(
                Student.id == student_id,
                Student.institution_id == institution_id,
                Student.is_active == True,
                StudentGroup.academic_year == academic_year,
                UserGroup.user_id == user_id,
                UserGroup.academic_year == academic_year,
            )
        )
        row = result.first()
        return (row[0], row[1], row[2], row[3]) if row else None

    async def create(self, student: Student) -> Student:
        self.session.add(student)
        await self.session.flush()
        await self.session.refresh(student)
        return student

    async def update_photo(self, student: Student, key: str) -> Student:
        student.photo_url = key
        await self.session.flush()
        return student

    async def save(self, student: Student) -> Student:
        # Los campos ya se mutaron sobre el objeto (patrón de `update_photo`); esto
        # solo confirma el flush. `get_db()` hace commit/rollback de la unidad de
        # trabajo completa, este método no llama commit.
        await self.session.flush()
        return student

    async def get_by_id_with_group(
        self, student_id: UUID, institution_id: UUID
    ) -> tuple[Student, UUID | None, str | None, UUID | None, str | None] | None:
        """Estudiante + matrícula activa del año vigente, con IDs (no solo nombres):
        alimenta la ficha de detalle y el formulario de edición del admin, que
        necesitan preseleccionar el `<select>` de grado/salón, no solo mostrarlo.
        """
        result = await self.session.execute(
            select(Student, Grade.id, Grade.name, Group.id, Group.name)
            .outerjoin(
                StudentGroup,
                (StudentGroup.student_id == Student.id) & (StudentGroup.is_active == True),
            )
            .outerjoin(Group, Group.id == StudentGroup.group_id)
            .outerjoin(Grade, Grade.id == Group.grade_id)
            .where(Student.id == student_id, Student.institution_id == institution_id)
        )
        row = result.first()
        return (row[0], row[1], row[2], row[3], row[4]) if row else None

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
