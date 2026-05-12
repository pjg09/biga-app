import resend

from app.core.config import settings


class ResendEmailAdapter:
    def send(self, to: str, subject: str, html: str) -> None:
        resend.api_key = settings.resend_api_key
        resend.Emails.send({
            "from": settings.email_from,
            "to": to,
            "subject": subject,
            "html": html,
        })
