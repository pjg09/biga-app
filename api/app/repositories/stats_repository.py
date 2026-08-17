"""Consultas agregadas para el módulo de Estadísticas del admin.

Por qué SQL crudo (`text()`) y no el ORM, a diferencia del resto de repositorios:
estas consultas son agregaciones analíticas — `generate_series` para rellenar días
sin datos, `FILTER (WHERE ...)`, ventanas, `NULLIF` para no dividir por cero. En
ORM quedan ilegibles y no aportan nada, porque no devuelven entidades sino filas
de números. **Todos los parámetros van bindeados** (`:inst`, `:desde`), nunca
interpolados: son datos del token y de la query string.

Regla de aislamiento multi-tenant (CLAUDE.md): toda consulta lleva
`institution_id = :inst` en su WHERE, incluidas las que unen varias tablas — y en
ese caso, en **todas** las tablas que lo tengan, no solo en la principal.
"""
from datetime import date as PyDate
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class StatsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _rows(self, sql: str, **params) -> list[dict]:
        result = await self.session.execute(text(sql), params)
        return [dict(r) for r in result.mappings().all()]

    async def _row(self, sql: str, **params) -> dict:
        rows = await self._rows(sql, **params)
        return rows[0] if rows else {}

    # ── Asistencia ────────────────────────────────────────────────────

    async def attendance_daily(
        self, institution_id: UUID, desde: PyDate, hasta: PyDate
    ) -> list[dict]:
        """Serie diaria de asistencia. `generate_series` deja los días sin
        registros con ceros en vez de ausentes de la serie: un hueco en una línea
        de tendencia se lee como caída, no como "no se tomó lista"."""
        return await self._rows(
            """
            SELECT d::date AS dia,
                   COALESCE(a.presentes, 0)   AS presentes,
                   COALESCE(a.ausentes, 0)    AS ausentes,
                   COALESCE(a.tardanzas, 0)   AS tardanzas,
                   COALESCE(a.justificadas, 0) AS justificadas
            FROM generate_series(:desde, :hasta, interval '1 day') d
            LEFT JOIN (
                SELECT date,
                       count(*) FILTER (WHERE status = 'PRESENT')   AS presentes,
                       count(*) FILTER (WHERE status = 'ABSENT')    AS ausentes,
                       count(*) FILTER (WHERE status = 'LATE')      AS tardanzas,
                       count(*) FILTER (WHERE status = 'JUSTIFIED') AS justificadas
                FROM attendance_records
                WHERE institution_id = :inst AND date BETWEEN :desde AND :hasta
                GROUP BY date
            ) a ON a.date = d::date
            ORDER BY dia
            """,
            inst=institution_id, desde=desde, hasta=hasta,
        )

    async def attendance_by_group(
        self, institution_id: UUID, desde: PyDate, hasta: PyDate
    ) -> list[dict]:
        return await self._rows(
            """
            SELECT gr.name AS grado, g.name AS salon, g.id AS group_id,
                   count(*) AS registros,
                   count(*) FILTER (WHERE ar.status IN ('PRESENT','LATE')) AS asistidos,
                   count(*) FILTER (WHERE ar.status = 'ABSENT')            AS ausentes,
                   count(DISTINCT ar.student_id)                           AS estudiantes
            FROM attendance_records ar
            JOIN groups g  ON g.id = ar.group_id
            JOIN grades gr ON gr.id = g.grade_id
            WHERE ar.institution_id = :inst
              AND g.institution_id = :inst
              AND ar.date BETWEEN :desde AND :hasta
            GROUP BY gr.name, gr.level, g.name, g.id
            ORDER BY gr.level, g.name
            """,
            inst=institution_id, desde=desde, hasta=hasta,
        )

    async def attendance_by_weekday(
        self, institution_id: UUID, desde: PyDate, hasta: PyDate
    ) -> list[dict]:
        """Ausentismo por día de la semana. Lunes y viernes suelen concentrarlo;
        saberlo cambia dónde se programan las actividades que no se pueden perder."""
        return await self._rows(
            """
            SELECT EXTRACT(ISODOW FROM date)::int AS dow,
                   count(*) AS registros,
                   count(*) FILTER (WHERE status IN ('PRESENT','LATE')) AS asistidos
            FROM attendance_records
            WHERE institution_id = :inst AND date BETWEEN :desde AND :hasta
            GROUP BY dow
            ORDER BY dow
            """,
            inst=institution_id, desde=desde, hasta=hasta,
        )

    async def attendance_by_period(
        self, institution_id: UUID, desde: PyDate, hasta: PyDate
    ) -> list[dict]:
        """Ausentismo por hora de clase. Una caída fuerte después del descanso es
        fuga de estudiantes a media jornada, y se corrige con vigilancia, no con
        circulares a las familias."""
        return await self._rows(
            """
            SELECT cp.period_order AS orden,
                   min(cp.start_time)::text AS desde_hora,
                   count(*) AS registros,
                   count(*) FILTER (WHERE ar.status IN ('PRESENT','LATE')) AS asistidos
            FROM attendance_records ar
            JOIN class_periods cp ON cp.id = ar.class_period_id
            WHERE ar.institution_id = :inst
              AND cp.institution_id = :inst
              AND ar.date BETWEEN :desde AND :hasta
            GROUP BY cp.period_order
            ORDER BY cp.period_order
            """,
            inst=institution_id, desde=desde, hasta=hasta,
        )

    async def attendance_coverage(
        self, institution_id: UUID, desde: PyDate, hasta: PyDate, academic_year: int
    ) -> dict:
        """Cobertura de toma de lista: bloques con lista tomada / bloques
        programados en el horario.

        **Es la métrica que valida a las demás.** Si solo se toma lista en el 40%
        de los bloques, una "tasa de asistencia del 95%" no dice nada del colegio,
        dice algo del 40% que sí registra. Va primero en la vista por eso.
        """
        return await self._row(
            """
            WITH dias AS (
                SELECT d::date AS dia, EXTRACT(ISODOW FROM d)::int AS dow
                FROM generate_series(:desde, :hasta, interval '1 day') d
            ),
            programados AS (
                SELECT dias.dia, cp.id AS class_period_id
                FROM dias
                JOIN class_periods cp ON cp.day_of_week = dias.dow
                JOIN groups g ON g.id = cp.group_id AND g.academic_year = :anio
                WHERE cp.institution_id = :inst AND g.institution_id = :inst
            )
            SELECT count(*) AS programados,
                   count(*) FILTER (WHERE EXISTS (
                       SELECT 1 FROM attendance_records ar
                       WHERE ar.class_period_id = programados.class_period_id
                         AND ar.date = programados.dia
                         AND ar.institution_id = :inst
                   )) AS tomados
            FROM programados
            """,
            inst=institution_id, desde=desde, hasta=hasta, anio=academic_year,
        )

    async def justification_funnel(
        self, institution_id: UUID, desde: PyDate, hasta: PyDate
    ) -> dict:
        """De las inasistencias notificadas, cuántas responde la familia.

        `attendance_justifications` no denormaliza `institution_id` (ver
        CLAUDE.md): el tenant se valida por el join con `attendance_records`.
        """
        return await self._row(
            """
            SELECT count(*) AS ausencias,
                   count(*) FILTER (WHERE EXISTS (
                       SELECT 1 FROM attendance_justifications j
                       WHERE j.attendance_record_id = ar.id
                   )) AS justificadas,
                   count(*) FILTER (WHERE ar.absence_closed_at IS NOT NULL) AS cerradas
            FROM attendance_records ar
            WHERE ar.institution_id = :inst
              AND ar.date BETWEEN :desde AND :hasta
              AND ar.status = 'ABSENT'
            """,
            inst=institution_id, desde=desde, hasta=hasta,
        )

    # ── PAE ───────────────────────────────────────────────────────────

    async def pae_daily(
        self, institution_id: UUID, desde: PyDate, hasta: PyDate, academic_year: int
    ) -> list[dict]:
        """Entregas por día contra el número de inscritos activos.

        El inscrito se cuenta como constante del período (el de hoy), no día a
        día: `pae_enrollments` no guarda histórico de bajas, así que reconstruir
        "cuántos había inscritos el martes pasado" sería inventarlo.
        """
        return await self._rows(
            """
            SELECT d::date AS dia, COALESCE(p.entregas, 0) AS entregas
            FROM generate_series(:desde, :hasta, interval '1 day') d
            LEFT JOIN (
                SELECT delivery_date, count(*) AS entregas
                FROM pae_deliveries
                WHERE institution_id = :inst
                  AND delivery_date BETWEEN :desde AND :hasta
                GROUP BY delivery_date
            ) p ON p.delivery_date = d::date
            ORDER BY dia
            """,
            inst=institution_id, desde=desde, hasta=hasta,
        )

    async def pae_coverage_by_grade(
        self, institution_id: UUID, academic_year: int
    ) -> list[dict]:
        """Inscritos al PAE sobre matriculados, por grado. Una cobertura baja en
        un grado concreto suele ser un trámite sin hacer, no falta de necesidad."""
        return await self._rows(
            """
            SELECT gr.name AS grado, gr.level AS nivel,
                   count(DISTINCT sg.student_id) AS matriculados,
                   count(DISTINCT sg.student_id) FILTER (WHERE pe.id IS NOT NULL) AS inscritos
            FROM student_groups sg
            JOIN groups g  ON g.id = sg.group_id AND g.academic_year = :anio
            JOIN grades gr ON gr.id = g.grade_id
            JOIN students s ON s.id = sg.student_id AND s.is_active = true
            LEFT JOIN pae_enrollments pe
                   ON pe.student_id = sg.student_id
                  AND pe.institution_id = :inst
                  AND pe.academic_year = :anio
                  AND pe.is_active = true
            WHERE g.institution_id = :inst
              AND s.institution_id = :inst
              AND sg.is_active = true
            GROUP BY gr.name, gr.level
            ORDER BY gr.level
            """,
            inst=institution_id, anio=academic_year,
        )

    async def pae_inactive_enrolled(
        self, institution_id: UUID, desde: PyDate, hasta: PyDate, academic_year: int,
        dias_umbral: int,
    ) -> list[dict]:
        """Inscritos que llevan `dias_umbral` días sin reclamar (o que no
        reclamaron nunca).

        El criterio es **días desde la última entrega**, no "cero entregas en el
        período": la primera versión pedía cero y por eso no veía al que reclamó
        durante dos meses y dejó de hacerlo hace tres semanas — que es
        exactamente el caso que hay que detectar. Con datos de juguete el fallo
        era invisible; se destapó al generar historia real.

        Es la métrica con consecuencia económica directa (raciones que se piden y
        se pierden) y, a la vez, señal temprana de deserción.
        """
        return await self._rows(
            """
            WITH ultimas AS (
                SELECT s.id AS student_id,
                       s.first_name || ' ' || s.last_name AS nombre,
                       s.document_number AS documento,
                       gr.name AS grado, g.name AS salon,
                       (SELECT max(delivery_date) FROM pae_deliveries pd
                         WHERE pd.student_id = s.id
                           AND pd.institution_id = :inst
                           AND pd.delivery_date <= :hasta) AS ultima_entrega
                FROM pae_enrollments pe
                JOIN students s ON s.id = pe.student_id AND s.is_active = true
                LEFT JOIN student_groups sg
                       ON sg.student_id = s.id AND sg.is_active = true
                LEFT JOIN groups g  ON g.id = sg.group_id AND g.academic_year = :anio
                LEFT JOIN grades gr ON gr.id = g.grade_id
                WHERE pe.institution_id = :inst
                  AND s.institution_id = :inst
                  AND pe.academic_year = :anio
                  AND pe.is_active = true
            )
            SELECT * FROM ultimas
            WHERE ultima_entrega IS NULL
               OR ultima_entrega < (CAST(:hasta AS date) - CAST(:umbral AS int))
            ORDER BY ultima_entrega NULLS FIRST, nombre
            LIMIT 50
            """,
            inst=institution_id, desde=desde, hasta=hasta, anio=academic_year,
            umbral=dias_umbral,
        )

    async def pae_service_days(
        self, institution_id: UUID, desde: PyDate, hasta: PyDate
    ) -> int:
        """Días con al menos una entrega. Divisor honesto para el promedio: en
        vacaciones o festivos no hubo servicio, y contarlos hunde la media."""
        row = await self._row(
            """
            SELECT count(DISTINCT delivery_date) AS dias
            FROM pae_deliveries
            WHERE institution_id = :inst AND delivery_date BETWEEN :desde AND :hasta
            """,
            inst=institution_id, desde=desde, hasta=hasta,
        )
        return int(row.get("dias") or 0)

    # ── Convivencia ───────────────────────────────────────────────────

    async def discipline_monthly(
        self, institution_id: UUID, desde: PyDate, hasta: PyDate
    ) -> list[dict]:
        """Casos por mes y gravedad máxima del caso.

        Un caso puede citar varios artículos; se le asigna la **gravedad más
        alta** de los que cita. Contar por artículo inflaría los números (un caso
        con tres artículos contaría tres veces) y haría la serie incomparable
        entre meses.
        """
        return await self._rows(
            """
            WITH casos AS (
                SELECT dr.id,
                       date_trunc('month', dr.date)::date AS mes,
                       max(CASE ca.severity
                               WHEN 'GRAVE' THEN 3 WHEN 'MODERADA' THEN 2 ELSE 1 END) AS sev
                FROM discipline_records dr
                LEFT JOIN discipline_record_articles dra ON dra.discipline_record_id = dr.id
                LEFT JOIN convivencia_articles ca
                       ON ca.id = dra.article_id AND ca.institution_id = :inst
                WHERE dr.institution_id = :inst
                  AND dr.date BETWEEN :desde AND :hasta
                GROUP BY dr.id, mes
            )
            SELECT mes,
                   count(*) AS casos,
                   count(*) FILTER (WHERE sev = 1) AS leve,
                   count(*) FILTER (WHERE sev = 2) AS moderada,
                   count(*) FILTER (WHERE sev = 3) AS grave
            FROM casos
            GROUP BY mes
            ORDER BY mes
            """,
            inst=institution_id, desde=desde, hasta=hasta,
        )

    async def discipline_top_articles(
        self, institution_id: UUID, desde: PyDate, hasta: PyDate
    ) -> list[dict]:
        return await self._rows(
            """
            SELECT ca.code AS codigo, ca.title AS titulo, ca.severity::text AS gravedad,
                   count(*) AS casos
            FROM discipline_record_articles dra
            JOIN convivencia_articles ca ON ca.id = dra.article_id
            JOIN discipline_records dr   ON dr.id = dra.discipline_record_id
            WHERE dr.institution_id = :inst
              AND ca.institution_id = :inst
              AND dr.date BETWEEN :desde AND :hasta
            GROUP BY ca.code, ca.title, ca.severity
            ORDER BY casos DESC, ca.code
            LIMIT 8
            """,
            inst=institution_id, desde=desde, hasta=hasta,
        )

    async def discipline_repeat_students(
        self, institution_id: UUID, desde: PyDate, hasta: PyDate
    ) -> list[dict]:
        """Reincidentes: 2+ casos en el período. Un estudiante con cinco casos no
        es cinco veces el mismo problema, es un caso de seguimiento individual."""
        return await self._rows(
            """
            SELECT s.id AS student_id,
                   s.first_name || ' ' || s.last_name AS nombre,
                   gr.name AS grado, g.name AS salon,
                   count(*) AS casos,
                   max(dr.date) AS ultimo
            FROM discipline_records dr
            JOIN students s ON s.id = dr.student_id
            LEFT JOIN student_groups sg ON sg.student_id = s.id AND sg.is_active = true
            LEFT JOIN groups g  ON g.id = sg.group_id
            LEFT JOIN grades gr ON gr.id = g.grade_id
            WHERE dr.institution_id = :inst
              AND s.institution_id = :inst
              AND dr.date BETWEEN :desde AND :hasta
            GROUP BY s.id, nombre, gr.name, g.name
            HAVING count(*) >= 2
            ORDER BY casos DESC, ultimo DESC
            LIMIT 20
            """,
            inst=institution_id, desde=desde, hasta=hasta,
        )

    # ── Estudiantes en riesgo ─────────────────────────────────────────

    async def student_risk(
        self, institution_id: UUID, desde: PyDate, hasta: PyDate, min_registros: int
    ) -> list[dict]:
        """Una fila por estudiante con las cuatro señales que ya recolectamos.

        `min_registros` corta a los que tienen tan pocos registros que un
        porcentaje no significa nada: con 2 registros, faltar a uno es "50% de
        ausentismo" y encabezaría la lista por encima de un caso real.
        """
        return await self._rows(
            """
            SELECT s.id AS student_id,
                   s.first_name || ' ' || s.last_name AS nombre,
                   s.document_number AS documento,
                   gr.name AS grado, g.name AS salon,
                   count(ar.id) AS registros,
                   count(ar.id) FILTER (WHERE ar.status = 'ABSENT') AS ausencias,
                   count(ar.id) FILTER (WHERE ar.status = 'LATE')   AS tardanzas,
                   (SELECT count(*) FROM discipline_records dr
                     WHERE dr.student_id = s.id AND dr.institution_id = :inst
                       AND dr.date BETWEEN :desde AND :hasta) AS casos_convivencia,
                   (SELECT count(*) FROM early_departures ed
                     WHERE ed.student_id = s.id AND ed.institution_id = :inst
                       AND ed.departure_date BETWEEN :desde AND :hasta) AS salidas
            FROM students s
            LEFT JOIN attendance_records ar
                   ON ar.student_id = s.id
                  AND ar.institution_id = :inst
                  AND ar.date BETWEEN :desde AND :hasta
            LEFT JOIN student_groups sg ON sg.student_id = s.id AND sg.is_active = true
            LEFT JOIN groups g  ON g.id = sg.group_id
            LEFT JOIN grades gr ON gr.id = g.grade_id
            WHERE s.institution_id = :inst AND s.is_active = true
            GROUP BY s.id, nombre, documento, gr.name, g.name
            HAVING count(ar.id) >= :minreg
                OR (SELECT count(*) FROM discipline_records dr
                     WHERE dr.student_id = s.id AND dr.institution_id = :inst
                       AND dr.date BETWEEN :desde AND :hasta) > 0
            ORDER BY ausencias DESC, casos_convivencia DESC
            """,
            inst=institution_id, desde=desde, hasta=hasta, minreg=min_registros,
        )

    # ── Resumen ───────────────────────────────────────────────────────

    async def headline_counts(
        self, institution_id: UUID, desde: PyDate, hasta: PyDate
    ) -> dict:
        """Los cuatro números del período en una sola consulta. Se piden dos
        veces (período actual y anterior) para poder mostrar la variación, que es
        lo único que convierte un número en una decisión."""
        return await self._row(
            """
            SELECT
              (SELECT count(*) FROM attendance_records
                WHERE institution_id = :inst AND date BETWEEN :desde AND :hasta) AS att_registros,
              (SELECT count(*) FROM attendance_records
                WHERE institution_id = :inst AND date BETWEEN :desde AND :hasta
                  AND status IN ('PRESENT','LATE')) AS att_asistidos,
              (SELECT count(*) FROM pae_deliveries
                WHERE institution_id = :inst AND delivery_date BETWEEN :desde AND :hasta) AS pae_entregas,
              (SELECT count(*) FROM discipline_records
                WHERE institution_id = :inst AND date BETWEEN :desde AND :hasta) AS convivencia,
              (SELECT count(*) FROM early_departures
                WHERE institution_id = :inst AND departure_date BETWEEN :desde AND :hasta) AS salidas
            """,
            inst=institution_id, desde=desde, hasta=hasta,
        )

    async def notification_health(
        self, institution_id: UUID, desde: PyDate, hasta: PyDate
    ) -> dict:
        """Salud del canal con las familias. Un pico de FAILED significa que las
        notificaciones de inasistencia no están llegando: el colegio cree que
        avisó y nadie recibió nada."""
        return await self._row(
            """
            SELECT count(*) FILTER (WHERE status = 'SENT')    AS enviadas,
                   count(*) FILTER (WHERE status = 'FAILED')  AS fallidas,
                   count(*) FILTER (WHERE status = 'PENDING') AS pendientes
            FROM notifications_log
            WHERE institution_id = :inst
              -- `CAST(... AS date)` y no `:hasta::date`: SQLAlchemy parsea el
              -- `::` pegado a un parámetro bindeado como si empezara otro
              -- parámetro y revienta con "syntax error at or near :".
              AND created_at >= :desde AND created_at < (CAST(:hasta AS date) + 1)
            """,
            inst=institution_id, desde=desde, hasta=hasta,
        )
