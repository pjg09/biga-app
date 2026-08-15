# Pitfalls conocidos

> Trampas de este repo que ya costaron tiempo una vez. **Leer antes de** tocar migraciones,
> fechas/zona horaria, Docker, autenticación o correo — y siempre que algo "debería funcionar"
> y no funciona.
>
> Extraído de `CLAUDE.md` para no cargarlo en cada prompt. Si añades una entrada aquí y es de
> las que corrompen datos en silencio, considera dejar también una línea en `CLAUDE.md`.

## Git y CI

- Cada commit de un PR contra `main` (no solo el título) se valida en CI con `commitlint` (`.github/workflows/commitlint.yml`, `@commitlint/config-conventional` → Conventional Commits: `feat:`, `fix:`, etc.). Un push a `main` dispara `semantic-release` (`.github/workflows/release.yml`) que corta un release según esos tipos (`feat`→minor, `fix`→patch, `BREAKING CHANGE`→major; `docs`/`chore`/etc. no liberan). Mensajes mal formateados no rompen el push, pero sí el check de CI del PR.
- Para separar un working tree grande en commits por temática **sin `git add -p`** (no soportado, pide input interactivo): extraer los hunks de `git diff` con Python por índice de línea — nunca retecleándolos a mano en un editor, un espacio inicial perdido en una línea de contexto vacía corrompe el patch. Al combinar/dividir hunks, recalcular el header `@@ -a,b +c,d @@` con un script (a mano se desincroniza fácil). Validar con `git apply --check --cached` antes de `git apply --cached`, comitear, y **regenerar el diff con `git diff` recién ahí** antes de tocar el mismo archivo de nuevo — los offsets de los hunks restantes cambian con cada commit.

## Fechas y zona horaria

- `api`, `worker`, `beat` y `postgres` fijan `TZ=America/Bogota` en `docker-compose.yml` (y `postgres` además `-c timezone=America/Bogota` por flag, porque `TZ`/`PGTZ` solo aplican al initdb de un cluster nuevo). Sin eso las imágenes corren en UTC y `date.today()` **adelanta un día entre las 19:00 y medianoche hora Colombia**, escribiendo la fecha equivocada en `attendance_records`, `pae_deliveries` y `early_departures`. No es un problema de presentación: el dato entra mal en la BD.
- Todo el código usa ya hora local (`datetime.now()` / `date.today()`). **El único UTC explícito que queda es el `exp` del JWT** en `security.py`, y debe seguir así: es un instante absoluto que se codifica a epoch. No reintroducir `datetime.now(timezone.utc)` en los services.
- Las columnas `TIMESTAMP` son naive y mezclan zonas por historia: las filas creadas **antes** del 2026-08-14 guardan UTC, las posteriores hora de Bogotá. No afecta a los hashes del PAE (la auditoría recalcula desde el valor almacenado, verificado con 18 firmas viejas + 1 nueva conviviendo, 0 manipuladas), pero sí a cualquier consulta que compare marcas de tiempo de ambos lados de esa fecha.

## Docker y entorno

- El build backend en cualquier `pyproject.toml` de este repo debe ser `setuptools.build_meta`. `setuptools.backends.legacy:build` no existe en `python:3.12-slim` y rompe el build de Docker.
- La variable `DATABASE_URL` en `.env` usa el hostname `postgres` (nombre del servicio Docker). Para conectar desde fuera de Docker (TablePlus, psql local) usar `localhost:5433`.
- `pytest` no está en la imagen Docker de producción. Para correr tests en el contenedor: `docker compose exec api pip install -r requirements-dev.txt` primero.
- `docker compose exec api python -c "..."` con código multiline falla por indentación al pegar. Crear scripts en `api/scripts/` y ejecutar con `python -m scripts.nombre`.
- `STORAGE_PUBLIC_URL` en `.env` debe apuntar al hostname accesible desde el browser (`http://localhost:9000` en dev). `STORAGE_ENDPOINT_URL` es el hostname interno de Docker (`http://minio:9000`) — sin esta separación las URLs presignadas no son accesibles desde el frontend.
- `docker stop` falla con "permission denied" por AppArmor. Workaround: `sudo kill -9 $(docker inspect --format '{{.State.Pid}}' <id>)`.
- Tras un pull que añade vars a `.env.example`, `worker`/`beat` crashean al arrancar con `ValueError: Field required` de Pydantic (campos nuevos en `Settings` que no están en el `.env` local gitignored). Detectar vars ausentes: `diff <(grep -oP '^[A-Z_]+(?==)' .env.example | sort) <(grep -oP '^[A-Z_]+(?==)' .env | sort)`.
- El `worker` de Celery no tiene autoreload. Usar el comando SIGHUP de "Comandos frecuentes" para recargar — `docker compose restart worker` choca con el problema de AppArmor de `docker stop`.
- Al crear un módulo de job nuevo en `app/jobs/`, agregarlo al `include` de `app/core/celery.py` — si no, el worker nunca registra el task y `.delay()` encola mensajes que nadie ejecuta nunca (sin error visible).

## Auth y correo

- `passlib` es incompatible con `bcrypt>=4.0`. Este proyecto usa `bcrypt` directamente (sin passlib). No reintroducir `passlib[bcrypt]`.
- El dummy hash para prevención de timing en login (`AuthService._DUMMY_HASH`) debe ser un bcrypt válido pre-computado. Un string malformado lanza `ValueError: Invalid salt` en bcrypt.
- `POST /auth/login` espera `application/x-www-form-urlencoded` con campos `username`/`password` (OAuth2PasswordRequestForm), no JSON con `email`/`password`.
- Probar correos sin dominio verificado en Resend: `EMAIL_FROM=onboarding@resend.dev` y el destinatario **debe** ser el correo dueño de la cuenta Resend — cualquier otro destinatario da 403 y el notifier lo registra como `FAILED`. Verificar `biga.app` (SPF/DKIM) es requisito para enviar a acudientes reales.

## FastAPI y Pydantic

- En Pydantic los `field_validator` corren **después** de las restricciones del `Field`: `Field(min_length=1)` + un validador que hace `.strip()` deja pasar `"   "` y lo guarda vacío. Usar el helper `_strip_required` de `schemas/admin.py`, que recorta **y** rechaza el vacío, en todo campo de texto obligatorio.
- Si un curl a un endpoint con path param (ej. `/agendatorio/records/$RECORD_ID`) devuelve body vacío sin error visible, revisar que la variable no esté vacía: un segmento final vacío (`/records/`) dispara un 307 a `/records` que curl no sigue por defecto, devolviendo body vacío en silencio.
- FastAPI/Starlette resuelve rutas por **orden de registro, no por especificidad**: un `GET /{id}` declarado antes que un `GET /search` hace que "search" matchee como `{id}` (422 si el tipo no castea) y el segundo endpoint nunca se alcanza. Al agregar un endpoint `/{id}` a un router que ya tiene una ruta estática de un solo segmento (`/search`, `/me`, etc.), declararlo **después** en el archivo.

## Migraciones, SQL y seeds

- `alembic check` **no detecta deriva en CHECK constraints** (sí en columnas e índices). Un modelo que declara un CHECK distinto al de la BD pasa el check en verde. Verificar con `pg_constraint` cuando se toque un CHECK.
- `psql -c "..."` **no interpola** variables `-v` (`:'x'`): hay que pasar el SQL por stdin (`psql -v h="$H" <<'SQL' ... SQL`). Y `psql -tAc "INSERT ... RETURNING x"` imprime el valor **y** la etiqueta `INSERT 0 1`: encadenar `| head -1`.
- El `DATABASE_URL` requiere el driver `postgresql+asyncpg://` — no `postgresql://` ni `postgres://`.
- En SQLAlchemy 2.x, nombrar una columna `date` en un modelo que también importa `from datetime import date` causa `MappedAnnotationError`. Solución: `from datetime import date as PyDate`.
- Agregar un valor a un enum nativo de PostgreSQL (`ALTER TYPE ... ADD VALUE`) no corre dentro del bloque transaccional de Alembic. Hay que envolverlo en `with op.get_context().autocommit_block():` (ver migración `c3e8f1a6b9d2`).
- `scripts/seed_dev_users.sql` usa `ON CONFLICT (id) DO NOTHING`: re-correrlo **no** actualiza filas existentes. Para cambiar datos ya seedeados (ej. el correo de los acudientes) usar `UPDATE` directo: `UPDATE guardians SET email='...' WHERE is_primary = true;`

## Tests y verificación

- Al verificar por `curl`, **no usar `-o /dev/null` en la llamada que prepara el escenario**: si falla, la comprobación siguiente mide otra cosa y parece un bug del código. Y comprobar el estado de la BD antes de aseverar: varias pruebas dieron 409 "correctos" por datos sobrantes de intentos previos, no por la regla que se quería probar.
- Los tests de repository (queries SQL reales, joins, M2M) no se pueden mockear con sentido. No existe infraestructura de fixtures contra Postgres real (`tests/integration/` vacío) — definir esa infraestructura antes de escribir `test_*_repository.py` en cualquier módulo.

## Edición de ficheros con scripts

- Al editar ficheros con scripts (`python3 - <<EOF` o `sed`), **poner `assert <ancla> in t` antes de cada `.replace()`**: una sustitución que no coincide no falla, deja el fichero intacto y el fallo aparece mucho después. Pasó con el `NAV_TITLES` de `PAEDashboard.jsx`, que difiere en alineación del de `TeacherDashboard.jsx`.
