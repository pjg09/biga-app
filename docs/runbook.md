# BIGA — Runbook: cómo levantar el stack

Guía operativa para levantar y trabajar con el proyecto en local. Todos los comandos
se corren **desde la raíz del repo** salvo que se indique lo contrario:

```
/BIGA
```

---

## 1. Prerrequisitos

- Docker + Docker Compose.
- Dos archivos de entorno (gitignored, ya deberían existir en tu máquina):
  - **`.env`** (raíz) — config del backend. Plantilla: `.env.example`.
  - **`web/.env`** — debe contener `VITE_API_URL=http://localhost:8000`. Sin esto el frontend hace `fetch` a `undefined/...` y falla en silencio.

Verificar que no falten vars nuevas en `.env` tras un pull:

```bash
diff <(grep -oP '^[A-Z_]+(?==)' .env.example | sort) <(grep -oP '^[A-Z_]+(?==)' .env | sort)
```

Si `worker`/`beat` crashean al arrancar con `ValueError: Field required`, es esto: falta una var en `.env`.

---

## 2. Servicios y puertos

| Servicio | Puerto host | Para qué |
|---|---|---|
| `api` | `8000` | FastAPI — API + Swagger en `/docs` |
| `web` | `5173` | Frontend Vite (React) |
| `postgres` | `5433` → 5432 | BD (desde fuera de Docker: `localhost:5433`) |
| `redis` | `6379` | Broker de Celery |
| `minio` | `9000` (API) / `9001` (consola) | Storage S3-compatible |
| `worker` | — | Celery worker (jobs por evento) |
| `beat` | — | Celery beat (job programado del PAE) |
| `storage-init` | — | Crea el bucket en MinIO y sale |

### ⚠️ Ajustes temporales de desarrollo — revertir antes de producción

| Variable | Valor de producción | Valor local actual | Por qué se bajó |
|---|---|---|---|
| `ATTENDANCE_GRACE_MINUTES` | **50** | **2** (desde 2026-08-11) | Es la ventana entre tomar lista en primera hora y avisar al acudiente. Con 50 min cada prueba del flujo de inasistencia cuesta casi una hora de espera. **Con 2 minutos el correo sale antes de que al estudiante le dé tiempo a llegar**, así que no puede quedarse así con docentes reales. |

`.env` está gitignored: el aviso también está como comentario junto a la variable, pero solo en la máquina donde se cambió. `.env.example` conserva el valor de producción.

---

## 3. Primer arranque (BD limpia)

```bash
# 1. Levantar todo el stack
docker compose up -d

# 2. Esperar a que la API responda
curl http://localhost:8000/health

# 3. Aplicar migraciones
docker compose exec api alembic upgrade head

# 4. Seed demo completo (3 usuarios, grupo 11A con horario semanal,
#    4 estudiantes + acudientes + matrículas, artículos de convivencia)
docker compose exec -T postgres psql -U biga -d biga < scripts/seed_dev_users.sql

# 5. Seed PAE (inscribe estudiantes y registra entregas de la semana con doble hash).
#    Es Python porque los hashes dependen de PAE_SIGNING_SECRET.
docker compose exec -T api python -m scripts.seed_pae
```

Abrir el frontend: **http://localhost:5173**

---

## 4. Arranque diario (ya tenías datos)

```bash
docker compose up -d
curl http://localhost:8000/health
```

Si hubo cambios de esquema desde la última vez: `docker compose exec api alembic upgrade head`.

---

## 5. Credenciales de prueba

Del seed `seed_dev_users.sql` (una por rol, contraseña `password123`):

| Email | Rol | Dashboard |
|---|---|---|
| `teacher@iedemo.edu.co` | TEACHER | `/dashboard/teacher` |
| `pae@iedemo.edu.co` | PAE_OPERATOR | `/dashboard/pae` |
| `admin@iedemo.edu.co` | ADMIN | `/dashboard/admin` |

Documentos de los 4 estudiantes demo: `1010100001`–`1010100004` (Mariana, Santiago, Valentina, Mateo — grupo 11A).

Token JWT para pruebas manuales por `curl` (OAuth2, form-urlencoded — **no** JSON):

```bash
export TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d "username=teacher@iedemo.edu.co&password=password123" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
```

---

## 6. Reconstruir tras cambios de código

- **Backend (`api/`)**: uvicorn recarga solo. Si cambiás dependencias: `docker compose up -d --build api`.
- **Jobs Celery (`app/jobs/`)**: el `worker` **no** tiene autoreload. Recargar sin reiniciar el contenedor (evita el bug de AppArmor de `docker stop`):
  ```bash
  docker compose exec worker python -c "import os, signal; os.kill(1, signal.SIGHUP)"
  ```
- **Frontend (`web/`)**: Vite tiene HMR, no hay que hacer nada. **Excepción**: si agregás una dependencia npm nueva, hay que renovar el volumen anónimo `node_modules` (ver §8).

---

## 7. Tests

Desde `api/`, en contenedor efímero (sin levantar servicios, instala dev deps):

```bash
docker compose run --rm --no-deps api sh -c "pip install -q -r requirements-dev.txt && pytest tests/unit -q"
```

Solo un archivo/test:

```bash
docker compose run --rm --no-deps api sh -c "pip install -q -r requirements-dev.txt && pytest tests/unit/test_attendance_service.py -q"
```

> Los tests de `tests/integration/` requieren Postgres real y aún no tienen fixtures — no correrlos todavía.

---

## 8. Problemas conocidos y workarounds

**`docker stop` / `restart` da "permission denied" (AppArmor).**
No uses `docker compose restart <svc>`. Para recrear un contenedor:

```bash
sudo kill -9 $(docker inspect --format '{{.State.Pid}}' <container_id_o_nombre>)
```

**Vite: `Failed to resolve import "..."` tras agregar una dependencia npm.**
El servicio `web` monta un volumen anónimo en `/app/node_modules` que tapa el de la imagen. Hay que rebuildear renovando ese volumen (y matar el contenedor viejo con el workaround de AppArmor):

```bash
docker compose up -d --build --force-recreate --renew-anon-volumes web
# si falla al parar el contenedor viejo:
sudo kill -9 $(docker inspect --format '{{.State.Pid}}' biga-web-1)
docker rm -f biga-web-1
docker compose up -d --renew-anon-volumes web
```

**`worker`/`beat` crashean con `ValueError: Field required`.**
Falta una var en `.env`. Detectarla con el `diff` de §1.

**Conectar a Postgres desde fuera de Docker** (TablePlus, psql local): `localhost:5433`, no `postgres:5432`.

**Correos**: sin API key real de Resend el correo no sale, pero el enlace de justificación queda en los logs del worker (`docker compose logs worker`).

---

## 9. Comandos útiles

```bash
docker compose logs -f api          # logs de la API en vivo
docker compose logs -f worker       # logs del worker (jobs, enlaces de justificación)
docker compose exec api alembic check   # detectar drift entre modelos y BD
docker compose ps                   # estado de los contenedores
docker compose down                 # bajar el stack (conserva volúmenes/datos)
docker compose down -v              # bajar y BORRAR datos (empezar de cero)
```

Swagger / OpenAPI UI: **http://localhost:8000/docs**
Consola de MinIO: **http://localhost:9001**
