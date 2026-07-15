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

```
api/app/
├── core/        — config, database, celery, dependencies, security
├── models/      — SQLAlchemy models + enums.py
├── schemas/     — Pydantic request/response schemas
├── repositories/— queries SQL (una clase por módulo)
├── services/    — lógica de negocio + clases Notifier para jobs
├── routers/     — endpoints FastAPI
├── jobs/        — Celery tasks (wrappers delgados sobre Notifiers)
└── adapters/    — email/ y storage/ (Protocol + implementación)
```

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

Los jobs de Celery que acceden a tablas operativas deben recibir `institution_id` explícitamente vía `.delay()` (ej. `.delay(str(record.id), str(institution_id))`) — el job corre fuera del contexto del request y no tiene acceso al JWT.

## Comandos frecuentes

> Guía operativa completa (arranque, credenciales, troubleshooting) en `docs/runbook.md`.

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
- `docker compose exec -T postgres psql -U biga -d biga < scripts/seed_dev_users.sql` — **seed demo completo** (3 usuarios TEACHER/PAE_OPERATOR/ADMIN, grupo 11A con horario, 4 estudiantes + acudientes + matrículas, artículos de convivencia). Correr **después** de `alembic upgrade head`. Credenciales en `docs/databaseDev.md`.
- `docker compose exec -T api python -m scripts.seed_pae` — inscribe los estudiantes demo al PAE y registra entregas de la semana con la cadena de doble hash válida. Es Python (no SQL) porque los hashes dependen de `PAE_SIGNING_SECRET`. Correr **después** del seed SQL.
- Obtener token JWT para pruebas manuales (tras `seed_base`, form-urlencoded con `username`/`password`, no JSON):
  `export TOKEN=$(curl -s -X POST http://localhost:8000/auth/login -d "username=demo@biga.app&password=Test1234!" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")`
- Recargar worker Celery tras cambiar código en `app/jobs/` (no tiene autoreload):
  `docker compose exec worker python -c "import os, signal; os.kill(1, signal.SIGHUP)"`

## Tests

Correr desde el directorio `api/` (requiere virtualenv local con `requirements-dev.txt`), o en el contenedor tras instalar dev deps:

```bash
pytest                                         # suite completa
pytest tests/unit/                             # solo unitarios
pytest tests/integration/                      # solo integración
pytest tests/unit/test_foo.py::test_bar -xvs  # test único con output completo
```

El `asyncio_mode = "auto"` en `pyproject.toml` hace que todos los tests `async def` sean recogidos automáticamente sin necesidad de `@pytest.mark.asyncio`.

Para testear una validación del Service que duplica una regla del schema Pydantic (ej. `Field(min_length=1)`), construir el input con `Schema.model_construct(...)` — bypassa la validación de Pydantic y permite llegar al chequeo del Service.

Correr localmente fuera del contenedor: `set -a && source ../.env && set +a` antes del comando pytest — `Settings()` busca `.env` relativo al cwd (`api/`), que no existe; sin las env vars el conftest falla al importar `app.main`.

Sin virtualenv local y con el stack abajo, correr unitarios en contenedor efímero (sin levantar servicios): `docker compose run --rm --no-deps api sh -c "pip install -q -r requirements-dev.txt && pytest tests/unit -q"`

Verificar que un cambio de front compila sin levantar navegador: `curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/src/pages/X.jsx` (200 = transforma OK; un error de sintaxis da 500) y `docker compose logs web | grep -iE "error|Internal server"`.

## Gestión de dependencias

- Producción: `api/requirements.txt`
- Desarrollo y tests: `api/requirements-dev.txt` — `pip install -r requirements-dev.txt`
- `api/pyproject.toml` contiene únicamente config de pytest (`asyncio_mode`). No es el gestor de dependencias.

## Invariantes de la sesión de base de datos

`get_db()` en `app/core/database.py` hace auto-commit al salir limpio y rollback automático en excepción. Los Repositories no deben llamar `session.commit()` ni `session.rollback()` — eso rompe la unidad de trabajo del request.

## Módulos del dominio

Módulos implementados: `auth`, `agendatorio` (registro de convivencia + historial del docente: notas de seguimiento append-only y ocultar del panel vía `archived_at`, sin borrar), `students` (registro append-only + búsqueda), `pae` (inscripción, entrega, reporte semanal, auditoría, notificación de no reclamo), `attendance` (clase a clase; notificación solo primera hora + justificación por link), `departures` (salidas anticipadas), `admin` (estadísticas `GET /admin/stats` + consola de gestión: usuarios, grados, grupos, matrículas, horarios `class_periods` y asignación docente-grupo). Pendientes: `imports`.

Búsqueda de estudiantes (`GET /students/search`): `q` es **opcional** — con `grade_id`/`group_id` se navega por grado/salón sin escribir. Es **insensible a acentos** vía la extensión `unaccent` (`Lopez` encuentra `López`; migración `d4a2c7e91b05`). Los selectores de grado/salón se llenan con `GET /agendatorio/grades` y `GET /agendatorio/groups` (accesibles a **staff**, no solo admin). El front reutiliza el componente `StudentSearch` en Convivencia e Historial.

Foto del estudiante: se **sube a MinIO** vía `POST /students/{id}/photo` (multipart), igual que la firma del agendatorio. `students.photo_url` guarda la **key** (no la URL); todo servicio que la devuelve la presigna con `resolve_photo_url(storage, ...)` de `app/core/photos.py` (deja pasar URLs `http(s)://` externas por compat). Por eso `PAEService`/`AttendanceService`/`StudentService` reciben el `S3StorageAdapter` inyectado.

Roles (`user_role`): `TEACHER`, `PAE_OPERATOR`, `ADMIN`. El operador PAE es un docente con funciones extra del PAE — las funciones de aula usan `require_staff` (TEACHER+PAE_OPERATOR); la gestión y estadísticas usan `require_admin`. Inscripción PAE y listado del día admiten PAE_OPERATOR o ADMIN (`require_pae_or_admin` en el router PAE). Dependencies en `app/core/dependencies.py`.
Cada módulo sigue el mismo patrón de archivos paralelos en cada capa.

Para proteger un endpoint con autenticación: `current_user: User = Depends(get_current_user)` desde `app.core.dependencies`. El `current_user.institution_id` es la fuente del tenant para todos los queries.

## Asistencia, salidas y jobs de notificación

- **Asistencia clase a clase**: el docente toma lista de **cualquier** clase del día, no solo la primera hora (scope 3.2). `GET /attendance/today` lista sus clases de hoy (resueltas vía `user_groups` → `class_periods` por `day_of_week`, con badge `already_taken`); `GET /attendance/classes/{class_period_id}` devuelve el roster de una clase; `POST /attendance` registra la lista. La UNIQUE `(student_id, class_period_id, date)` permite un registro por estudiante por clase por día (no requiere migración: el esquema ya lo soportaba). **La notificación al acudiente solo se dispara en primera hora** (`period_order == 1`): ahí, por cada `ABSENT` se encola `notify_absence_first_hour` con `countdown = ATTENDANCE_GRACE_MINUTES * 60` (default 50, bajar en dev). Las clases 2–N se registran para historial, sin correo. Si el alumno llega dentro de la ventana, el docente lo marca tardanza (`POST /attendance/records/{id}/arrived` → `LATE`) y el job, al disparar, relee el estado y no notifica.
- **Justificación por link**: el correo de inasistencia lleva un enlace de un solo uso `FRONTEND_URL/justificar/{token}` (tabla `attendance_tokens`, vence a medianoche). Los endpoints `GET/POST /attendance/justify/{token}` son **públicos** (sin JWT): el token UUID es la autorización. Al justificar, el registro pasa a `JUSTIFIED`.
- **Salidas anticipadas**: `POST /departures` crea el registro y encola `notify_early_departure` (correo informativo, sin token).
- **Jobs Celery + BD async**: las tareas son síncronas pero la BD es async. `app/jobs/runner.py::run_db_job` levanta un engine `NullPool` propio por tarea, hace commit/rollback y lo descarta. Cada job arma su notifier (`AttendanceNotifier`/`DepartureNotifier`/`DisciplineRecordNotifier`/`PAENotifier`) con esa sesión y un `EmailAdapter`. Un fallo de correo se registra en `notifications_log` como `FAILED` y **no** relanza. Sin una API key real de Resend el correo no sale, pero el enlace de justificación queda en los logs del worker.
- **PAE no reclamado**: único job **programado** (no por evento). `beat_schedule` en `app/core/celery.py` corre `sweep_pae_no_claim` cada 15 min → por cada institución cuya `pae_delivery_end_time` (columna en `institutions`) ya pasó hoy, encola `notify_pae_no_claim(institution_id, date)`. `PAENotifier` es idempotente (omite a quienes ya tienen log `PAE_NO_CLAIM` hoy) y no notifica si hubo 0 entregas ese día. Requiere el servicio `beat` levantado.

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
- El frontend requiere `web/.env` (gitignored, sin `.env.example`) con `VITE_API_URL=http://localhost:8000`. Sin esa var, `fetch` va a `undefined/...` y todo el front falla en silencio. El CORS del API ya permite `http://localhost:5173`. (`vite.config.js` tiene un proxy `/api-proxy` que el código actual no usa.)
- `PAEDashboard.jsx` **reutiliza** las vistas de aula de `TeacherDashboard.jsx` (`import { AttendanceView, ConvivenciaView, HistorialView, ... }`). El operador PAE es un docente con funciones extra: un módulo de aula nuevo debe exportarse desde `TeacherDashboard` y engancharse en **ambos** dashboards (nav + render). El componente `StudentSearch` (buscador grado/salón/nombre) vive en `TeacherDashboard` y se reutiliza.

## Pitfalls conocidos

- Al escribir texto con acentos/caracteres especiales en JSX vía las tools de edición, a veces quedan como escape literal (ej. `Sal\u00f3n` se ve literal en vez de `Salón`; `\u2026` en vez de `…`). En **JSX-texto/atributo** esos escapes NO se interpretan y se ven literales en la UI. Detectar con `grep -rn '\\u00\|\\u2026' web/src`; corregir con `perl -CSD -i -pe 's/\\u2026/\x{2026}/g' <archivo>` (al carácter UTF-8 real).
- El servicio `web` monta un volumen anónimo en `/app/node_modules` (compose). Tras agregar una dependencia npm nueva, Vite falla con `Failed to resolve import "..."` aunque esté en `package.json`: el volumen viejo tapa el `node_modules` de la imagen. Rebuildear renovando el volumen: `docker compose up -d --build --force-recreate --renew-anon-volumes web` (y matar el contenedor viejo con el workaround de AppArmor si `stop` falla).
- El build backend en cualquier `pyproject.toml` de este repo debe ser `setuptools.build_meta`. `setuptools.backends.legacy:build` no existe en `python:3.12-slim` y rompe el build de Docker.
- La variable `DATABASE_URL` en `.env` usa el hostname `postgres` (nombre del servicio Docker). Para conectar desde fuera de Docker (TablePlus, psql local) usar `localhost:5433`.
- El `DATABASE_URL` requiere el driver `postgresql+asyncpg://` — no `postgresql://` ni `postgres://`.
- `passlib` es incompatible con `bcrypt>=4.0`. Este proyecto usa `bcrypt` directamente (sin passlib). No reintroducir `passlib[bcrypt]`.
- En SQLAlchemy 2.x, nombrar una columna `date` en un modelo que también importa `from datetime import date` causa `MappedAnnotationError`. Solución: `from datetime import date as PyDate`.
- El dummy hash para prevención de timing en login (`AuthService._DUMMY_HASH`) debe ser un bcrypt válido pre-computado. Un string malformado lanza `ValueError: Invalid salt` en bcrypt.
- `pytest` no está en la imagen Docker de producción. Para correr tests en el contenedor: `docker compose exec api pip install -r requirements-dev.txt` primero.
- Agregar un valor a un enum nativo de PostgreSQL (`ALTER TYPE ... ADD VALUE`) no corre dentro del bloque transaccional de Alembic. Hay que envolverlo en `with op.get_context().autocommit_block():` (ver migración `c3e8f1a6b9d2`).
- `docker compose exec api python -c "..."` con código multiline falla por indentación al pegar. Crear scripts en `api/scripts/` y ejecutar con `python -m scripts.nombre`.
- `STORAGE_PUBLIC_URL` en `.env` debe apuntar al hostname accesible desde el browser (`http://localhost:9000` en dev). `STORAGE_ENDPOINT_URL` es el hostname interno de Docker (`http://minio:9000`) — sin esta separación las URLs presignadas no son accesibles desde el frontend.
- `docker stop` falla con "permission denied" por AppArmor. Workaround: `sudo kill -9 $(docker inspect --format '{{.State.Pid}}' <id>)`.
- `POST /auth/login` espera `application/x-www-form-urlencoded` con campos `username`/`password` (OAuth2PasswordRequestForm), no JSON con `email`/`password`.
- Si un curl a un endpoint con path param (ej. `/agendatorio/records/$RECORD_ID`) devuelve body vacío sin error visible, revisar que la variable no esté vacía: un segmento final vacío (`/records/`) dispara un 307 a `/records` que curl no sigue por defecto, devolviendo body vacío en silencio.
- Tras un pull que añade vars a `.env.example`, `worker`/`beat` crashean al arrancar con `ValueError: Field required` de Pydantic (campos nuevos en `Settings` que no están en el `.env` local gitignored). Detectar vars ausentes: `diff <(grep -oP '^[A-Z_]+(?==)' .env.example | sort) <(grep -oP '^[A-Z_]+(?==)' .env | sort)`.
- El `worker` de Celery no tiene autoreload. Usar el comando SIGHUP de "Comandos frecuentes" para recargar — `docker compose restart worker` choca con el problema de AppArmor de `docker stop`.
- Al crear un módulo de job nuevo en `app/jobs/`, agregarlo al `include` de `app/core/celery.py` — si no, el worker nunca registra el task y `.delay()` encola mensajes que nadie ejecuta nunca (sin error visible).
- Los tests de repository (queries SQL reales, joins, M2M) no se pueden mockear con sentido. No existe infraestructura de fixtures contra Postgres real (`tests/integration/` vacío) — definir esa infraestructura antes de escribir `test_*_repository.py` en cualquier módulo.
- Probar correos sin dominio verificado en Resend: `EMAIL_FROM=onboarding@resend.dev` y el destinatario **debe** ser el correo dueño de la cuenta Resend — cualquier otro destinatario da 403 y el notifier lo registra como `FAILED`. Verificar `biga.app` (SPF/DKIM) es requisito para enviar a acudientes reales.
- `scripts/seed_dev_users.sql` usa `ON CONFLICT (id) DO NOTHING`: re-correrlo **no** actualiza filas existentes. Para cambiar datos ya seedeados (ej. el correo de los acudientes) usar `UPDATE` directo: `UPDATE guardians SET email='...' WHERE is_primary = true;`

