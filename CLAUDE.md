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

## Principios SOLID

S, O, I y D aplican. Liskov aplica únicamente donde hay polimorfismo real (los Adapters). No forzar LSP donde no hay jerarquías de herencia.