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

## Aislamiento multi-tenant — regla crítica

Todo método de Repository que acceda a una tabla operativa **debe recibir `institution_id` como parámetro y filtrarlo en el WHERE**. El ORM no lo hace automáticamente. Omitirlo expone datos de todas las instituciones.

El `institution_id` siempre proviene del token JWT del usuario autenticado (`current_user.institution_id`), nunca de parámetros de la request. Ver `docs/implementation-notes.md` para el patrón completo con ejemplos.

## Comandos frecuentes

- `docker compose up -d` — levantar el stack (el servicio `storage-init` crea el bucket en MinIO automáticamente)
- `docker compose up -d --build` — rebuild + levantar
- `docker compose exec api alembic upgrade head` — aplicar migraciones pendientes
- `docker compose exec api alembic revision --autogenerate -m "desc"` — generar migración
- `docker compose logs -f api` — logs en tiempo real
- `curl http://localhost:8000/health` — verificar que la API responde
- `http://localhost:8000/docs` — OpenAPI UI (Swagger)
- `docker compose exec api alembic check` — verificar que no hay drift entre modelos y BD
- `docker compose exec api python -m scripts.seed_base` — crear institución y usuario demo (BD limpia)
- `docker compose exec api python -m scripts.seed_agendatorio` — crear estudiante y acudiente de prueba

## Tests

Correr desde el directorio `api/` (requiere virtualenv local con `requirements-dev.txt`), o en el contenedor tras instalar dev deps:

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

Módulos implementados: `auth`, `agendatorio`, `students` (registro append-only + búsqueda), `pae` (inscripción, entrega, reporte semanal, auditoría). Pendientes: `attendance`, `departures`, `imports`.
Cada módulo sigue el mismo patrón de archivos paralelos en cada capa.

Para proteger un endpoint con autenticación: `current_user: User = Depends(get_current_user)` desde `app.core.dependencies`. El `current_user.institution_id` es la fuente del tenant para todos los queries.

## Integridad PAE — doble hash encadenado (regla crítica)

Inscripciones (`pae_enrollments`) y entregas (`pae_deliveries`) son registros tipo libro contable: **no se modifican ni se borran vía API** (no hay `PUT`/`PATCH`/`DELETE`). Cada uno se firma con HMAC-SHA256 y la entrega encadena el hash de la inscripción:

- `enrollment_hash` (capa 1) = `HMAC(student_id : institution_id : academic_year : enrolled_at)`
- `delivery_hash` (capa 2) = `HMAC(student_id : delivery_date : delivered_by_user_id : created_at : enrollment_hash)`

Funciones en `app/core/security.py`. `register_delivery` verifica la capa 1 antes de entregar y rechaza inscripciones comprometidas. `GET /pae/audit` recomputa ambas capas. La clave (`PAE_SIGNING_SECRET`) nunca vive en la BD. Detalle completo en `docs/architecture.md`.

- Los `created_at`/`enrolled_at` de estos dos modelos se fijan en la app (no `server_default`) porque entran en el hash. No cambiar a `server_default` sin ajustar el cálculo del hash.

## Convenciones del frontend

- Cada componente tiene su propio archivo CSS en `web/src/styles/` con el mismo nombre: `Hero.jsx` → `styles/hero.css`.
- Los estilos globales y variables van en `web/src/index.css`.
- Las páginas viven en `web/src/pages/`, los componentes reutilizables en `web/src/components/`.
- Los hooks personalizados van en `web/src/hooks/`.

## Pitfalls conocidos

- El build backend en cualquier `pyproject.toml` de este repo debe ser `setuptools.build_meta`. `setuptools.backends.legacy:build` no existe en `python:3.12-slim` y rompe el build de Docker.
- La variable `DATABASE_URL` en `.env` usa el hostname `postgres` (nombre del servicio Docker). Para conectar desde fuera de Docker (TablePlus, psql local) usar `localhost:5433`.
- El `DATABASE_URL` requiere el driver `postgresql+asyncpg://` — no `postgresql://` ni `postgres://`.
- `passlib` es incompatible con `bcrypt>=4.0`. Este proyecto usa `bcrypt` directamente (sin passlib). No reintroducir `passlib[bcrypt]`.
- En SQLAlchemy 2.x, nombrar una columna `date` en un modelo que también importa `from datetime import date` causa `MappedAnnotationError`. Solución: `from datetime import date as PyDate`.
- El dummy hash para prevención de timing en login (`AuthService._DUMMY_HASH`) debe ser un bcrypt válido pre-computado. Un string malformado lanza `ValueError: Invalid salt` en bcrypt.
- `pytest` no está en la imagen Docker de producción. Para correr tests en el contenedor: `docker compose exec api pip install -r requirements-dev.txt` primero.
- `docker compose exec api python -c "..."` con código multiline falla por indentación al pegar. Crear scripts en `api/scripts/` y ejecutar con `python -m scripts.nombre`.
- `STORAGE_PUBLIC_URL` en `.env` debe apuntar al hostname accesible desde el browser (`http://localhost:9000` en dev). `STORAGE_ENDPOINT_URL` es el hostname interno de Docker (`http://minio:9000`) — sin esta separación las URLs presignadas no son accesibles desde el frontend.
- `docker stop` falla con "permission denied" por AppArmor. Workaround: `sudo kill -9 $(docker inspect --format '{{.State.Pid}}' <id>)`.

