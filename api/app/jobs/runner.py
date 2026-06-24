import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


def run_db_job(work: Callable[[AsyncSession], Awaitable[None]]) -> None:
    """Ejecuta una corrutina que necesita una sesión de BD desde una tarea Celery.

    Las tareas Celery son síncronas pero la BD del proyecto es async. Cada tarea
    levanta su propio engine con `NullPool` (sin reusar conexiones entre event
    loops, lo que rompería con asyncpg) y lo descarta al terminar. Igual que
    `get_db()`, hace commit al salir limpio y rollback ante excepción.
    """

    async def _run() -> None:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                try:
                    await work(session)
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
        finally:
            await engine.dispose()

    asyncio.run(_run())
