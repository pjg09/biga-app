import logging
from datetime import datetime, timedelta
from uuid import uuid4

from app.jobs.lead_jobs import notify_demo_lead
from app.models.enums import NotificationStatus
from app.models.lead import DemoLead
from app.repositories.lead_repository import LeadRepository
from app.schemas.leads import LeadCreate, LeadResponse

logger = logging.getLogger(__name__)

# Ventana de supresión: si el mismo correo ya pidió demo dentro de este plazo,
# el lead se guarda igual pero no se manda un aviso nuevo. Evita que alguien
# pulsando el botón veinte veces llene el buzón interno.
DUPLICATE_WINDOW = timedelta(hours=24)


class LeadService:
    def __init__(self, repo: LeadRepository):
        self.repo = repo

    async def register_lead(self, data: LeadCreate, source: str = "LANDING_CTA") -> LeadResponse:
        email = str(data.email).strip().lower()

        # El conteo va antes del insert para que la propia fila nueva no cuente.
        recent = await self.repo.count_recent_by_email(email, datetime.now() - DUPLICATE_WINDOW)

        is_duplicate = recent > 0
        lead = DemoLead(
            id=uuid4(),
            email=email,
            source=source,
            # SUPPRESSED deja constancia de que no se intentó enviar a propósito.
            # Dejarlo en PENDING lo haría indistinguible de un worker caído.
            notification_status=(
                NotificationStatus.SUPPRESSED if is_duplicate else NotificationStatus.PENDING
            ),
        )
        saved = await self.repo.create(lead)

        if is_duplicate:
            logger.info(
                "Lead %s duplicado en las últimas 24h (%s solicitudes previas); no se avisa",
                saved.id,
                recent,
            )
        else:
            # countdown corto: el job lee el lead de la BD y get_db aún no ha
            # hecho commit al salir del request. Mismo patrón que departures.
            notify_demo_lead.apply_async((str(saved.id),), countdown=10)

        # Siempre `received: true`: el visitante no debe distinguir un lead nuevo
        # de uno duplicado, ni enterarse de si el aviso interno salió.
        return LeadResponse()
