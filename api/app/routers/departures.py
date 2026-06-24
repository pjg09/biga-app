from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_staff
from app.models.user import User
from app.repositories.departure_repository import DepartureRepository
from app.repositories.student_repository import StudentRepository
from app.schemas.departures import DepartureCreate, DepartureResponse
from app.services.departure_service import DepartureService

router = APIRouter(prefix="/departures", tags=["departures"])


def get_departure_service(db: AsyncSession = Depends(get_db)) -> DepartureService:
    return DepartureService(DepartureRepository(db), StudentRepository(db))


@router.post("", response_model=DepartureResponse, status_code=status.HTTP_201_CREATED)
async def create_departure(
    body: DepartureCreate,
    current_user: User = Depends(require_staff),
    service: DepartureService = Depends(get_departure_service),
):
    return await service.create_departure(
        data=body,
        institution_id=current_user.institution_id,
        user_id=current_user.id,
    )


@router.get("", response_model=list[DepartureResponse])
async def list_departures(
    current_user: User = Depends(require_staff),
    service: DepartureService = Depends(get_departure_service),
):
    return await service.list_today(institution_id=current_user.institution_id)
