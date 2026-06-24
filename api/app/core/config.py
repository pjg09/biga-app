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


settings = Settings()
