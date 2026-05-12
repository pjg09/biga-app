# BIGA — Próximos pasos

Documento de referencia para el equipo. Refleja el estado actual de avance y qué se debe construir a continuación.

---

## Estado actual

| Componente | Estado |
|---|---|
| Arquitectura y decisiones técnicas | Documentado en `docs/architecture.md` |
| Esquema de base de datos | Documentado en `docs/database-schema.md` |
| Scaffolding del monorepo (`api/` + `web/`) | Completo |
| Stack Docker (api, worker, beat, postgres, redis, minio) | Funcionando |
| Modelos SQLAlchemy | Completo |
| Migración inicial Alembic | Completo |
| Autenticación (JWT) | Pendiente |
| Módulos operativos | Pendiente |

---

## Objetivo inmediato — Modelos SQLAlchemy + Primera migración

Traducir el esquema de `docs/database-schema.md` a modelos ORM y generar la migración que crea todas las tablas en PostgreSQL.

### Archivos a crear en `api/app/models/`

| Archivo | Contenido |
|---|---|
| `enums.py` | Todos los ENUMs del proyecto centralizados |
| `institution.py` | Tabla `institutions` |
| `grade.py` | Tabla `grades` |
| `group.py` | Tabla `groups` |
| `class_period.py` | Tabla `class_periods` |
| `user.py` | Tabla `users` |
| `user_group.py` | Tabla `user_groups` |
| `student.py` | Tabla `students` |
| `student_group.py` | Tabla `student_groups` |
| `guardian.py` | Tabla `guardians` |
| `pae.py` | Tablas `pae_enrollments` + `pae_deliveries` |
| `attendance.py` | Tablas `attendance_records` + `attendance_tokens` + `attendance_justifications` |
| `agendatorio.py` | Tablas `convivencia_articles` + `discipline_records` + `discipline_record_articles` |
| `departure.py` | Tabla `early_departures` |
| `notification.py` | Tabla `notifications_log` |
| `import_job.py` | Tabla `import_jobs` |

### Convenciones en los modelos

- IDs: `UUID` generado en la aplicación con `default=uuid4`
- `created_at` en todas las tablas con `server_default=func.now()`
- Typed annotations con `Mapped[T]` y `mapped_column()` — SQLAlchemy 2.x style
- ENUMs como tipos nativos de PostgreSQL (`native_enum=True`)
- Índices definidos en `__table_args__` con `Index()`

### Comandos para ejecutar al terminar los modelos

```bash
# Generar la migración
docker compose exec api alembic revision --autogenerate -m "initial schema"

# Revisar el archivo generado en api/alembic/versions/ antes de aplicar

# Aplicar la migración
docker compose exec api alembic upgrade head

# Verificar tablas creadas
docker compose exec postgres psql -U biga -c "\dt"
docker compose exec postgres psql -U biga -c "\dT"
```

### Criterio de éxito

- `\dt` lista las 18 tablas
- `\dT` lista los 9 ENUMs nativos
- `alembic current` muestra la revisión aplicada sin errores

---

## Backlog (en orden de prioridad)

1. **Autenticación** — login de docente con JWT. Prerequisito de todos los módulos.
2. **Módulo PAE** — el más autocontenido. Buen punto de partida.
3. **Módulo Asistencia** — incluye la lógica de tokens de justificación.
4. **Módulo Agendatorio** — incluye captura de firma y selección de artículos.
5. **Módulo Salidas Tempranas** — el más simple de los cuatro.
6. **Carga masiva Excel** — import_jobs + procesamiento async.

---

*Documento de próximos pasos — BIGA APP | Mayo 2026*
