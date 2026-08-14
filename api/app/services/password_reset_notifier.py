import logging

from app.adapters.email.base import EmailAdapter

logger = logging.getLogger(__name__)


def _build_html(first_name: str, code: str, ttl_minutes: int) -> str:
    spaced = " ".join(code)  # "482913" -> "4 8 2 9 1 3", más fácil de transcribir
    return f"""\
<div style="font-family: system-ui, sans-serif; max-width: 520px; margin: 0 auto; color: #1a1730;">
  <h2 style="color: #4A0A9E;">Recuperación de contraseña</h2>
  <p>Hola {first_name}, recibimos una solicitud para restablecer la contraseña de tu cuenta BIGA.</p>
  <p>Tu código de verificación es:</p>
  <p style="font-size: 32px; font-weight: 700; letter-spacing: 6px; color: #4A0A9E;
            background: #F5F3FF; border-radius: 12px; padding: 18px; text-align: center;">
    {spaced}
  </p>
  <p style="font-size: 13px; color: #6b6880;">
    El código vence en {ttl_minutes} minutos y solo puede usarse una vez.
  </p>
  <p style="font-size: 13px; color: #6b6880;">
    Si no pediste este cambio, ignora este mensaje: tu contraseña actual sigue funcionando.
    Nadie puede cambiarla sin este código.
  </p>
</div>"""


class PasswordResetNotifier:
    """Envía el código OTP.

    No toca la base de datos, a diferencia del resto de notifiers: recibe todo
    por parámetro. Así el job no compite con el commit del request que lo encoló
    y no hay que retrasarlo — en un OTP la latencia se nota.

    Tampoco escribe en `notifications_log`: esa tabla exige `student_id` y
    `guardian_id` NOT NULL, y aquí el destinatario es un usuario del staff.
    """

    def __init__(self, email: EmailAdapter):
        self.email = email

    def notify(self, to_email: str, first_name: str, code: str, ttl_minutes: int) -> None:
        subject = "Tu código para restablecer la contraseña — BIGA"
        html = _build_html(first_name, code, ttl_minutes)
        try:
            self.email.send(to_email, subject, html)
        except Exception:  # noqa: BLE001
            # No se relanza: el usuario ya recibió un 200 genérico y reintentará.
            # El fallo tiene que quedar en los logs del worker.
            logger.exception("Fallo enviando el código de recuperación")
