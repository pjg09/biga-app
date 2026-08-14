from app.adapters.email.resend import ResendEmailAdapter
from app.core.celery import celery_app
from app.services.password_reset_notifier import PasswordResetNotifier


@celery_app.task
def notify_password_reset_code(
    to_email: str, first_name: str, code: str, ttl_minutes: int
) -> None:
    """Envía el OTP de recuperación.

    Se encola en vez de enviarse dentro del request por dos razones: la llamada
    HTTP a Resend bloquearía el event loop, y sobre todo el tiempo de respuesta
    del endpoint queda igual exista o no la cuenta — si un correo real tardase
    400 ms más que uno inexistente, el propio cronómetro delataría qué cuentas
    existen y la respuesta genérica no serviría de nada.

    Contrapartida asumida: el código viaja en claro por Redis. Es la misma
    exposición que el correo en sí, pero implica **no publicar el puerto de
    Redis fuera de la red de Docker en producción**.
    """
    PasswordResetNotifier(ResendEmailAdapter()).notify(to_email, first_name, code, ttl_minutes)
