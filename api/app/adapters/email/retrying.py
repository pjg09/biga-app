"""Reintento con backoff alrededor de cualquier `EmailAdapter`.

Los proveedores de correo limitan por tasa y **el límite se alcanza en la
operación normal**, no en un pico raro: al notificar el no reclamo del PAE se
envía un correo por inscrito, y con 14 estudiantes Mailtrap ya devolvió
`550 5.7.0 Too many emails per second` en 12 de ellos. Resend limita igual
(2 req/s en el plan gratuito). Sin reintento, esos 12 avisos se pierden para
siempre: un `FAILED` no se reencola y no hay pantalla para reenviarlo.

Envuelve al adaptador real en vez de tocar cada notifier: la frontera sigue
siendo el Protocol `EmailAdapter` y todos los tipos de notificación —PAE,
inasistencia, convivencia, salidas, contraseñas— heredan el comportamiento.

**Solo reintenta lo transitorio.** Una dirección inválida o una API key mala no
mejoran esperando; gastar tres intentos en ellas retrasa la cola sin motivo y
esconde el error real detrás de un log repetido.
"""
import logging
import random
import time

from app.adapters.email.base import EmailAdapter

logger = logging.getLogger(__name__)

# Marcas de "vuelve a intentarlo" en el texto del error. Se mira la cadena y no
# el tipo porque cada proveedor levanta la suya (`SMTPDataError` de smtplib con
# Mailtrap, errores HTTP del SDK con Resend) y el Protocol no las unifica.
TRANSIENT_MARKERS = (
    "too many", "rate limit", "ratelimit", "429",
    "timeout", "timed out", "temporarily", "try again",
    "502", "503", "504", "connection reset", "connection aborted",
)


def is_transient(exc: Exception) -> bool:
    return any(m in str(exc).lower() for m in TRANSIENT_MARKERS)


class RetryingEmailAdapter:
    """Decorador de `EmailAdapter` con backoff exponencial y jitter.

    El jitter no es adorno: sin él, varios envíos que chocan contra el mismo
    límite reintentan exactamente a la vez y vuelven a chocar todos juntos.
    """

    def __init__(self, inner: EmailAdapter, attempts: int = 3, base_delay: float = 0.6):
        self.inner = inner
        self.attempts = max(1, attempts)
        self.base_delay = base_delay

    def send(self, to: str, subject: str, html: str) -> None:
        for intento in range(1, self.attempts + 1):
            try:
                self.inner.send(to, subject, html)
                if intento > 1:
                    logger.info("Correo enviado en el intento %s de %s", intento, self.attempts)
                return
            except Exception as exc:  # noqa: BLE001 — se reenvía abajo si no toca reintentar
                ultimo = intento == self.attempts
                if ultimo or not is_transient(exc):
                    # Se propaga tal cual: el notifier la registra como FAILED
                    # con su mensaje original, que es lo que se ve en la consola.
                    raise
                espera = self.base_delay * (2 ** (intento - 1)) + random.uniform(0, 0.4)
                logger.warning(
                    "Envío rechazado (%s); reintento %s/%s en %.1fs",
                    exc, intento + 1, self.attempts, espera,
                )
                time.sleep(espera)
