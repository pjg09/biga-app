# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentación

`docs/README.md` es el índice de los 11 documentos del proyecto — consultarlo antes de tocar un módulo. Dos tienen valor de regla: **`docs/scope.md`** es la fuente de verdad de *qué* se construye, y **`docs/database-schema.md`** debe actualizarse **antes** de escribir cada migración.

Al cerrar un cambio de módulo, sincronizar también su doc temático (`attendance.md`, `pae.md`, `frontend.md`, `landing-page.md`…), no solo `database-schema.md`: es la deuda que más rápido se acumula.

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

## Frontend

Las convenciones de CSS/JSX y los gotchas del navegador viven en **`web/CLAUDE.md`** (se carga solo al trabajar en `web/`). **Leerlo antes de tocar el frontend**: casi toda tarea en este repo es full-stack y esos gotchas — Vite 200 ≠ pantalla viva, propagación en portales, `backdrop-filter` y bloques contenedores — muerden antes de que te des cuenta.

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
- `docker compose exec -T postgres psql -U biga -d biga < scripts/seed_dev_users.sql` — **seed demo completo** (3 usuarios TEACHER/PAE_OPERATOR/ADMIN, grupo 11A con horario, 4 estudiantes + acudientes + matrículas, artículos de convivencia). Correr **después** de `alembic upgrade head`. Credenciales en `docs/databaseDev.md`. Ubicación dual de seeds: `seed_dev_users.sql` vive en `./scripts/` (root, se pipea con `psql <`), mientras que `seed_base`/`seed_pae` viven en `api/scripts/` y se corren con `python -m scripts.X` dentro del contenedor.
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

Verificar que un cambio de front compila: `curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/src/pages/X.jsx` (200 = transforma OK; un error de sintaxis da 500) y `docker compose logs web | grep -iE "error|Internal server"`. **200 y logs limpios NO significan que la pantalla funcione**: un error en tiempo de ejecución (p. ej. borrar por accidente un helper compartido como `fmtShort`) deja la app **en blanco** con Vite sirviendo 200 y sin registrar nada. Comprobar siempre el DOM renderizado; para ver el error real, capturar `Runtime.exceptionThrown` / `Log.entryAdded` por CDP.

## Gestión de dependencias

- Producción: `api/requirements.txt`
- Desarrollo y tests: `api/requirements-dev.txt` — `pip install -r requirements-dev.txt`
- `api/pyproject.toml` contiene únicamente config de pytest (`asyncio_mode`). No es el gestor de dependencias.

## Invariantes de la sesión de base de datos

`get_db()` en `app/core/database.py` hace auto-commit al salir limpio y rollback automático en excepción. Los Repositories no deben llamar `session.commit()` ni `session.rollback()` — eso rompe la unidad de trabajo del request.

## Módulos del dominio

Módulos implementados: `auth`, `agendatorio` (registro de convivencia + historial del docente: notas de seguimiento append-only y ocultar del panel vía `archived_at`, sin borrar), `students` (registro append-only + búsqueda), `pae` (inscripción, entrega, reporte semanal, auditoría, notificación de no reclamo), `attendance` (clase a clase; notificación solo primera hora + justificación por link), `departures` (salidas anticipadas), `admin` (estadísticas `GET /admin/stats` + consola de gestión: usuarios, grados, grupos, matrículas, horarios `class_periods` y asignación docente-grupo), `leads` (`POST /leads` **público** desde el formulario de la landing: guarda en `demo_leads` y encola un aviso interno a `LEADS_NOTIFY_EMAIL`). Pendientes: `imports`.

`demo_leads` es la **única tabla sin `institution_id`**, por decisión explícita: un visitante que pide una demo no pertenece a ninguna institución. Su estado de envío vive en columnas `notification_*` propias, no en `notifications_log` (esa tabla exige `institution_id`/`student_id`/`guardian_id` NOT NULL). El endpoint público lleva rate limit por IP en Redis (`app/core/rate_limit.py`); si Redis cae, deja pasar la petición en vez de perder el lead.

Se consultan desde la consola de admin (`GET /admin/leads`, sección "Comercial" del `AdminDashboard`). **Al no haber `institution_id` no hay filtro de tenant en el WHERE**: el aislamiento lo da `require_leads_reader` (`app/core/dependencies.py`), que exige ADMIN + estar en `LEADS_ADMIN_EMAILS`. Con esa lista vacía **cualquier ADMIN de cualquier institución ve todos los leads** — sostenible solo mientras haya una única institución en la BD. Llenarla antes de dar de alta a la segunda, o sustituirla por un rol de superusuario real.

**`GET /students` (módulo "Estudiantes" de la sección Aula) está acotado por rol**: a `TEACHER` y `PAE_OPERATOR` les devuelve solo los estudiantes de los salones que tienen en `user_groups` (por asignación docente-grupo, **no** por horario: da igual la hora de la clase). Solo `ADMIN` recibe la institución entera. El operador PAE es un docente con funciones extra, así que su módulo de Aula se comporta como el de cualquier docente. El recorte vive en `StudentService.list_students`, no en el front: cualquiera puede llamar al endpoint a mano.

`GET /students` acepta `grade_id`/`group_id` opcionales, pero **solo filtran el listado del ADMIN** (`StudentRepository.list_by_institution`, LEFT JOIN a `student_groups`/`groups`/`grades`): el de docente/operador PAE ya viene acotado a sus propios salones y los ignora. La respuesta incluye `grade_name`/`group_name` (`null` si el estudiante no tiene matrícula activa) para toda institución, no solo cuando se filtra.

`POST /admin/students` (consola admin, **distinto** de `POST /students`) crea atómicamente un Student + matrícula opcional en `student_groups` + uno o más Guardians en una sola transacción — `AdminManagementService.create_student_full`, no encadena tres requests. `group_id` es opcional; si se pasa, debe existir en la institución (404 si no). `student_groups` no tiene `grade_id`: el Grado es un filtro de UI para acotar el `<select>` de Salón, nunca llega al payload — la matrícula se guarda con `academic_year` del año actual, calculado en el servidor, no elegible desde el form. Al menos un `guardian` es obligatorio y exactamente uno debe tener `is_primary=true` — validado en `AdminStudentCreate` (Pydantic `model_validator`, no en el service, porque es una regla de forma sin dependencia de BD), reforzado además por el índice parcial único `one_primary_per_student` en la tabla `guardians`. La foto sigue siendo un paso aparte y no-fatal vía `POST /students/{id}/photo`, fuera de esta transacción.

Los **módulos del PAE no se ven afectados**: `/pae/students/today` y las matrículas consultan `pae_enrollments`/`pae_deliveries` filtrando solo por institución, así que el operador sigue viendo a todos los que reclaman o están matriculados, den o no clase con él.

**El operador PAE NO matricula a nadie en el PAE.** `POST /pae/enrollments` exige `require_admin`. Regla de dominio: el operador *opera* el programa (toma el listado, ve métricas, consulta matriculados) pero admitir a un estudiante al PAE es una decisión administrativa. Sus módulos de Aula son **literalmente los del docente**: `PAEDashboard` monta `TeacherStudentsView` (exportada de `TeacherDashboard`), no `StudentsView`. Esta última —con alta de estudiante e inscripción al PAE— la usa **solo** `AdminDashboard`, aunque por historia siga definida en `PAEDashboard.jsx`.

No confundir con `GET /students/search`, que **sigue alcanzando a toda la institución** a propósito: convivencia debe poder registrar a cualquier estudiante, sea o no de sus salones.

Búsqueda de estudiantes (`GET /students/search`): `q` es **opcional** — con `grade_id`/`group_id` se navega por grado/salón sin escribir. Es **insensible a acentos** vía la extensión `unaccent` (`Lopez` encuentra `López`; migración `d4a2c7e91b05`). Los selectores de grado/salón se llenan con `GET /agendatorio/grades` y `GET /agendatorio/groups` (accesibles a **staff**, no solo admin). El front reutiliza el componente `StudentSearch` en Convivencia e Historial.

Foto del estudiante: se **sube a MinIO** vía `POST /students/{id}/photo` (multipart), igual que la firma del agendatorio. `students.photo_url` guarda la **key** (no la URL); todo servicio que la devuelve la presigna con `resolve_photo_url(storage, ...)` de `app/core/photos.py` (deja pasar URLs `http(s)://` externas por compat). Por eso `PAEService`/`AttendanceService`/`StudentService` reciben el `S3StorageAdapter` inyectado.

Para exponer `photo_url` en un endpoint de **lista/detalle nuevo**: (1) agregar el campo al Row/dataclass del repo y al schema de respuesta, (2) `select(Student.photo_url)` en la query + mapearlo, (3) presignar con `resolve_photo_url(self.storage, key)` en el service (que debe recibir `S3StorageAdapter` vía `Depends(get_storage_adapter)`). Sin migración (solo lee `students.photo_url`). El front renderiza `<StudentPhoto src={x.photo_url}>` con fallback a avatar de iniciales.

## Recuperación de contraseña

Tres endpoints **públicos** en `/auth` (`password-reset/request` → `verify` → `confirm`) y la página `/recuperar` en el front (`ForgotPasswordPage.jsx`, asistente de 3 pasos que reutiliza `login.css` + `LoginBrandPanel` exportado de `LoginPage`).

Reglas que no deben relajarse:
- `request` devuelve **siempre** `{"sent": true}`, exista o no la cuenta. Distinguir convierte el endpoint en un oráculo de qué correos tienen cuenta.
- El código va **bcrypt-hasheado** en `password_reset_otps.code_hash`. Seis dígitos con un hash rápido se revierten en segundos si se filtra la BD.
- El paso 3 exige el `reset_token` que emite el servidor al validar el OTP, no el correo. Sin él, cualquiera cambiaría la contraseña de otro afirmando haber pasado el código.
- **`verify_code` no lanza `HTTPException` en el camino de fallo**: devuelve `None` y el router responde el 400 con `JSONResponse`. `get_db()` hace rollback ante excepción, así que lanzar revertiría el `attempts += 1` y el bloqueo por fuerza bruta nunca contaría nada.
- El OTP se manda vía Celery (`app/jobs/auth_jobs.py`) y no dentro del request para que el tiempo de respuesta sea idéntico exista o no la cuenta — si no, el cronómetro delata lo que la respuesta genérica oculta. El `apply_async` pasa `argsrepr` para que el código **no salga en los logs del worker**. Contrapartida: viaja en claro por Redis, así que en producción el puerto de Redis no debe publicarse fuera de la red de Docker.

Roles (`user_role`): `TEACHER`, `PAE_OPERATOR`, `ADMIN`. El operador PAE es un docente con funciones extra del PAE — las funciones de aula usan `require_staff` (TEACHER+PAE_OPERATOR); la gestión y estadísticas usan `require_admin`. En el router PAE: el **listado del día** admite PAE_OPERATOR o ADMIN (`require_pae_or_admin`); entrega, reporte semanal y auditoría son solo del operador (`require_pae_operator`); la **inscripción al PAE es solo del ADMIN** (`require_admin`). Dependencies en `app/core/dependencies.py`.
Cada módulo sigue el mismo patrón de archivos paralelos en cada capa.

Para proteger un endpoint con autenticación: `current_user: User = Depends(get_current_user)` desde `app.core.dependencies`. El `current_user.institution_id` es la fuente del tenant para todos los queries.

## Asistencia, salidas y jobs de notificación

> Referencia completa del módulo en **`docs/attendance.md`** (flujos, endpoints, tablas). Aquí solo los
> invariantes que no deben romperse.

- **La notificación al acudiente solo se dispara en primera hora** (`period_order == 1`). Se encola con
  `countdown = ATTENDANCE_GRACE_MINUTES * 60` y, al disparar, el job **relee el estado**: si el docente
  marcó tardanza, no envía. La tarea **no se desencola** — releer al disparar cubre también el caso de
  que la justificación llegue antes.
- Los endpoints `GET/POST /attendance/justify/{token}` son **públicos** (sin JWT): el token UUID es la
  autorización. `POST` es **multipart** (adjunto opcional, PDF/imagen ≤ `JUSTIFICATION_MAX_UPLOAD_MB`).
  Al ser público, la lista blanca de content-types y el tope de tamaño **son la única defensa**: la
  extensión sale de esa lista, nunca del nombre que manda el cliente.
- Los adjuntos se suben al bucket **antes** de escribir en BD (un huérfano en storage es preferible a una
  fila apuntando a nada) y los intentos rechazados **no consumen el token**.
- **Inasistencias** (sin justificar) y **Mensajes** (excusas recibidas) son secciones de Seguimiento con
  el patrón del Historial: filtros, detalle, notas append-only y cierre reversible. El caso pasa de una a
  otra por la **existencia de `attendance_justifications`**, no por el estado del registro. Aislamiento
  doble: institución **y** `recorded_by_user_id`.
- `attendance_justifications` **no denormaliza `institution_id`**: el tenant se valida con join a
  `attendance_records`. Comprobarlo antes de escribir queries nuevas sobre esa tabla.
- El cierre de una inasistencia es `attendance_records.absence_closed_at`, **no** `archived_at`: el
  registro sigue contando en el roster y en las estadísticas; solo se cierra el seguimiento.
- **Jobs Celery + BD async**: `app/jobs/runner.py::run_db_job` levanta un engine `NullPool` por tarea,
  hace commit/rollback y lo descarta. Un fallo de correo se registra como `FAILED` y **no** relanza.
- **PAE no reclamado**: único job **programado** (`beat_schedule`, cada 15 min). `PAENotifier` es
  idempotente y no notifica si hubo 0 entregas ese día. Requiere el servicio `beat` levantado.
- **Salidas anticipadas**: `POST /departures` encola `notify_early_departure` (correo informativo, sin token).

## Integridad PAE — doble hash encadenado (regla crítica)

Inscripciones (`pae_enrollments`) y entregas (`pae_deliveries`) son registros tipo libro contable: **no se modifican ni se borran vía API** (no hay `PUT`/`PATCH`/`DELETE`). Cada uno se firma con HMAC-SHA256 y la entrega encadena el hash de la inscripción:

- `enrollment_hash` (capa 1) = `HMAC(student_id : institution_id : academic_year : enrolled_at)`
- `delivery_hash` (capa 2) = `HMAC(student_id : delivery_date : delivered_by_user_id : created_at : enrollment_hash)`

Funciones en `app/core/security.py`. `register_delivery` verifica la capa 1 antes de entregar y rechaza inscripciones comprometidas. `GET /pae/audit` recomputa ambas capas. La clave (`PAE_SIGNING_SECRET`) nunca vive en la BD. Detalle completo en `docs/architecture.md`.

- Los `created_at`/`enrolled_at` de estos dos modelos se fijan en la app (no `server_default`) porque entran en el hash. No cambiar a `server_default` sin ajustar el cálculo del hash.

## Pitfalls conocidos

- Al editar ficheros con scripts (`python3 - <<EOF` o `sed`), **poner `assert <ancla> in t` antes de cada `.replace()`**: una sustitución que no coincide no falla, deja el fichero intacto y el fallo aparece mucho después. Pasó con el `NAV_TITLES` de `PAEDashboard.jsx`, que difiere en alineación del de `TeacherDashboard.jsx`.
- `psql -c "..."` **no interpola** variables `-v` (`:'x'`): hay que pasar el SQL por stdin (`psql -v h="$H" <<'SQL' ... SQL`). Y `psql -tAc "INSERT ... RETURNING x"` imprime el valor **y** la etiqueta `INSERT 0 1`: encadenar `| head -1`.
- El build backend en cualquier `pyproject.toml` de este repo debe ser `setuptools.build_meta`. `setuptools.backends.legacy:build` no existe en `python:3.12-slim` y rompe el build de Docker.
- `api`, `worker`, `beat` y `postgres` fijan `TZ=America/Bogota` en `docker-compose.yml` (y `postgres` además `-c timezone=America/Bogota` por flag, porque `TZ`/`PGTZ` solo aplican al initdb de un cluster nuevo). Sin eso las imágenes corren en UTC y `date.today()` **adelanta un día entre las 19:00 y medianoche hora Colombia**, escribiendo la fecha equivocada en `attendance_records`, `pae_deliveries` y `early_departures`. No es un problema de presentación: el dato entra mal en la BD.
- Todo el código usa ya hora local (`datetime.now()` / `date.today()`). **El único UTC explícito que queda es el `exp` del JWT** en `security.py`, y debe seguir así: es un instante absoluto que se codifica a epoch. No reintroducir `datetime.now(timezone.utc)` en los services.
- Las columnas `TIMESTAMP` son naive y mezclan zonas por historia: las filas creadas **antes** del 2026-08-14 guardan UTC, las posteriores hora de Bogotá. No afecta a los hashes del PAE (la auditoría recalcula desde el valor almacenado, verificado con 18 firmas viejas + 1 nueva conviviendo, 0 manipuladas), pero sí a cualquier consulta que compare marcas de tiempo de ambos lados de esa fecha.
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
