import logging

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: Redis | None = None


def get_redis() -> Redis:
    """Cliente Redis compartido del proceso API.

    Se reutiliza el mismo Redis que ya usa Celery como broker: montar un store
    aparte solo para contar peticiones no se justifica.
    """
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def client_ip(request: Request) -> str:
    """IP del cliente, respetando el primer salto de `X-Forwarded-For`.

    En local no hay proxy delante y cae siempre en `request.client.host`. En
    producción detrás de un balanceador, el header es el único dato real — pero
    solo es de fiar si el proxy lo sobrescribe; si algún día se expone la API
    directo a internet, este valor lo puede falsificar el cliente.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def enforce_rate_limit(request: Request, bucket: str, max_hits: int, window_seconds: int) -> None:
    """Ventana fija por IP. Lanza 429 al superar `max_hits` dentro de la ventana.

    Si Redis no responde, **deja pasar la petición**: perder un lead por una
    caída de Redis es peor que aceptar un envío de más. El fallo queda en logs.
    """
    key = f"ratelimit:{bucket}:{client_ip(request)}"
    try:
        redis = get_redis()
        hits = await redis.incr(key)
        if hits == 1:
            await redis.expire(key, window_seconds)
    except Exception:  # noqa: BLE001
        logger.exception("Rate limit no aplicado (Redis inaccesible) para bucket %s", bucket)
        return

    if hits > max_hits:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Intenta de nuevo más tarde.",
        )
