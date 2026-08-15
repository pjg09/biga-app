from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]

    database_url: str
    redis_url: str

    secret_key: str
    algorithm: str = "HS256"
    pae_signing_secret: str

    @field_validator("secret_key", "pae_signing_secret")
    @classmethod
    def secret_key_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("secret_key must be at least 32 characters")
        return v
    access_token_expire_minutes: int = 480

    # URL pública del frontend. Se usa para construir los enlaces de
    # justificación de inasistencia que se envían por correo al acudiente.
    frontend_url: str = "http://localhost:5173"

    # Minutos de gracia tras tomar lista en la primera hora antes de notificar
    # la inasistencia. Si el estudiante llega dentro de la ventana, el docente
    # lo marca como tardanza y no se envía correo. Bajar en dev para probar.
    attendance_grace_minutes: int = 50

    storage_endpoint_url: str
    storage_public_url: str = ""  # URL accesible desde el browser; si vacía usa storage_endpoint_url
    storage_access_key: str
    storage_secret_key: str
    storage_bucket_name: str
    storage_region: str = "us-east-1"

    # ── Correo ──────────────────────────────────────────────────────
    # Proveedor activo: `resend` entrega de verdad; `mailtrap` captura todo en
    # una bandeja de pruebas compartida y NO entrega a nadie.
    #
    # El default es `resend` a propósito y no se deduce de `debug` ni de ninguna
    # otra señal de entorno: un despliegue que cayera en `mailtrap` por
    # inferencia desviaría en silencio los correos de acudientes reales
    # (justificaciones, avisos del PAE) a un buzón interno, y los notifiers lo
    # registrarían como `SENT`. Encenderlo tiene que ser un acto explícito.
    email_provider: str = "resend"

    resend_api_key: str
    email_from: str

    # Solo se usan con email_provider=mailtrap.
    mailtrap_host: str = "sandbox.smtp.mailtrap.io"
    mailtrap_port: int = 2525
    mailtrap_user: str = ""
    mailtrap_password: str = ""

    @field_validator("email_provider")
    @classmethod
    def known_email_provider(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in {"resend", "mailtrap"}:
            raise ValueError("EMAIL_PROVIDER debe ser 'resend' o 'mailtrap'")
        return v

    @model_validator(mode="after")
    def mailtrap_needs_credentials(self) -> "Settings":
        # Falla al arrancar y no en el primer envío: si no, el error aparecería
        # dentro de un job de Celery, donde solo se ve rebuscando en los logs
        # del worker y con los correos ya perdidos.
        if self.email_provider == "mailtrap" and not (self.mailtrap_user and self.mailtrap_password):
            raise ValueError(
                "EMAIL_PROVIDER=mailtrap requiere MAILTRAP_USER y MAILTRAP_PASSWORD"
            )
        return self

    # Buzón interno que recibe el aviso de cada solicitud de demo de la landing.
    # Con `biga.app` sin verificar en Resend, este correo debe ser el de la cuenta
    # dueña de Resend o el envío devuelve 403.
    leads_notify_email: str

    # Solicitudes de demo permitidas por IP en `leads_rate_limit_window_seconds`.
    # El endpoint es público: sin esto es un amplificador de correo gratuito.
    leads_rate_limit_max: int = 5
    leads_rate_limit_window_seconds: int = 3600

    # Tamaño máximo del soporte que el acudiente adjunta a una justificación.
    # El endpoint es público: sin tope, un token válido permite subir un archivo
    # arbitrariamente grande al bucket.
    justification_max_upload_mb: int = 5

    # Tamaño máximo de una foto de perfil (estudiante o personal). Estos
    # endpoints sí exigen JWT, así que el riesgo es menor que en la
    # justificación pública, pero sin tope un solo POST puede llenar el bucket.
    photo_max_upload_mb: int = 5

    # ── Recuperación de contraseña ──────────────────────────────────
    # Ventana de vida del código OTP enviado por correo.
    password_reset_otp_ttl_minutes: int = 10
    # Vida del token que habilita el cambio de contraseña, emitido al validar
    # el OTP. Corto: es el equivalente a una sesión con permiso para cambiar
    # credenciales.
    password_reset_token_ttl_minutes: int = 15
    # Intentos fallidos antes de inutilizar el código. Con 6 dígitos y 5
    # intentos, la probabilidad de acertar a ciegas es 5 en 1.000.000.
    password_reset_max_attempts: int = 5
    # Solicitudes de código por IP y hora. El endpoint es público y manda
    # correo: sin límite es un amplificador de spam contra terceros.
    password_reset_rate_limit_max: int = 5
    password_reset_rate_limit_window_seconds: int = 3600
    # Intentos de validación por IP y hora, además del contador por código.
    # Frena el barrido de códigos usando muchas cuentas distintas.
    password_reset_verify_rate_limit_max: int = 20

settings = Settings()
