from pydantic import field_validator
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

    resend_api_key: str
    email_from: str

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

    # Correos que pueden leer `GET /admin/leads` (JSON array). Los leads no
    # pertenecen a ninguna institución, así que sin esta lista **cualquier ADMIN
    # de cualquier institución cliente vería el pipeline comercial completo**.
    # Vacío = cualquier ADMIN puede verlos; aceptable solo mientras haya una
    # única institución en la BD. Llenar antes de dar de alta a la segunda.
    leads_admin_emails: list[str] = []


settings = Settings()
