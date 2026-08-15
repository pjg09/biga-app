"""Único punto donde se elige el proveedor de correo.

Los jobs piden `get_email_adapter()` en vez de instanciar un proveedor concreto:
así el Protocol `EmailAdapter` sigue siendo la frontera y cambiar de proveedor
no toca ningún notifier ni ningún job.

Se resuelve en cada llamada, no en import: los jobs corren en el worker, que
vive mucho tiempo, y así un cambio de `EMAIL_PROVIDER` solo necesita reiniciar
el proceso y no razonar sobre qué se importó primero.
"""
import logging

from app.adapters.email.base import EmailAdapter
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_email_adapter() -> EmailAdapter:
    if settings.email_provider == "mailtrap":
        from app.adapters.email.mailtrap import MailtrapEmailAdapter

        # Se registra en cada envío a propósito: si alguien deja esto encendido
        # donde no debe, el rastro tiene que ser imposible de pasar por alto.
        logger.warning(
            "EMAIL_PROVIDER=mailtrap — los correos se capturan en la bandeja de "
            "pruebas y NO llegan a ningún destinatario real."
        )
        return MailtrapEmailAdapter()

    from app.adapters.email.resend import ResendEmailAdapter

    return ResendEmailAdapter()
