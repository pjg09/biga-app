# Reporte de estado del MVP — Backend BIGA

> Auditoría del backend contra `docs/scope.md`. Generado el 2026-06-26 tras el commit
> `16e0ee8` ("agendatorio - filtros de listado, edicion de articulos y job de notificacion").
>
> **Actualización (2026-07-05):** se implementó la 3ª notificación (PAE no reclamado) con su
> barrido programado. El código del MVP está **completo**. El único pendiente real es
> **operativo, no de código**: credenciales de correo funcionales (§3). Las secciones §4 y §5
> quedan como registro histórico del faltante ya resuelto — ver la nota al inicio de cada una.

---

## 1. Veredicto

El scope (§1, *MVP — Alcance inicial*) prioriza **tres notificaciones automáticas** hacia el acudiente:

| # | Notificación del MVP | Estado |
|---|----------------------|--------|
| 1 | Inasistencia del estudiante a la primera hora | ✅ Completo |
| 2 | Registro de una sanción en el agendatorio | ✅ Completo (cerrado en `16e0ee8`) |
| 3 | **Estudiante PAE que no reclamó su alimento** | ✅ Completo (2026-07-05, ver abajo) |

Los tres flujos de notificación y todos los flujos de registro (PAE entrega, asistencia, agendatorio,
salidas) están implementados y el `beat_schedule` que dispara el barrido de PAE ya existe.

**Cierre de la 3ª notificación (2026-07-05):**
- `app/repositories/pae_repository.py` — `count_deliveries_on`, `get_no_claim_students_with_guardians`
  (inscritos activos sin entrega hoy y sin notificar aún, con acudiente primario), `get_institution_ids_past_pae_end`.
- `app/services/pae_notifier.py` — `PAENotifier.notify_no_claims`, mismo patrón que los otros notifiers.
- `app/jobs/pae_jobs.py` — `sweep_pae_no_claim` (beat, cross-tenant) → fan-out `notify_pae_no_claim(institution_id, date)`.
- `app/core/celery.py` — `beat_schedule` con el barrido cada 15 min.
- `tests/unit/test_pae_notifier.py` — 4 tests (0 entregas → no notifica; sin candidatos; envía+loguea SENT; fallo de correo → FAILED sin romper el lote). Suite completa: 53 passed.
- **Sin migración:** `Institution.pae_delivery_end_time` y `NotificationType.PAE_NO_CLAIM` ya existían en el esquema inicial.

> ⚠️ **Único pendiente (operativo, no de código):** el "✅ Completo" es a nivel de *código*. En la
> práctica **ningún correo sale todavía** porque la configuración de email no es funcional. Ver §3.

---

## 2. Lo que SÍ está completo

### Asistencia (`attendance`)
- Toma de lista de primera hora (`POST /attendance/first-class`), resolución de la clase
  `period_order=1` vía `user_groups → class_periods`.
- Encolado por evento: por cada `ABSENT` se hace `notify_absence_first_hour.apply_async(..., countdown=ATTENDANCE_GRACE_MINUTES*60)`.
- Marcar tardanza dentro de la ventana (`POST /attendance/records/{id}/arrived` → `LATE`); el job relee el estado y no notifica si el alumno llegó.
- Justificación por link público de un solo uso (`GET/POST /attendance/justify/{token}`).
- Notifier real: `app/services/attendance_notifier.py`.

### Agendatorio (`agendatorio`)
- CRUD de artículos del manual de convivencia, registro con firma (PNG a storage) + observaciones.
- Notificación al acudiente: `notify_discipline_record.delay(...)` encolado desde el service tras crear el registro.
- Notifier real: `app/services/discipline_notifier.py` (carga estudiante + acudiente primario, envía email, escribe en `notifications_log`).

### Salidas tempranas (`departures`)
- Registro (`POST /departures`) + `notify_early_departure.apply_async(..., countdown=10)`.
- Notifier real: `app/services/departure_notifier.py`.

### PAE (`pae`) — flujo de entrega/inscripción/reporte/auditoría
- Inscripción, entrega, reporte semanal y auditoría con cadena de doble hash HMAC.
- Identificación por documento (flujo MVP). Reconocimiento facial es fase 2 (deferral documentado en CLAUDE.md, **no** cuenta como faltante).

---

## 3. Hallazgo transversal: los correos NO se están enviando

Este punto afecta a **las tres** notificaciones, incluidas las marcadas como completas. El cableado del
código es correcto (los notifiers leen el email real del acudiente desde la BD y llaman `email.send()`),
pero la entrega real está bloqueada por configuración.

### 3.1 La API key de Resend es el placeholder
`RESEND_API_KEY` en `.env` vale literalmente `re_xxxxxxxxxxxx` — el mismo valor de `.env.example`,
no una key real.

### 3.2 Qué pasa en runtime con ese placeholder
`ResendEmailAdapter.send()` igualmente llama a `resend.Emails.send(...)`. Con una key inválida, la API
de Resend responde 401 y el SDK lanza excepción. Los notifiers la capturan (p.ej. `attendance_notifier.py:92-98`):

```python
try:
    self.email.send(guardian.email, subject, html)
except Exception as exc:
    notif_status = NotificationStatus.FAILED
    ...
```

Resultado: el job **no se rompe**, pero **cada notificación queda registrada en `notifications_log`
como `FAILED`** y el acudiente nunca recibe nada. El link de justificación sí se escribe en los logs del
worker (`attendance_notifier.py:87`), lo que permite probar el flujo en dev sin que salga el correo.

### 3.3 No basta con poner una key real — segundo bloqueante
Aunque se configure una `RESEND_API_KEY` válida, falta resolver `EMAIL_FROM=no-reply@biga.app`: Resend
solo entrega desde un **dominio verificado** en su panel. Sin verificar `biga.app` (registros SPF/DKIM):
- En cuenta de prueba, Resend solo entrega al email del dueño de la cuenta, no a correos arbitrarios de padres.
- Sin verificación de dominio, los envíos a acudientes reales fallan.

Para que lleguen correos a padres reales hacen falta **dos cosas que hoy no existen**: una API key real
**y** el dominio `biga.app` verificado en Resend.

### 3.4 Aclaración
No es un bug de código: es configuración/credenciales. La capa de adapter y los notifiers están bien
construidos. (La notificación de PAE no reclamado no llega ni a esta capa porque el task es un stub — ver §4.)

---

## 4. El faltante: notificación de PAE no reclamado — ✅ RESUELTO (2026-07-05)

> Esta sección describe el estado **antes** del cierre. Se conserva como registro. El código descrito
> como faltante ya existe; ver el resumen de cierre en §1.

Tres capas faltan o están incompletas. Es trabajo nuevo, no un ajuste menor.

### 4.1 El task Celery es un stub
`app/jobs/pae_jobs.py`:
```python
@celery_app.task
def notify_pae_no_claim(institution_id: str, delivery_date: str) -> None:
    pass
```
Comparado con los otros tres jobs, que delegan en un Notifier real vía `run_db_job`.

### 4.2 No existe `PAENotifier`
En `app/services/` hay `attendance_notifier.py`, `departure_notifier.py` y `discipline_notifier.py`,
pero **ningún** notifier de PAE. Hay que crearlo siguiendo el mismo patrón
(sesión propia vía `run_db_job`, `EmailAdapter`, escritura en `notifications_log`).

### 4.3 No existe la query de "inscritos sin entrega del día"
`app/repositories/pae_repository.py` tiene `get_enrolled_students_with_delivery_status`
(para el listado del día), pero ninguna query que devuelva los inscritos activos **sin** entrega hoy
**junto con su acudiente primario** para alimentar al notifier.

### 4.4 No hay `beat_schedule` — problema de fondo
`app/core/celery.py` **no define `beat_schedule` ni `add_periodic_task`**. El servicio `beat` está
levantado en `docker-compose.yml` pero corre en vacío. Las otras tres notificaciones se disparan por
evento (`.delay()` / `apply_async` desde el request), así que no dependen de beat. La de PAE es por
naturaleza **programada** ("al finalizar el descanso", scope §3.1) → **requiere** beat. Aunque el task
estuviera implementado, hoy nada lo dispararía.

### 4.5 Spec de la lógica del job (preservado del antiguo `plan-pae.md`)
Regla de negocio acordada para el job, que se conserva aquí porque era el único contenido vigente del
plan PAE ya eliminado:

```
SI COUNT(pae_deliveries WHERE delivery_date = hoy AND institution_id = X) = 0
    → No notificar. Se asume que el PAE no operó ese día.
SI COUNT > 0
    → Notificar a los acudientes de estudiantes con pae_enrollment activo
      (is_active=True, academic_year=año vigente) que NO tienen delivery hoy.
```
- El job debe programarse contra la hora de cierre del PAE de la institución.
- Multi-tenant: el job corre **sin JWT**, así que debe recibir/iterar `institution_id` explícitamente
  (regla crítica de CLAUDE.md), p.ej. `notify_pae_no_claim.delay(str(institution_id), str(delivery_date))`.

---

## 5. Bloqueante de diseño — ✅ RESUELTO (era un error de la auditoría)

La auditoría original afirmó que "no hay una hora de fin de PAE modelada". **Eso era incorrecto:**
el campo `Institution.pae_delivery_end_time` (`Time`, `nullable=False`) **ya existía** en el modelo y en
la migración inicial. No hizo falta migración.

Solución adoptada (Opción B, sin el costo que se le atribuía): Celery beat corre un **barrido cada 15 min**
(`sweep_pae_no_claim`) que lee `pae_delivery_end_time` de cada institución y dispara la notificación para
las que ya cerraron su horario hoy. El barrido es cross-tenant por diseño (es el scheduler); el trabajo
por institución lleva `institution_id` explícito. Idempotencia: el `PAENotifier` omite a los estudiantes
que ya tienen un log `PAE_NO_CLAIM` hoy, así que re-correr el barrido no duplica correos. Guarda adicional:
si hubo **0 entregas** ese día se asume que el PAE no operó y no se notifica a nadie.

---

## 6. Trabajo restante para cerrar el MVP

Todo el código del MVP está implementado. Lo que queda es **operativo**, no de desarrollo:

1. **Habilitar el envío real de correo (§3):** configurar una `RESEND_API_KEY` válida **y** verificar el
   dominio de `EMAIL_FROM` en Resend (SPF/DKIM). Sin esto, ninguna notificación —de ningún módulo— llega
   al acudiente, aunque el código esté completo.
2. **Levantar el servicio `beat`** en producción (ya está en `docker-compose.yml`) para que el barrido
   de PAE corra; sin `beat` activo, la notificación de no reclamo nunca se dispara.
3. **Verificar `pae_delivery_end_time`** por institución en los datos de seed/producción (es `NOT NULL`,
   pero conviene confirmar que la hora cargada es la real de cierre del PAE).

### Deuda técnica conocida (no bloquea el MVP)
- No hay tests de repositorio contra Postgres real (`tests/integration/` vacío). Las queries nuevas de
  `pae_repository.py` (incluida la de no reclamo con sus subconsultas) solo están cubiertas indirectamente
  vía los mocks del notifier. Validarlas end-to-end requiere levantar el stack y correr el flujo real.
- El barrido re-encola un job por institución cada 15 min por el resto del día aunque ya no haya a quién
  notificar (la idempotencia lo hace inofensivo, pero es trabajo redundante). Optimizable con un marcador
  "barrido hecho hoy" por institución si el volumen lo justifica.

---

*Reporte de auditoría — Backend BIGA | 2026-06-26*
