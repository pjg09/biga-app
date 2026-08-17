# BIGA — Despliegue (Railway)

> Cómo llega el código a producción y qué pasa exactamente al hacer push. Para levantar el
> entorno **local**, ver `docs/runbook.md`.

---

## Lo primero, porque es lo que más se pregunta

**Un push a `main` NO aplica migraciones por sí mismo.** Ningún workflow de GitHub Actions tiene
credenciales de producción ni ejecuta Alembic. Lo que hace cada uno:

| Workflow | Cuándo | Qué hace |
|---|---|---|
| `test.yml` | push y PR a `main` | Tests unitarios contra una Postgres **efímera del runner**. No toca la BD real. |
| `commitlint.yml` | PR a `main` | Valida los mensajes de commit (Conventional Commits). |
| `release.yml` | push a `main` | `semantic-release`: tag y release en GitHub. **No despliega.** |

Las migraciones las aplica **Railway al arrancar el contenedor**, no el push. La cadena real es:

```
push a main → Railway detecta el commit → build de la imagen → arranca el contenedor
            → entrypoint.railway.sh → alembic upgrade head → uvicorn
```

Si Railway no tiene auto-deploy activado para `main`, el push no cambia nada en producción. Esa
conexión se configura en el panel de Railway: **no hay `railway.json` ni `Procfile` en el repo**.

---

## Los tres procesos del backend salen de un solo contenedor

Railway no permite fijar el start command por servicio desde la CLI, así que el rol se elige con
la variable `PROCESS_TYPE`, que sí es manejable, y lo resuelve `api/entrypoint.railway.sh`:

| `PROCESS_TYPE` | Arranca | Detalle |
|---|---|---|
| `api` (default) | `alembic upgrade head` + uvicorn | **Único que migra** |
| `worker` | Celery worker | `--concurrency=2 --without-gossip --without-mingle` |
| `beat` | Celery beat | `--schedule /tmp/celerybeat-schedule` |

Tres cosas que parecen detalles y no lo son:

- **Solo el proceso `api` migra.** Si migraran también worker y beat, tres réplicas competirían
  por el lock de Alembic en cada despliegue.
- **`--concurrency=2` es obligatorio.** Sin él, Celery mira los núcleos del *host* de Railway (48)
  y levanta 48 procesos con una copia entera de la app cada uno: ~1 GB de RAM sin procesar una
  sola tarea. El límite de CPU del contenedor no lo evita — es un cgroup y `os.cpu_count()` sigue
  viendo los 48. Las tareas son envíos de correo (I/O, de a uno): con 2 sobra.
- **El schedule de beat va a `/tmp`.** El filesystem de Railway es efímero y se pierde en cada
  deploy, que es lo correcto para un scheduler sin estado propio.

Las imágenes de producción son `api/Dockerfile.railway` y `web/Dockerfile.railway` (las de al lado,
sin sufijo, son las de desarrollo y reciben el comando desde `docker-compose`). Se seleccionan con
la variable de servicio `RAILWAY_DOCKERFILE_PATH`.

> **El frontend congela sus variables en el build.** Vite reemplaza las `VITE_*` dentro del bundle
> en tiempo de compilación; no las lee en runtime. Cambiar `VITE_API_URL` **obliga a reconstruir**,
> no basta con redesplegar. El runtime sirve el `dist` con `serve -s`, y ese `-s` es lo que hace que
> recargar en `/justificar/{token}` o `/dashboard` entre a la SPA en vez de dar 404.

---

## Antes de desplegar: comprobar que las migraciones no van a abortar

`entrypoint.railway.sh` corre con `set -e`. Si `alembic upgrade head` falla, uvicorn no arranca y
**el deploy se cae** (Railway mantiene la versión anterior; no se corrompe nada, pero no sube).

Dos migraciones abortan **a propósito** si encuentran datos que violan los invariantes que
introducen — un `EXCLUDE` no admite `NOT VALID`, así que o los datos están limpios o el
`ALTER TABLE` falla:

```sql
-- f2d5a81c9e37 — dos clases del mismo salón solapadas en el reloj
SELECT count(*) FROM class_periods a JOIN class_periods b
  ON a.group_id = b.group_id AND a.day_of_week = b.day_of_week AND a.id < b.id
 AND a.start_time < b.end_time AND b.start_time < a.end_time;

-- b7e4f1c8a209 — un docente en dos salones a la vez
SELECT count(*) FROM class_periods a JOIN class_periods b
  ON a.user_id = b.user_id AND a.day_of_week = b.day_of_week AND a.id < b.id
 AND a.start_time < b.end_time AND b.start_time < a.end_time;
```

Ambas deben dar **0**. Si no, las migraciones listan los conflictos con nombre, salón y horas en el
mensaje de error, para poder corregirlos antes de reintentar. La segunda es la que más probabilidad
tiene de fallar en una BD con horario ya cargado: esa regla no existía antes y nada impedía
crear el conflicto.

> `worker` y `beat` arrancan con el código nuevo **sin esperar** a que el `api` termine de migrar.
> Sus tareas actuales son envíos de correo y no tocan `class_periods`, así que la ventana es
> inocua; tenerlo presente si alguna migración futura cambia una tabla que los jobs escriben.

---

## Variables de entorno

Sin estas la API no arranca — `Settings()` las exige sin default y falla al importar:

| Variable | Nota |
|---|---|
| `DATABASE_URL` | **Debe** empezar por `postgresql+asyncpg://` (ni `postgresql://` ni `postgres://`) |
| `REDIS_URL` | Broker de Celery. En producción **no publicar el puerto** fuera de la red interna: los OTP de recuperación viajan en claro por él |
| `SECRET_KEY` | Firma de los JWT |
| `PAE_SIGNING_SECRET` | Clave de los hashes del PAE. **Cambiarla invalida todas las firmas anteriores** y la auditoría marcará como manipuladas las entregas ya registradas |
| `RESEND_API_KEY`, `EMAIL_FROM` | Correo saliente |
| `LEADS_NOTIFY_EMAIL` | Destinatario del aviso de demo de la landing |
| `STORAGE_ENDPOINT_URL`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_BUCKET_NAME` | Object storage (fotos, firmas, adjuntos) |

Con default, pero conviene fijarlas en producción:

- `EMAIL_PROVIDER` — default `resend`. **`mailtrap` no entrega a nadie**: captura todo en una
  bandeja de QA. El default no se deduce de `debug` ni de ninguna otra señal de entorno
  precisamente para que un despliegue no caiga en él por descuido.
- `FRONTEND_URL` — se usa en los enlaces de los correos (justificación, bienvenida). Si apunta a
  `localhost`, las familias reciben enlaces que no abren.
- `CORS_ORIGINS` — el dominio real del front.
- `ATTENDANCE_GRACE_MINUTES` — 50 en producción. Si está en 2, es un ajuste de QA sin revertir.
- `TZ=America/Bogota` — la imagen ya la fija; **la BD también la necesita**. Sin ella, `date.today()`
  adelanta un día entre las 19:00 y medianoche y las fechas entran mal en `attendance_records`,
  `pae_deliveries` y `early_departures`. No es presentación: es el dato.

---

## Después de desplegar

```bash
curl https://<api>/health                 # 200
curl https://<api>/docs                   # OpenAPI
```

Y comprobar en la consola de Railway que los tres servicios del backend están arriba: si `beat` no
corre, **el barrido de no reclamo del PAE no se ejecuta** y ninguna familia recibe ese aviso — sin
error visible en ningún sitio, porque no falla nada: simplemente no ocurre.
