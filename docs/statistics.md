# Estadísticas del admin — referencia funcional

> Extraído de `docs/admin.md`, que pasaba de 30 KB. La consola de gestión (personal,
> académico, PAE) sigue allí; los horarios, en `docs/schedule.md`.

Dos cosas distintas con nombre parecido: **`GET /admin/stats`** es la foto del día que alimenta
el Resumen del dashboard, y **`/admin/stats/*`** es la sección de análisis con series históricas.

## Estadísticas

### `GET /admin/stats`
Snapshot del día y semana actuales (`AdminService.get_stats`, `AdminRepository`). Todos los
conteos filtran por `institution_id`.

```json
{
  "date": "2026-08-14",
  "students_active": 4, "staff_total": 3, "teachers": 1, "pae_operators": 1,
  "pae_enrolled": 4, "pae_delivered_today": 2, "pae_delivered_week": 2, "pae_claim_rate": 50.0,
  "attendance_present_today": 0, "attendance_absent_today": 0, "attendance_late_today": 0,
  "attendance_justified_today": 0, "attendance_rate_today": 0.0,
  "departures_today": 0,
  "discipline_records": 0, "discipline_leve": 0, "discipline_moderada": 0, "discipline_grave": 0,
  "notifications_sent": 12, "notifications_failed": 0, "notifications_pending": 0
}
```

`pae_claim_rate` = % de inscritos que reclamaron **hoy** (no acumulado). `attendance_rate_today`
= (presentes + tardanzas) / total de registros de hoy — una tardanza cuenta como asistencia
para esta métrica, aunque dispare la notificación de inasistencia si no se marca a tiempo
(ver `docs/attendance.md`).

---

## Sección de Estadísticas (`/admin/stats/*`)

Cinco endpoints con ventana temporal (`?days=`, 7–365) sobre `StatsRepository` →
`StatsService`. El `GET /admin/stats` de arriba sigue existiendo y no cambia: es la foto del
día que alimenta el *Resumen*; esto es la serie histórica y los cruces por salón, hora y
estudiante.

| Endpoint | Qué responde |
|---|---|
| `/stats/overview` | KPIs con variación contra el período anterior + **alertas accionables** |
| `/stats/attendance` | Serie diaria, por salón, por día de semana, por hora, cobertura, embudo de justificación |
| `/stats/pae` | Serie de reclamo, cobertura por grado, inscritos que dejaron de reclamar |
| `/stats/discipline` | Casos por mes y gravedad, artículos más citados, reincidentes |
| `/stats/risk` | Estudiantes ordenados por señales de riesgo |

### Las tres reglas que sostienen el módulo

1. **Ningún porcentaje sobre una muestra minúscula.** Con 3 registros, faltar a uno da "33% de
   ausentismo" y encabeza cualquier ranking por encima de un caso real de 40 ausencias sobre
   200. Por eso `MIN_REGISTROS_ESTUDIANTE = 10` (por debajo, el ausentismo del estudiante
   **no se calcula**: queda en 0 y solo entra en la tabla si tiene otra señal) y por eso toda
   tasa viaja con su `n`, que el front muestra al lado y usa para atenuar la barra.
2. **Una tasa sin cobertura de registro es propaganda.** `cobertura` = bloques del horario con
   lista tomada / bloques programados. Si vale 47%, la "asistencia del 90%" describe a los
   docentes que registran, no al colegio. Va en el resumen, encabeza la vista de asistencia y
   dispara la **primera** alerta por debajo del 70%.
3. **Comparar contra el período anterior**, contiguo y de igual longitud. Sin período previo
   con datos, `Delta.disponible = False` y el front escribe "sin período comparable" en vez de
   un +340% contra una semana vacía.

### Puntaje de riesgo

`StatsService._risk_score` combina cuatro señales que ya recolectamos: ausentismo (hasta 60
puntos), casos de convivencia (20), salidas anticipadas (10) y estar inscrito al PAE sin
reclamar (10). **No es un modelo**: es un criterio de priorización explícito y auditable, y el
ausentismo pesa más que el resto junto porque es el único con evidencia de predecir deserción.
Umbrales: `alto` con ausentismo ≥ 20% (o puntaje ≥ 45), `medio` con ≥ 10% o dos casos.

### Un inscrito "inactivo" en el PAE se mide por días desde la última entrega

`DIAS_PAE_INACTIVO = 14`. La primera versión pedía **cero entregas en todo el período** y por
eso no veía al que reclamó durante dos meses y dejó de hacerlo hace tres semanas — que es
justo el caso a detectar (ración perdida + posible deserción). El fallo era invisible con los
datos de juguete de desarrollo; se destapó al generar historia real con
`scripts/seed_stats_demo.py`. Si se toca esta consulta, comprobarla contra datos con volumen.

### SQL crudo en `StatsRepository`

Único repositorio del proyecto que usa `text()` en vez del ORM: son agregaciones
(`generate_series` para rellenar días sin datos, `FILTER (WHERE …)`, ventanas) que no
devuelven entidades sino filas de números. **Todos los parámetros van bindeados** y toda
consulta filtra `institution_id`, también en las tablas unidas —
`attendance_justifications` no lo tiene, así que su tenant se valida por el join con
`attendance_records`.

> Cuidado con `:param::tipo`: SQLAlchemy parsea el `::` pegado a un parámetro bindeado como si
> empezara otro parámetro y falla con `syntax error at or near ":"`. Usar `CAST(:param AS date)`.

---
