"""Adapter de correo contra la bandeja de pruebas de Mailtrap.

Mailtrap Email Testing **captura** los correos en una bandeja web compartida en
vez de entregarlos al destinatario real. Sirve para que los product owners vean
exactamente lo que la app enviaría — asunto, HTML renderizado, destinatario
original — sin dominio verificado y sin dar de alta a cada persona.

Se habla SMTP con `smtplib` de la stdlib a propósito: no añade dependencia nueva
a `requirements.txt` y sirve igual para cualquier otro buzón SMTP (Mailhog en
local, por ejemplo) cambiando solo el host.

**Nunca en producción real**: aquí ningún acudiente recibe nada. El selector de
`config.py` deja `resend` por defecto justo para que esto haya que encenderlo a
mano.
"""
import smtplib
from email.message import EmailMessage

from app.core.config import settings


class MailtrapEmailAdapter:
    def send(self, to: str, subject: str, html: str) -> None:
        msg = EmailMessage()
        msg["From"] = settings.email_from
        msg["To"] = to
        msg["Subject"] = subject
        # El destinatario real ya va en la cabecera `To`, pero la bandeja es
        # compartida: esta cabecera propia facilita filtrar por persona sin
        # depender de cómo Mailtrap muestre el `To`.
        msg["X-BIGA-Original-To"] = to
        # Alternativa en texto plano para clientes que no renderizan HTML; el
        # cuerpo real es el HTML, idéntico al que se enviaría en producción.
        msg.set_content("Este mensaje requiere un cliente de correo con HTML.")
        msg.add_alternative(html, subtype="html")

        with smtplib.SMTP(settings.mailtrap_host, settings.mailtrap_port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(settings.mailtrap_user, settings.mailtrap_password)
            smtp.send_message(msg)
