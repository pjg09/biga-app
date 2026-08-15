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
