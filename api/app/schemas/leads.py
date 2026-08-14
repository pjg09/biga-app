from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LeadCreate(BaseModel):
    # max_length 320 = límite real de una dirección RFC 5321 (64 local + @ + 255 dominio).
    email: EmailStr = Field(max_length=320)


class LeadResponse(BaseModel):
    """Respuesta del endpoint público.

    Deliberadamente mínima: no expone el id ni el estado de notificación, que
    son internos. El visitante solo necesita saber que su solicitud quedó
    registrada — y que el aviso interno salga o no es problema nuestro.
    """

    received: bool = True


class LeadItem(BaseModel):
    """Un lead visto desde la consola de administración."""

    id: UUID
    email: str
    source: str
    notification_status: str
    notification_error: str | None
    notified_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LeadsPage(BaseModel):
    items: list[LeadItem]
    total: int  # total de leads que cumplen el filtro, no solo los de esta página
    counts: dict[str, int]  # conteo por estado sobre TODOS los leads, sin filtrar
