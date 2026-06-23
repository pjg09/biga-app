from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    compute_delivery_hash,
    compute_enrollment_hash,
    verify_delivery_hash,
    verify_enrollment_hash,
)
from app.models.enums import PAEIdentificationMethod
from app.models.pae import PAEDelivery, PAEEnrollment
from app.repositories.pae_repository import PAERepository
from app.schemas.pae import (
    PAEAuditItem,
    PAEAuditResponse,
    PAEDeliveryResponse,
    PAEEnrollmentResponse,
    PAEStudentListItem,
    PAEWeeklyReportItem,
    PAEWeeklyReportResponse,
)
from app.services.pae_strategies import DocumentSearchStrategy, FacialRecognitionStrategy, PAEIdentificationStrategy


def _get_strategy(method: PAEIdentificationMethod) -> PAEIdentificationStrategy:
    if method == PAEIdentificationMethod.FACIAL:
        return FacialRecognitionStrategy()
    return DocumentSearchStrategy()


class PAEService:
    def __init__(self, repo: PAERepository, session: AsyncSession):
        self.repo = repo
        self.session = session

    async def list_students_today(
        self,
        institution_id: UUID,
        academic_year: int,
        delivery_date: date,
    ) -> list[PAEStudentListItem]:
        pairs = await self.repo.get_enrolled_students_with_delivery_status(
            institution_id=institution_id,
            academic_year=academic_year,
            delivery_date=delivery_date,
        )
        return [
            PAEStudentListItem(
                student_id=student.id,
                document_number=student.document_number,
                first_name=student.first_name,
                last_name=student.last_name,
                photo_url=student.photo_url,
                delivered=delivered,
            )
            for student, delivered in pairs
        ]

    async def enroll_student(
        self,
        student_id: UUID,
        institution_id: UUID,
        academic_year: int,
    ) -> PAEEnrollmentResponse:
        student = await self.repo.get_active_student(
            student_id=student_id,
            institution_id=institution_id,
        )
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Estudiante no encontrado en esta institución",
            )

        existing = await self.repo.get_any_enrollment(
            student_id=student_id,
            institution_id=institution_id,
            academic_year=academic_year,
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El estudiante ya está inscrito en el PAE para este año académico",
            )

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        enrollment_hash = compute_enrollment_hash(
            student_id=student_id,
            institution_id=institution_id,
            academic_year=academic_year,
            enrolled_at=now,
        )

        enrollment = PAEEnrollment(
            id=uuid4(),
            student_id=student_id,
            institution_id=institution_id,
            academic_year=academic_year,
            is_active=True,
            enrolled_at=now,
            enrollment_hash=enrollment_hash,
        )
        saved = await self.repo.create_enrollment(enrollment)
        return PAEEnrollmentResponse.model_validate(saved)

    async def register_delivery(
        self,
        student_id: UUID,
        identification_method: PAEIdentificationMethod,
        delivered_by_user_id: UUID,
        institution_id: UUID,
        academic_year: int,
    ) -> PAEDeliveryResponse:
        strategy = _get_strategy(identification_method)
        student = await strategy.identify(
            input_data={"student_id": student_id},
            institution_id=institution_id,
            session=self.session,
        )

        enrollment = await self.repo.get_enrollment(
            student_id=student.id,
            institution_id=institution_id,
            academic_year=academic_year,
        )
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El estudiante no está inscrito en el PAE para este año académico",
            )

        # Capa 1 de la cadena: la inscripción debe ser íntegra antes de habilitar
        # una entrega. Si su hash no coincide, la fila fue manipulada en la BD y
        # se rechaza la entrega en lugar de encadenar sobre un dato corrupto.
        if not verify_enrollment_hash(
            student_id=enrollment.student_id,
            institution_id=enrollment.institution_id,
            academic_year=enrollment.academic_year,
            enrolled_at=enrollment.enrolled_at,
            stored_hash=enrollment.enrollment_hash,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La inscripción PAE del estudiante está comprometida. Contacte al administrador.",
            )

        today = date.today()
        existing = await self.repo.get_delivery_today(
            student_id=student.id,
            institution_id=institution_id,
            delivery_date=today,
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El estudiante ya recibió su entrega PAE hoy",
            )

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # Capa 2 de la cadena: el hash de la entrega incorpora el de la
        # inscripción, atando la entrega a la inscripción exacta que la habilitó.
        delivery_hash = compute_delivery_hash(
            student_id=student.id,
            delivery_date=today,
            delivered_by_user_id=delivered_by_user_id,
            created_at=now,
            enrollment_hash=enrollment.enrollment_hash,
        )

        delivery = PAEDelivery(
            id=uuid4(),
            student_id=student.id,
            institution_id=institution_id,
            delivered_by_user_id=delivered_by_user_id,
            delivery_date=today,
            identification_method=identification_method,
            delivery_hash=delivery_hash,
            created_at=now,
        )
        saved = await self.repo.create_delivery(delivery)
        return PAEDeliveryResponse.model_validate(saved)

    async def weekly_report(self, institution_id: UUID) -> PAEWeeklyReportResponse:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())  # lunes
        week_end = week_start + timedelta(days=4)  # viernes
        counts = await self.repo.get_delivery_counts_between(
            institution_id=institution_id,
            start_date=week_start,
            end_date=week_end,
        )
        by_date = {d: c for d, c in counts}
        items = [
            PAEWeeklyReportItem(
                delivery_date=week_start + timedelta(days=offset),
                count=by_date.get(week_start + timedelta(days=offset), 0),
            )
            for offset in range(5)
        ]
        return PAEWeeklyReportResponse(
            week_start=week_start,
            week_end=week_end,
            total=sum(item.count for item in items),
            items=items,
        )

    async def audit_deliveries(self, institution_id: UUID) -> PAEAuditResponse:
        pairs = await self.repo.get_all_deliveries_for_audit(institution_id=institution_id)
        records = []
        tampered = 0
        for d, enrollment in pairs:
            # Capa 1: la inscripción existe y su hash coincide.
            enrollment_valid = enrollment is not None and verify_enrollment_hash(
                student_id=enrollment.student_id,
                institution_id=enrollment.institution_id,
                academic_year=enrollment.academic_year,
                enrolled_at=enrollment.enrolled_at,
                stored_hash=enrollment.enrollment_hash,
            )
            # Capa 2: el hash de la entrega coincide usando el hash de
            # inscripción almacenado (el que se usó al crearla). Si la
            # inscripción desapareció, la cadena está rota por definición.
            delivery_valid = enrollment is not None and verify_delivery_hash(
                student_id=d.student_id,
                delivery_date=d.delivery_date,
                delivered_by_user_id=d.delivered_by_user_id,
                created_at=d.created_at,
                enrollment_hash=enrollment.enrollment_hash,
                stored_hash=d.delivery_hash,
            )
            chain_valid = enrollment_valid and delivery_valid
            if not chain_valid:
                tampered += 1
            records.append(
                PAEAuditItem(
                    delivery_id=d.id,
                    student_id=d.student_id,
                    delivery_date=d.delivery_date,
                    delivered_by_user_id=d.delivered_by_user_id,
                    enrollment_hash_valid=enrollment_valid,
                    delivery_hash_valid=delivery_valid,
                    hash_valid=chain_valid,
                )
            )
        return PAEAuditResponse(total=len(records), tampered=tampered, records=records)
