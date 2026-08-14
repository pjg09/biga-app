from datetime import date
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.adapters.storage.s3 import S3StorageAdapter
from app.core.photos import resolve_photo_url
from app.jobs.departure_jobs import notify_early_departure
from app.models.departure import EarlyDeparture
from app.repositories.departure_repository import DepartureRepository
from app.repositories.student_repository import StudentRepository
from app.schemas.departures import DepartureCreate, DepartureResponse


class DepartureService:
    def __init__(
        self,
        repo: DepartureRepository,
        student_repo: StudentRepository,
        storage: S3StorageAdapter,
    ):
        self.repo = repo
        self.student_repo = student_repo
        self.storage = storage

    async def create_departure(
        self,
        data: DepartureCreate,
        institution_id: UUID,
        user_id: UUID,
    ) -> DepartureResponse:
        student = await self.student_repo.get_by_id(data.student_id, institution_id)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Estudiante no encontrado en esta institución",
            )

        departure = EarlyDeparture(
            id=uuid4(),
            student_id=data.student_id,
            institution_id=institution_id,
            recorded_by_user_id=user_id,
            departure_date=date.today(),
            departure_time=data.departure_time,
            reason=data.reason,
        )
        saved = await self.repo.create(departure)

        # Notifica al acudiente. El countdown corto evita la carrera con el
        # commit del request (get_db hace commit al salir del scope).
        notify_early_departure.apply_async((str(saved.id),), countdown=10)

        return DepartureResponse(
            id=saved.id,
            student_id=saved.student_id,
            student_name=f"{student.first_name} {student.last_name}",
            departure_date=saved.departure_date,
            departure_time=saved.departure_time,
            reason=saved.reason,
            created_at=saved.created_at,
        )

    async def list_today(self, institution_id: UUID, user_id: UUID) -> list[DepartureResponse]:
        rows = await self.repo.list_for_date(
            institution_id=institution_id, date=date.today(), recorded_by_user_id=user_id
        )
        return [
            DepartureResponse(
                id=d.id,
                student_id=d.student_id,
                student_name=name,
                photo_url=resolve_photo_url(self.storage, photo_key),
                departure_date=d.departure_date,
                departure_time=d.departure_time,
                reason=d.reason,
                created_at=d.created_at,
            )
            for d, name, photo_key in rows
        ]
