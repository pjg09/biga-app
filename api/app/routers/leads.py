from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import enforce_rate_limit
from app.repositories.lead_repository import LeadRepository
from app.schemas.leads import LeadCreate, LeadResponse
from app.services.lead_service import LeadService

router = APIRouter(prefix="/leads", tags=["leads"])


def get_lead_service(db: AsyncSession = Depends(get_db)) -> LeadService:
    return LeadService(LeadRepository(db))


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    request: Request,
    body: LeadCreate,
    service: LeadService = Depends(get_lead_service),
):
    """Solicitud de demo desde la landing. **Endpoint público, sin JWT.**

    Quien lo llama es un visitante anónimo, así que no hay tenant ni usuario. La
    única protección es el rate limit por IP.
    """
    await enforce_rate_limit(
        request,
        bucket="leads",
        max_hits=settings.leads_rate_limit_max,
        window_seconds=settings.leads_rate_limit_window_seconds,
    )
    return await service.register_lead(body)
