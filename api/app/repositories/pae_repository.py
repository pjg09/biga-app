from datetime import date, time
from uuid import UUID

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationType
from app.models.guardian import Guardian
from app.models.institution import Institution
from app.models.notification import NotificationLog
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

    # --- Job de notificación de no reclamo ---

    async def get_institution_ids_past_pae_end(self, current_time: time) -> list[UUID]:
        # Cross-tenant a propósito: es el barrido programado (beat) que decide qué
        # instituciones ya cerraron su horario de entrega hoy. El trabajo por
        # institución sí se hace con institution_id explícito.
        result = await self.session.execute(
            select(Institution.id).where(Institution.pae_delivery_end_time <= current_time)
        )
        return list(result.scalars().all())

    async def get_pae_delivery_end_time(self, institution_id: UUID) -> time | None:
        result = await self.session.execute(
            select(Institution.pae_delivery_end_time).where(Institution.id == institution_id)
        )
        return result.scalar_one_or_none()

    async def has_no_claim_notification_today(
        self,
        institution_id: UUID,
        student_id: UUID,
        delivery_date: date,
    ) -> bool:
        result = await self.session.execute(
            select(func.count())
            .select_from(NotificationLog)
            .where(
                NotificationLog.institution_id == institution_id,
                NotificationLog.student_id == student_id,
                NotificationLog.type == NotificationType.PAE_NO_CLAIM,
                func.date(NotificationLog.created_at) == delivery_date,
            )
        )
        return result.scalar_one() > 0

    async def get_primary_guardian(self, student_id: UUID) -> Guardian | None:
        result = await self.session.execute(
            select(Guardian).where(Guardian.student_id == student_id, Guardian.is_primary == True)
        )
        return result.scalar_one_or_none()

    async def count_deliveries_on(self, institution_id: UUID, delivery_date: date) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(PAEDelivery)
            .where(
                PAEDelivery.institution_id == institution_id,
                PAEDelivery.delivery_date == delivery_date,
            )
        )
        return result.scalar_one()

    async def get_no_claim_students_with_guardians(
        self,
        institution_id: UUID,
        academic_year: int,
        delivery_date: date,
    ) -> list[tuple[Student, Guardian]]:
        # Inscritos activos que hoy NO tienen entrega y a los que aún NO se les
        # notificó el no reclamo (idempotencia: el barrido puede correr varias
        # veces en la tarde). El JOIN a Guardian con is_primary excluye a los
        # estudiantes sin acudiente primario — no hay a quién notificar.
        delivered_subq = select(PAEDelivery.student_id).where(
            PAEDelivery.institution_id == institution_id,
            PAEDelivery.delivery_date == delivery_date,
        )
        notified_subq = select(NotificationLog.student_id).where(
            NotificationLog.institution_id == institution_id,
            NotificationLog.type == NotificationType.PAE_NO_CLAIM,
            func.date(NotificationLog.created_at) == delivery_date,
        )
        result = await self.session.execute(
            select(Student, Guardian)
            .join(PAEEnrollment, PAEEnrollment.student_id == Student.id)
            .join(Guardian, (Guardian.student_id == Student.id) & (Guardian.is_primary == True))
            .where(
                PAEEnrollment.institution_id == institution_id,
                PAEEnrollment.academic_year == academic_year,
                PAEEnrollment.is_active == True,
                Student.institution_id == institution_id,
                Student.is_active == True,
                Student.id.notin_(delivered_subq),
                Student.id.notin_(notified_subq),
            )
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
