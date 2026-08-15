# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentación

`docs/README.md` es el índice de los 13 documentos del proyecto — consultarlo antes de tocar un módulo. Dos tienen valor de regla: **`docs/scope.md`** es la fuente de verdad de *qué* se construye, y **`docs/database-schema.md`** debe actualizarse **antes** de escribir cada migración.

Al cerrar un cambio de módulo, sincronizar también su doc temático (`attendance.md`, `pae.md`, `students.md`, `admin.md`, `frontend.md`, `landing-page.md`…), no solo `database-schema.md`: es la deuda que más rápido se acumula.

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
  El proveedor de correo se elige con `EMAIL_PROVIDER` (`resend` | `mailtrap`) y se resuelve en `app/adapters/email/factory.py`; los jobs piden `get_email_adapter()`, nunca una clase concreta. **`mailtrap` no entrega a nadie**: captura todo en una bandeja de QA compartida.

## Frontend

Las convenciones de CSS/JSX y los gotchas del navegador viven en **`web/CLAUDE.md`** (se carga solo al trabajar en `web/`). **Leerlo antes de tocar el frontend**: casi toda tarea en este repo es full-stack y esos gotchas — Vite 200 ≠ pantalla viva, propagación en portales, `backdrop-filter` y bloques contenedores — muerden antes de que te des cuenta.

## Convenciones de base de datos

- Todos los IDs son `UUID` generados en la aplicación. Nunca usar `SERIAL` o `BIGSERIAL`.
- Para impedir **solapamiento de rangos** (no solo duplicados exactos): `EXCLUDE USING gist` + extensión `btree_gist`, como `class_periods_no_overlap` sobre `int4range(period_order, period_order + span)`. Una `UNIQUE` sobre el valor de inicio no cubre un rango que se extiende. Duplicar la comprobación en el service solo para dar un 409 legible.
- Todo cambio al esquema debe reflejarse en `docs/database-schema.md` antes de escribir la migración.

**Corrección del dato en el tiempo** (no son gotchas: si se rompen, el dato entra mal en la BD):

- `api`, `worker`, `beat` y `postgres` fijan `TZ=America/Bogota` en `docker-compose.yml` (y `postgres` además `-c timezone=America/Bogota` por flag, porque `TZ`/`PGTZ` solo aplican al initdb de un cluster nuevo). Sin eso las imágenes corren en UTC y `date.today()` **adelanta un día entre las 19:00 y medianoche hora Colombia**, escribiendo la fecha equivocada en `attendance_records`, `pae_deliveries` y `early_departures`. No es un problema de presentación: el dato entra mal en la BD.
- Todo el código usa ya hora local (`datetime.now()` / `date.today()`). **El único UTC explícito que queda es el `exp` del JWT** en `security.py`, y debe seguir así: es un instante absoluto que se codifica a epoch. No reintroducir `datetime.now(timezone.utc)` en los services.
- Las columnas `TIMESTAMP` son naive y mezclan zonas por historia: las filas creadas **antes** del 2026-08-14 guardan UTC, las posteriores hora de Bogotá. No afecta a los hashes del PAE (la auditoría recalcula desde el valor almacenado, verificado con 18 firmas viejas + 1 nueva conviviendo, 0 manipuladas), pero sí a cualquier consulta que compare marcas de tiempo de ambos lados de esa fecha.
- Para un campo "único por institución" (no global): `UniqueConstraint("institution_id", campo)` + índice a nivel BD, más un chequeo previo en el service (`get_by_X(institution_id, valor)` → `409` si existe) para dar un mensaje claro en vez de que lo reviente la constraint. Patrón ya usado en `students.document_number`, `subjects.name` y `users.document_number` — replicarlo tal cual, no reinventarlo.

## Aislamiento multi-tenant — regla crítica

Todo método de Repository que acceda a una tabla operativa **debe recibir `institution_id` como parámetro y filtrarlo en el WHERE**. El ORM no lo hace automáticamente. Omitirlo expone datos de todas las instituciones.

El `institution_id` siempre proviene del token JWT del usuario autenticado (`current_user.institution_id`), nunca de parámetros de la request. Ver `docs/implementation-notes.md` para el patrón completo con ejemplos.

Los jobs de Celery que acceden a tablas operativas deben recibir `institution_id` explícitamente vía `.delay()` (ej. `.delay(str(record.id), str(institution_id))`) — el job corre fuera del contexto del request y no tiene acceso al JWT.

## Comandos frecuentes

> Guía operativa completa (arranque, credenciales, troubleshooting) en `docs/runbook.md`.

- `docker compose up -d` — levantar el stack (el servicio `storage-init` crea el bucket en MinIO automáticamente)
- `docker compose up -d --build` — rebuild + levantar
- `docker compose up -d --force-recreate api worker beat` — recrear servicios tras cambiar `.env` (`Settings()` se evalúa al importar, el SIGHUP del worker no basta). Esquiva el problema de AppArmor de `docker stop`.
- `docker compose exec api alembic upgrade head` — aplicar migraciones pendientes
- `docker compose exec api alembic revision --autogenerate -m "desc"` — generar migración
- `docker compose logs -f api` — logs en tiempo real
- `curl http://localhost:8000/health` — verificar que la API responde
- `http://localhost:8000/docs` — OpenAPI UI (Swagger)
- `docker compose exec api alembic check` — verificar que no hay drift entre modelos y BD
- `docker compose exec api python -m scripts.seed_base` — crear institución y usuario demo (BD limpia)
- `docker compose exec api python -m scripts.seed_agendatorio` — crear estudiante y acudiente de prueba
- `docker compose exec -T postgres psql -U biga -d biga < scripts/seed_dev_users.sql` — **seed demo completo** (3 usuarios TEACHER/PAE_OPERATOR/ADMIN, grupo 11A con horario, 4 estudiantes + acudientes + matrículas, artículos de convivencia). Correr **después** de `alembic upgrade head`. Credenciales en `docs/runbook.md` §5. Ubicación dual de seeds: `seed_dev_users.sql` vive en `./scripts/` (root, se pipea con `psql <`), mientras que `seed_base`/`seed_pae` viven en `api/scripts/` y se corren con `python -m scripts.X` dentro del contenedor.
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

Módulos implementados: `auth`, `agendatorio` (registro de convivencia + historial del docente: notas de seguimiento append-only y ocultar del panel vía `archived_at`, sin borrar), `students` (registro append-only + búsqueda), `pae` (inscripción, entrega, reporte semanal, auditoría, notificación de no reclamo), `attendance` (clase a clase; notificación solo primera hora + justificación por link), `departures` (salidas anticipadas), `admin` (estadísticas `GET /admin/stats` + consola de gestión: usuarios, salones, materias, matrículas y horarios — rejilla semanal con materia y docente por bloque, más la asignación docente-salón de `user_groups`), `leads` (`POST /leads` **público** desde el formulario de la landing: guarda en `demo_leads` y encola un aviso interno a `LEADS_NOTIFY_EMAIL`). Pendientes: `imports`.

**Grados = catálogo fijo**: 11 niveles sembrados (`app/core/grades.py`, migración `a7c3e9f2b581`). No existe `POST /admin/grades` ni alta en la consola.

**`DELETE` en admin = baja lógica** (`is_active = false`), nunca borrado: usuarios y estudiantes. `get_current_user` valida `is_active`, así que desactivar **revoca el acceso en el request siguiente**, no al expirar el JWT. Los listados aceptan `include_inactive=true` para poder reactivar.

**El admin no fija contraseñas**: al crear un usuario el service genera una temporal y la envía por correo (`notify_staff_welcome`, con `argsrepr` para que no caiga en los logs del worker).

`demo_leads` es la **única tabla sin `institution_id`**, por decisión explícita: un visitante que pide una demo no pertenece a ninguna institución. Su estado de envío vive en columnas `notification_*` propias, no en `notifications_log` (esa tabla exige `institution_id`/`student_id`/`guardian_id` NOT NULL). El endpoint público lleva rate limit por IP en Redis (`app/core/rate_limit.py`); si Redis cae, deja pasar la petición en vez de perder el lead.

Sin visor en el `AdminDashboard` (deliberado — ver `docs/admin.md`): esa consola es del colegio, y los leads son datos comerciales de BIGA, no de la institución. El equipo de BIGA gestiona la repartición de demos por fuera de la app; el único aviso es el correo a `LEADS_NOTIFY_EMAIL`.

**Referencia completa del ciclo de vida de estudiantes y acudientes (alta, matrícula,
búsqueda, acudiente principal) en `docs/students.md`; consola de gestión del admin
(usuarios, grados, salones, horarios) en `docs/admin.md`.** Acá solo las reglas más
fáciles de romper por accidente:

- `GET /students` está **acotado por rol**: `TEACHER`/`PAE_OPERATOR` solo ven los salones
  que tienen en `user_groups`; solo `ADMIN` recibe la institución entera y puede filtrar por
  `grade_id`/`group_id`. El recorte vive en `StudentService.list_students`, no en el front.
  No confundir con `GET /students/search`, que **sigue alcanzando a toda la institución** a
  propósito (convivencia debe poder registrar a cualquiera, sea o no de sus salones).
- `POST /admin/students` crea Student + matrícula opcional + Guardians **atómicamente**
  (`AdminManagementService.create_student_full`). `student_groups` no tiene `grade_id` — el
  Grado es solo un filtro de UI, nunca llega al payload. Exactamente un `guardian` debe ser
  `is_primary=true` (validado en el schema, reforzado por el índice único
  `one_primary_per_student` en BD).
- Los **módulos del PAE no se ven afectados** por el scoping de `GET /students`:
  `/pae/students/today` y las matrículas del PAE filtran solo por institución. Y el
  operador PAE **no matricula a nadie en el PAE** — `POST /pae/enrollments` exige
  `require_admin` (detalle en `docs/pae.md`).
- Patrón "ficha + edición" del admin (`GET`/`PUT /admin/students/{id}`, `GET`/`PUT /admin/users/{id}`):
  el `GET` trae la ficha de solo lectura; el `PUT` reusa el mismo formulario del alta, precargado,
  para editar. Mismo componente de front para crear y editar (`editingId` decide el modo). Detalle en
  `docs/students.md` y `docs/admin.md`.

Foto del estudiante: se **sube a MinIO** vía `POST /students/{id}/photo` (multipart), igual que la firma del agendatorio. `students.photo_url` guarda la **key** (no la URL); todo servicio que la devuelve la presigna con `resolve_photo_url(storage, ...)` de `app/core/photos.py` (deja pasar URLs `http(s)://` externas por compat). Por eso `PAEService`/`AttendanceService`/`StudentService` reciben el `S3StorageAdapter` inyectado.

Para exponer `photo_url` en un endpoint de **lista/detalle nuevo** (de cualquier módulo, no solo estudiantes): (1) agregar el campo al Row/dataclass del repo y al schema de respuesta, (2) `select(Student.photo_url)` en la query + mapearlo, (3) presignar con `resolve_photo_url(self.storage, key)` en el service (que debe recibir `S3StorageAdapter` vía `Depends(get_storage_adapter)`). Sin migración (solo lee `students.photo_url`). El front renderiza `<StudentPhoto src={x.photo_url}>` con fallback a avatar de iniciales.

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

- **El docente de "Mis clases de hoy" sale de `class_periods.user_id`** (NOT NULL), no de `user_groups`. Antes, un docente asignado al salón veía **todas** las horas de ese salón. Las 4 consultas de `attendance_repository` filtran por bloque — y como `class_periods` no tiene año, hay que unir `Group` y filtrar `Group.academic_year`, o reaparecen bloques de años pasados.
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

Inscripciones (`pae_enrollments`) y entregas (`pae_deliveries`) son registros tipo libro contable: **los campos que entran en el hash no se modifican ni se borran vía API** (no hay `PUT`/`PATCH`/`DELETE` sobre `pae_enrollments`/`pae_deliveries` en sí). Cada uno se firma con HMAC-SHA256 y la entrega encadena el hash de la inscripción:

- `enrollment_hash` (capa 1) = `HMAC(student_id : institution_id : academic_year : enrolled_at)`
- `delivery_hash` (capa 2) = `HMAC(student_id : delivery_date : delivered_by_user_id : created_at : enrollment_hash)`

Funciones en `app/core/security.py`. `register_delivery` verifica la capa 1 antes de entregar y rechaza inscripciones comprometidas. `GET /pae/audit` recomputa ambas capas. La clave (`PAE_SIGNING_SECRET`) nunca vive en la BD. Detalle completo en `docs/architecture.md`.

**Única excepción:** `pae_enrollments.is_active` (no entra en el hash) se puede alternar desde `PUT /admin/students/{id}` — el switch "Inscrito en el PAE" del formulario de edición del admin, ver `docs/students.md` y `docs/pae.md`. Nunca toca los campos que sí entran en el hash.

- Los `created_at`/`enrolled_at` de estos dos modelos se fijan en la app (no `server_default`) porque entran en el hash. No cambiar a `server_default` sin ajustar el cálculo del hash.

## Pitfalls conocidos

Extraídos a **`docs/pitfalls.md`** (30 entradas en 8 categorías) para no cargarlos en cada prompt.

**Leerlo antes de** tocar migraciones, Docker/`.env`, autenticación o correo — y siempre que algo
"debería funcionar" y no funciona. Lo que hay allí: AppArmor y `docker stop`, `passlib` vs `bcrypt`,
enums nativos de PG fuera del bloque transaccional, `alembic check` ciego a los CHECK, orden de
registro de rutas en Starlette, validadores de Pydantic tras el `Field`, el `include` de Celery,
commitlint, y cómo editar ficheros con scripts sin romperlos en silencio.

Las trampas de **frontend** (headless/CDP, `backdrop-filter`, cascade, overflow atrapado) viven
aparte, en `web/CLAUDE.md`.
