import logging

from app.adapters.email.base import EmailAdapter

logger = logging.getLogger(__name__)

ROLE_LABELS = {
    "TEACHER": "Docente",
    "PAE_OPERATOR": "Operador PAE",
    "ADMIN": "Administrador",
}


def _build_html(first_name: str, email: str, temp_password: str, role_label: str, login_url: str) -> str:
    return f"""\
<div style="font-family: system-ui, sans-serif; max-width: 520px; margin: 0 auto; color: #1a1730;">
  <h2 style="color: #4A0A9E;">Tu cuenta en BIGA está lista</h2>
  <p>Hola {first_name}, se creó tu cuenta con el perfil <strong>{role_label}</strong>.</p>
  <p>Entra con estos datos:</p>
  <div style="background: #F5F3FF; border-radius: 12px; padding: 18px; margin: 16px 0;">
    <p style="margin: 0 0 8px;"><strong>Correo:</strong> {email}</p>
    <p style="margin: 0;"><strong>Contraseña temporal:</strong>
      <code style="font-size: 17px; letter-spacing: 1px; color: #4A0A9E;">{temp_password}</code>
    </p>
  </div>
  <p style="margin: 20px 0;">
    <a href="{login_url}"
       style="background: #059669; color: #fff; text-decoration: none; font-weight: 700;
              padding: 12px 22px; border-radius: 10px; display: inline-block;">
      Entrar a BIGA
    </a>
  </p>
  <p style="font-size: 13px; color: #6b6880;">
    Por seguridad, cámbiala en cuanto entres: usa <strong>¿Olvidaste tu contraseña?</strong>
    en la pantalla de inicio de sesión. Esta contraseña viajó por correo, así que no deberías
    conservarla.
  </p>
  <p style="font-size: 13px; color: #6b6880;">
    Si no esperabas esta cuenta, avisa al administrador de tu institución.
  </p>
</div>"""


class StaffWelcomeNotifier:
    """Envía las credenciales iniciales a un miembro del personal recién creado.

    No toca la base de datos ni `notifications_log`, por la misma razón que
    `PasswordResetNotifier`: esa tabla exige `student_id`/`guardian_id` NOT NULL
    y aquí el destinatario es un usuario del staff.
    """

    def __init__(self, email: EmailAdapter):
        self.email = email

    def notify(
        self, to_email: str, first_name: str, temp_password: str, role: str, login_url: str
    ) -> None:
        subject = "Tu cuenta en BIGA — credenciales de acceso"
        html = _build_html(first_name, to_email, temp_password, ROLE_LABELS.get(role, role), login_url)
        try:
            self.email.send(to_email, subject, html)
        except Exception:  # noqa: BLE001
            # No se relanza: el usuario ya quedó creado y el admin recibió su 201.
            # Si el correo falla, el usuario puede entrar por `/recuperar` igual.
            logger.exception("Fallo enviando las credenciales de bienvenida")
