from app.adapters.email.factory import get_email_adapter
from app.core.celery import celery_app
from app.services.password_reset_notifier import PasswordResetNotifier
from app.services.staff_welcome_notifier import StaffWelcomeNotifier


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
    PasswordResetNotifier(get_email_adapter()).notify(to_email, first_name, code, ttl_minutes)


@celery_app.task
def notify_staff_welcome(
    to_email: str, first_name: str, temp_password: str, role: str, login_url: str
) -> None:
    """Envía las credenciales iniciales a un miembro del personal recién creado.

    Va encolado y no dentro del request por la razón de siempre: la llamada HTTP
    a Resend bloquearía el event loop, y además el alta no debe fallar porque el
    proveedor de correo esté caído — el usuario ya quedó creado y puede entrar
    por `/recuperar`.

    Igual que el OTP, se encola con `argsrepr` desde el service para que la
    contraseña temporal **no aparezca en los logs del worker**. Y como el OTP,
    viaja en claro por Redis: en producción ese puerto no debe publicarse fuera
    de la red de Docker.
    """
    StaffWelcomeNotifier(get_email_adapter()).notify(
        to_email, first_name, temp_password, role, login_url
    )
