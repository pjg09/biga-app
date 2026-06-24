from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.class_period import ClassPeriod
from app.models.grade import Grade
from app.models.group import Group
from app.models.student import Student
from app.models.student_group import StudentGroup
from app.models.user import User
from app.models.user_group import UserGroup


class AdminManagementRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _add(self, obj):
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    # --- Usuarios ---

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user(self, user_id: UUID, institution_id: UUID) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id, User.institution_id == institution_id)
        )
        return result.scalar_one_or_none()

    async def create_user(self, user: User) -> User:
        return await self._add(user)

    async def list_users(self, institution_id: UUID) -> list[User]:
        result = await self.session.execute(
            select(User)
            .where(User.institution_id == institution_id)
            .order_by(User.role, User.last_name, User.first_name)
        )
        return list(result.scalars().all())

    # --- Grados ---

    async def get_grade(self, grade_id: UUID, institution_id: UUID) -> Grade | None:
        result = await self.session.execute(
            select(Grade).where(Grade.id == grade_id, Grade.institution_id == institution_id)
        )
        return result.scalar_one_or_none()

    async def get_grade_by_level(self, institution_id: UUID, level: int) -> Grade | None:
        result = await self.session.execute(
            select(Grade).where(Grade.institution_id == institution_id, Grade.level == level)
        )
        return result.scalar_one_or_none()

    async def create_grade(self, grade: Grade) -> Grade:
        return await self._add(grade)

    async def list_grades(self, institution_id: UUID) -> list[Grade]:
        result = await self.session.execute(
            select(Grade).where(Grade.institution_id == institution_id).order_by(Grade.level)
        )
        return list(result.scalars().all())

    # --- Grupos ---

    async def get_group(self, group_id: UUID, institution_id: UUID) -> Group | None:
        result = await self.session.execute(
            select(Group).where(Group.id == group_id, Group.institution_id == institution_id)
        )
        return result.scalar_one_or_none()

    async def get_group_by_unique(self, grade_id: UUID, name: str, academic_year: int) -> Group | None:
        result = await self.session.execute(
            select(Group).where(
                Group.grade_id == grade_id,
                Group.name == name,
                Group.academic_year == academic_year,
            )
        )
        return result.scalar_one_or_none()

    async def create_group(self, group: Group) -> Group:
        return await self._add(group)

    async def list_groups(self, institution_id: UUID) -> list[tuple[Group, str]]:
        result = await self.session.execute(
            select(Group, Grade.name)
            .join(Grade, Grade.id == Group.grade_id)
            .where(Group.institution_id == institution_id)
            .order_by(Grade.level, Group.name)
        )
        return [(row[0], row[1]) for row in result.all()]

    # --- Matrícula estudiante-grupo ---

    async def get_student(self, student_id: UUID, institution_id: UUID) -> Student | None:
        result = await self.session.execute(
            select(Student).where(
                Student.id == student_id,
                Student.institution_id == institution_id,
                Student.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_student_group(self, student_id: UUID, academic_year: int) -> StudentGroup | None:
        result = await self.session.execute(
            select(StudentGroup).where(
                StudentGroup.student_id == student_id,
                StudentGroup.academic_year == academic_year,
            )
        )
        return result.scalar_one_or_none()

    async def create_student_group(self, sg: StudentGroup) -> StudentGroup:
        return await self._add(sg)

    # --- Horarios (class_periods) ---

    async def get_class_period_by_unique(
        self, group_id: UUID, period_order: int, day_of_week: int
    ) -> ClassPeriod | None:
        result = await self.session.execute(
            select(ClassPeriod).where(
                ClassPeriod.group_id == group_id,
                ClassPeriod.period_order == period_order,
                ClassPeriod.day_of_week == day_of_week,
            )
        )
        return result.scalar_one_or_none()

    async def create_class_period(self, cp: ClassPeriod) -> ClassPeriod:
        return await self._add(cp)

    async def list_class_periods(self, group_id: UUID, institution_id: UUID) -> list[ClassPeriod]:
        result = await self.session.execute(
            select(ClassPeriod)
            .where(
                ClassPeriod.group_id == group_id,
                ClassPeriod.institution_id == institution_id,
            )
            .order_by(ClassPeriod.day_of_week, ClassPeriod.start_time)
        )
        return list(result.scalars().all())

    # --- Asignación docente-grupo (user_groups) ---

    async def get_user_group(self, user_id: UUID, group_id: UUID, academic_year: int) -> UserGroup | None:
        result = await self.session.execute(
            select(UserGroup).where(
                UserGroup.user_id == user_id,
                UserGroup.group_id == group_id,
                UserGroup.academic_year == academic_year,
            )
        )
        return result.scalar_one_or_none()

    async def create_user_group(self, ug: UserGroup) -> UserGroup:
        return await self._add(ug)

    async def list_user_groups(self, institution_id: UUID) -> list[tuple[UserGroup, str]]:
        result = await self.session.execute(
            select(UserGroup, func.concat(User.first_name, " ", User.last_name))
            .join(User, User.id == UserGroup.user_id)
            .join(Group, Group.id == UserGroup.group_id)
            .where(Group.institution_id == institution_id)
            .order_by(UserGroup.academic_year.desc())
        )
        return [(row[0], row[1]) for row in result.all()]
