# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Expected behavior

Challenge the developer's way of thinking, don't validate it. When a plan or technical decision is proposed:

- Point out flaws, edge cases and blind spots
- Disagree when the logic is weak or there are unsupported assumptions
- Say directly when something is a bad idea, instead of making it work anyway

No encouragement or positivity needed. Critical thinking and direct corrections are needed.

## Stack tecnológico

- **Backend**: Python + FastAPI + Pydantic v2 + SQLAlchemy 2.x async + Alembic
- **Frontend**: React + Vite
- **Base de datos**: PostgreSQL con `institution_id` en todas las tablas operativas (multi-tenant desde el inicio)
- **Jobs**: Celery 5.x + Redis
- **Storage**: Adapter S3-compatible (MinIO en local, S3 en prod — intercambiable por variable de entorno)
- **Email**: Resend (reemplazable vía Adapter)

## Arquitectura

El proyecto usa **monolito por capas**: Router → Service → Repository. La arquitectura detallada vive en `docs/architecture.md`.

Restricciones que no deben violarse:
- Ninguna capa se salta la inmediatamente siguiente. Un Router nunca toca el Repository directamente.
- No microservicios, no DDD, no Clean Architecture — decisión explícita documentada en `docs/architecture.md`.
- Los Services no instancian sus dependencias internamente. Todo se inyecta vía `Depends()` de FastAPI.

## Patrones en uso

- **Strategy**: módulo PAE usa `PAEIdentificationStrategy` (documento en MVP, facial recognition en fase 2).
- **Adapter**: email y storage se abstraen detrás de un Protocol. Nunca se llama directamente al SDK del proveedor desde un Service.

## Convenciones de base de datos

- Todos los IDs son `UUID` generados en la aplicación. Nunca usar `SERIAL` o `BIGSERIAL`.
- Todo cambio al esquema debe reflejarse en `docs/database-schema.md` antes de escribir la migración.

## Comandos frecuentes

- `docker compose up -d` — levantar el stack
- `docker compose up -d --build` — rebuild + levantar
- `docker compose exec api alembic upgrade head` — aplicar migraciones pendientes
- `docker compose exec api alembic revision --autogenerate -m "desc"` — generar migración
- `docker compose logs -f api` — logs en tiempo real
- `curl http://localhost:8000/health` — verificar que la API responde
- `http://localhost:8000/docs` — OpenAPI UI (Swagger)

## Tests

Correr desde el directorio `api/` (o dentro del contenedor con `docker compose exec api`):

```bash
pytest                                         # suite completa
pytest tests/unit/                             # solo unitarios
pytest tests/integration/                      # solo integración
pytest tests/unit/test_foo.py::test_bar -xvs  # test único con output completo
```

El `asyncio_mode = "auto"` en `pyproject.toml` hace que todos los tests `async def` sean recogidos automáticamente sin necesidad de `@pytest.mark.asyncio`.

## Gestión de dependencias

- Producción: `api/requirements.txt`
- Desarrollo y tests: `api/requirements-dev.txt` — `pip install -r requirements-dev.txt`
- `api/pyproject.toml` contiene únicamente config de pytest (`asyncio_mode`). No es el gestor de dependencias.

## Invariantes de la sesión de base de datos

`get_db()` en `app/core/database.py` hace auto-commit al salir limpio y rollback automático en excepción. Los Repositories no deben llamar `session.commit()` ni `session.rollback()` — eso rompe la unidad de trabajo del request.

## Módulos del dominio

Los módulos planeados (routers/services/repositories/schemas/models) son: `pae`, `attendance`, `agendatorio`, `departures`, `auth`, `imports`. Cada módulo sigue el mismo patrón de archivos paralelos en cada capa.

## Pitfalls conocidos

- El build backend en cualquier `pyproject.toml` de este repo debe ser `setuptools.build_meta`. `setuptools.backends.legacy:build` no existe en `python:3.12-slim` y rompe el build de Docker.
- La variable `DATABASE_URL` en `.env` usa el hostname `postgres` (nombre del servicio Docker). Para conectar desde fuera de Docker (TablePlus, psql local) usar `localhost:5433`.
- El `DATABASE_URL` requiere el driver `postgresql+asyncpg://` — no `postgresql://` ni `postgres://`.

## Principios SOLID

S, O, I y D aplican. Liskov aplica únicamente donde hay polimorfismo real (los Adapters). No forzar LSP donde no hay jerarquías de herencia.