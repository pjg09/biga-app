from datetime import date
from uuid import UUID

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pae import PAEDelivery, PAEEnrollment
from app.models.student import Student


class PAERepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_enrolled_students_with_delivery_status(
        self,
        institution_id: UUID,
        academic_year: int,
        delivery_date: date,
    ) -> list[tuple[Student, bool]]:
        enrollments_q = await self.session.execute(
            select(Student)
            .join(PAEEnrollment, PAEEnrollment.student_id == Student.id)
            .where(
                PAEEnrollment.institution_id == institution_id,
                PAEEnrollment.academic_year == academic_year,
                PAEEnrollment.is_active == True,
                Student.institution_id == institution_id,
                Student.is_active == True,
            )
        )
        students = list(enrollments_q.scalars().all())

        if not students:
            return []

        student_ids = [s.id for s in students]
        deliveries_q = await self.session.execute(
            select(PAEDelivery.student_id).where(
                PAEDelivery.institution_id == institution_id,
                PAEDelivery.delivery_date == delivery_date,
                PAEDelivery.student_id.in_(student_ids),
            )
        )
        delivered_ids = set(deliveries_q.scalars().all())

        return [(s, s.id in delivered_ids) for s in students]

    async def get_active_student(
        self,
        student_id: UUID,
        institution_id: UUID,
    ) -> Student | None:
        result = await self.session.execute(
            select(Student).where(
                Student.id == student_id,
                Student.institution_id == institution_id,
                Student.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_enrollment(
        self,
        student_id: UUID,
        institution_id: UUID,
        academic_year: int,
    ) -> PAEEnrollment | None:
        result = await self.session.execute(
            select(PAEEnrollment).where(
                PAEEnrollment.student_id == student_id,
                PAEEnrollment.institution_id == institution_id,
                PAEEnrollment.academic_year == academic_year,
                PAEEnrollment.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_any_enrollment(
        self,
        student_id: UUID,
        institution_id: UUID,
        academic_year: int,
    ) -> PAEEnrollment | None:
        # Incluye inscripciones inactivas: la constraint UNIQUE(student_id,
        # academic_year) impide reinscribir aunque la previa esté desactivada.
        result = await self.session.execute(
            select(PAEEnrollment).where(
                PAEEnrollment.student_id == student_id,
                PAEEnrollment.institution_id == institution_id,
                PAEEnrollment.academic_year == academic_year,
            )
        )
        return result.scalar_one_or_none()

    async def create_enrollment(self, enrollment: PAEEnrollment) -> PAEEnrollment:
        self.session.add(enrollment)
        await self.session.flush()
        await self.session.refresh(enrollment)
        return enrollment

    async def get_delivery_today(
        self,
        student_id: UUID,
        institution_id: UUID,
        delivery_date: date,
    ) -> PAEDelivery | None:
        result = await self.session.execute(
            select(PAEDelivery).where(
                PAEDelivery.student_id == student_id,
                PAEDelivery.institution_id == institution_id,
                PAEDelivery.delivery_date == delivery_date,
            )
        )
        return result.scalar_one_or_none()

    async def create_delivery(self, delivery: PAEDelivery) -> PAEDelivery:
        self.session.add(delivery)
        await self.session.flush()
        await self.session.refresh(delivery)
        return delivery

    async def get_all_deliveries_for_audit(
        self,
        institution_id: UUID,
    ) -> list[tuple[PAEDelivery, PAEEnrollment | None]]:
        # Une cada entrega con la inscripción que la habilitó (por estudiante y
        # año académico = año de la entrega). El LEFT JOIN deja en None las
        # entregas cuya inscripción fue borrada: eso también es manipulación y
        # la auditoría lo marca como cadena rota.
        result = await self.session.execute(
            select(PAEDelivery, PAEEnrollment)
            .outerjoin(
                PAEEnrollment,
                (PAEEnrollment.student_id == PAEDelivery.student_id)
                & (PAEEnrollment.academic_year == extract("year", PAEDelivery.delivery_date))
                & (PAEEnrollment.institution_id == PAEDelivery.institution_id),
            )
            .where(PAEDelivery.institution_id == institution_id)
            .order_by(PAEDelivery.delivery_date.desc())
        )
        return [(row[0], row[1]) for row in result.all()]

    async def get_delivery_counts_between(
        self,
        institution_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[tuple[date, int]]:
        result = await self.session.execute(
            select(PAEDelivery.delivery_date, func.count())
            .where(
                PAEDelivery.institution_id == institution_id,
                PAEDelivery.delivery_date >= start_date,
                PAEDelivery.delivery_date <= end_date,
            )
            .group_by(PAEDelivery.delivery_date)
            .order_by(PAEDelivery.delivery_date)
        )
        return [(row[0], row[1]) for row in result.all()]
