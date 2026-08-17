"""Estadísticas para la toma de decisiones del colegio.

Tres reglas que sostienen todo el módulo:

1. **Nada de porcentajes sobre muestras minúsculas.** Con 3 registros, faltar a
   uno es "33% de ausentismo" y encabeza cualquier ranking por encima de un caso
   real de 40 ausencias sobre 200. Por eso `MIN_REGISTROS_ESTUDIANTE` y por eso
   las tasas de salón llevan su `registros` al lado en la respuesta.
2. **Una tasa sin cobertura de registro es propaganda.** Si solo se toma lista en
   el 40% de los bloques, la "asistencia del 95%" describe a quien registra, no
   al colegio. `cobertura` viaja en el resumen y encabeza la vista de asistencia.
3. **Comparar contra el período anterior**, no contra cero. Un número suelto no
   es una decisión; su variación sí.
"""
from datetime import date, timedelta
from uuid import UUID

from app.repositories.admin_repository import AdminRepository
from app.repositories.stats_repository import StatsRepository
from app.schemas.stats import (
    Alert,
    AttendanceDay,
    AttendanceStats,
    Delta,
    DisciplineMonth,
    DisciplineStats,
    GradeCoverage,
    GroupAttendance,
    OverviewKPI,
    OverviewStats,
    PAEDay,
    PAEInactiveStudent,
    PAEStats,
    PeriodAttendance,
    PeriodInfo,
    RepeatStudent,
    RiskStats,
    RiskStudent,
    TopArticle,
    WeekdayAttendance,
)

DIAS_SEMANA = {1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves", 5: "Viernes",
               6: "Sábado", 7: "Domingo"}

# Ausentismo crónico: 10% de las clases perdidas es el umbral que usan los
# sistemas escolares para "chronic absenteeism", y a partir de ahí la correlación
# con repitencia y deserción deja de ser anecdótica.
UMBRAL_AUSENTISMO_MEDIO = 10.0
UMBRAL_AUSENTISMO_ALTO = 20.0
# Por debajo de esto no se calcula ausentismo del estudiante: no hay muestra.
MIN_REGISTROS_ESTUDIANTE = 10
# Cobertura de toma de lista por debajo de la cual el resto de cifras no es fiable.
UMBRAL_COBERTURA = 70.0
# Días sin reclamar una ración a partir de los cuales un inscrito al PAE se
# marca como inactivo. Dos semanas es más que cualquier ausencia normal por
# enfermedad y todavía a tiempo de ir a buscar al estudiante.
DIAS_PAE_INACTIVO = 14


def _pct(parte: float, total: float) -> float:
    return round(parte / total * 100, 1) if total else 0.0


class StatsService:
    def __init__(self, repo: StatsRepository, admin_repo: AdminRepository):
        self.repo = repo
        # Los conteos de población (estudiantes activos, inscritos al PAE) ya
        # viven en AdminRepository y son los mismos que alimentan `/admin/stats`.
        # Reimplementarlos aquí haría que dos pantallas dieran cifras distintas.
        self.admin_repo = admin_repo

    # ── Períodos ──────────────────────────────────────────────────────

    def _periodo(self, dias: int) -> PeriodInfo:
        """Ventana que termina hoy. `date.today()` es hora local a propósito:
        con `TZ=America/Bogota` en los contenedores, usar UTC adelantaría el día
        a partir de las 19:00 y metería en el período un día que aún no existe."""
        hasta = date.today()
        desde = hasta - timedelta(days=dias - 1)
        etiquetas = {7: "Últimos 7 días", 30: "Últimos 30 días",
                     90: "Últimos 90 días", 180: "Último semestre", 365: "Último año"}
        return PeriodInfo(desde=desde, hasta=hasta, dias=dias,
                          etiqueta=etiquetas.get(dias, f"Últimos {dias} días"))

    def _periodo_anterior(self, p: PeriodInfo) -> tuple[date, date]:
        hasta = p.desde - timedelta(days=1)
        return hasta - timedelta(days=p.dias - 1), hasta

    def _delta(self, actual: float, previo: float, hubo_datos: bool) -> Delta:
        if not hubo_datos:
            return Delta(valor=0.0, disponible=False)
        return Delta(valor=round(actual - previo, 1), disponible=True)

    # ── Resumen ───────────────────────────────────────────────────────

    async def overview(self, institution_id: UUID, dias: int) -> OverviewStats:
        p = self._periodo(dias)
        prev_desde, prev_hasta = self._periodo_anterior(p)
        anio = p.hasta.year

        actual = await self.repo.headline_counts(institution_id, p.desde, p.hasta)
        previo = await self.repo.headline_counts(institution_id, prev_desde, prev_hasta)
        cobertura = await self.repo.attendance_coverage(institution_id, p.desde, p.hasta, anio)
        notif = await self.repo.notification_health(institution_id, p.desde, p.hasta)
        embudo = await self.repo.justification_funnel(institution_id, p.desde, p.hasta)
        pae_inactivos = await self.repo.pae_inactive_enrolled(
            institution_id, p.desde, p.hasta, anio, DIAS_PAE_INACTIVO)
        salones = await self.repo.attendance_by_group(institution_id, p.desde, p.hasta)

        att_reg = int(actual.get("att_registros") or 0)
        att_ok = int(actual.get("att_asistidos") or 0)
        prev_reg = int(previo.get("att_registros") or 0)
        prev_ok = int(previo.get("att_asistidos") or 0)

        tasa = _pct(att_ok, att_reg)
        tasa_prev = _pct(prev_ok, prev_reg)
        cob_pct = _pct(cobertura.get("tomados") or 0, cobertura.get("programados") or 0)

        kpis = [
            OverviewKPI(
                clave="asistencia", etiqueta="Asistencia", valor=tasa, unidad="%",
                delta=self._delta(tasa, tasa_prev, prev_reg > 0), subir_es_bueno=True,
            ),
            OverviewKPI(
                clave="cobertura", etiqueta="Cobertura de registro", valor=cob_pct, unidad="%",
                subir_es_bueno=True,
            ),
            OverviewKPI(
                clave="pae", etiqueta="Raciones entregadas",
                valor=float(actual.get("pae_entregas") or 0), unidad="",
                delta=self._delta(float(actual.get("pae_entregas") or 0),
                                  float(previo.get("pae_entregas") or 0),
                                  bool(previo.get("pae_entregas"))),
                subir_es_bueno=True,
            ),
            OverviewKPI(
                clave="convivencia", etiqueta="Casos de convivencia",
                valor=float(actual.get("convivencia") or 0), unidad="",
                delta=self._delta(float(actual.get("convivencia") or 0),
                                  float(previo.get("convivencia") or 0),
                                  bool(previo.get("convivencia"))),
                subir_es_bueno=False,
            ),
            OverviewKPI(
                clave="salidas", etiqueta="Salidas anticipadas",
                valor=float(actual.get("salidas") or 0), unidad="",
                delta=self._delta(float(actual.get("salidas") or 0),
                                  float(previo.get("salidas") or 0),
                                  bool(previo.get("salidas"))),
                subir_es_bueno=False,
            ),
        ]

        alertas = self._alertas(
            cobertura=cob_pct, tasa=tasa, tasa_prev=tasa_prev, hubo_previo=prev_reg > 0,
            salones=salones, embudo=embudo, notif=notif, pae_inactivos=len(pae_inactivos),
        )

        return OverviewStats(
            periodo=p, kpis=kpis, alertas=alertas,
            cobertura_registro=cob_pct,
            estudiantes_activos=await self.admin_repo.count_active_students(institution_id),
            notificaciones_enviadas=int(notif.get("enviadas") or 0),
            notificaciones_fallidas=int(notif.get("fallidas") or 0),
        )

    def _alertas(self, *, cobertura, tasa, tasa_prev, hubo_previo, salones, embudo,
                 notif, pae_inactivos) -> list[Alert]:
        """Convierte números en cosas que alguien puede hacer mañana.

        El orden importa: la cobertura va primero porque, si está baja, invalida
        la lectura de todo lo demás y esa es la primera acción a tomar.
        """
        out: list[Alert] = []

        if cobertura < UMBRAL_COBERTURA:
            out.append(Alert(
                nivel="critico",
                titulo=f"Solo se tomó lista en el {cobertura}% de los bloques",
                detalle=("Con esta cobertura, las tasas de asistencia describen a los docentes "
                         "que sí registran, no al colegio. Es lo primero que hay que corregir "
                         "antes de leer el resto de indicadores."),
                vista="asistencia",
            ))

        fallidas = int(notif.get("fallidas") or 0)
        enviadas = int(notif.get("enviadas") or 0)
        if fallidas and fallidas / max(enviadas + fallidas, 1) > 0.1:
            out.append(Alert(
                nivel="critico",
                titulo=f"{fallidas} notificaciones a acudientes fallaron",
                detalle=("El colegio cree que avisó de esas inasistencias y la familia nunca "
                         "recibió nada. Revisar el proveedor de correo y los correos de los "
                         "acudientes."),
            ))

        # Salón con ausentismo muy por encima del resto: es donde intervenir.
        con_muestra = [s for s in salones if int(s.get("registros") or 0) >= 20]
        if con_muestra:
            peor = min(con_muestra, key=lambda s: _pct(s["asistidos"], s["registros"]))
            peor_tasa = _pct(peor["asistidos"], peor["registros"])
            if peor_tasa < tasa - 10:
                out.append(Alert(
                    nivel="atencion",
                    titulo=f"{peor['grado']} {peor['salon']} está {round(tasa - peor_tasa, 1)} puntos "
                           f"por debajo del promedio",
                    detalle=(f"Asistencia del {peor_tasa}% frente al {tasa}% institucional. "
                             "Un solo salón muy por debajo suele ser un problema concreto "
                             "(un horario, un docente, un grupo de estudiantes), no una tendencia."),
                    vista="asistencia",
                ))

        ausencias = int(embudo.get("ausencias") or 0)
        justificadas = int(embudo.get("justificadas") or 0)
        if ausencias >= 10:
            tasa_just = _pct(justificadas, ausencias)
            if tasa_just < 30:
                out.append(Alert(
                    nivel="atencion",
                    titulo=f"Solo el {tasa_just}% de las inasistencias recibió justificación",
                    detalle=(f"{ausencias - justificadas} de {ausencias} ausencias siguen sin "
                             "respuesta de la familia. O el enlace de justificación no está "
                             "llegando, o hay hogares con los que hay que contactar por otra vía."),
                    vista="asistencia",
                ))

        if pae_inactivos >= 5:
            out.append(Alert(
                nivel="atencion",
                titulo=f"{pae_inactivos} inscritos al PAE llevan más de {DIAS_PAE_INACTIVO} días sin reclamar",
                detalle=("Son raciones que se piden y se pierden, y en varios casos es la señal "
                         "temprana de un estudiante que dejó de venir. Verificar uno por uno."),
                vista="pae",
            ))

        if hubo_previo and tasa_prev - tasa >= 5:
            out.append(Alert(
                nivel="atencion",
                titulo=f"La asistencia cayó {round(tasa_prev - tasa, 1)} puntos frente al período anterior",
                detalle=f"Pasó de {tasa_prev}% a {tasa}%.",
                vista="asistencia",
            ))

        if not out:
            out.append(Alert(
                nivel="info",
                titulo="Sin alertas en este período",
                detalle="Ningún indicador cruzó los umbrales de atención.",
            ))
        return out

    # ── Asistencia ────────────────────────────────────────────────────

    async def attendance(self, institution_id: UUID, dias: int) -> AttendanceStats:
        p = self._periodo(dias)
        anio = p.hasta.year

        serie_raw = await self.repo.attendance_daily(institution_id, p.desde, p.hasta)
        grupos = await self.repo.attendance_by_group(institution_id, p.desde, p.hasta)
        semana = await self.repo.attendance_by_weekday(institution_id, p.desde, p.hasta)
        horas = await self.repo.attendance_by_period(institution_id, p.desde, p.hasta)
        cob = await self.repo.attendance_coverage(institution_id, p.desde, p.hasta, anio)
        embudo = await self.repo.justification_funnel(institution_id, p.desde, p.hasta)

        serie = []
        for r in serie_raw:
            total = r["presentes"] + r["ausentes"] + r["tardanzas"] + r["justificadas"]
            serie.append(AttendanceDay(
                dia=r["dia"], presentes=r["presentes"], ausentes=r["ausentes"],
                tardanzas=r["tardanzas"], justificadas=r["justificadas"],
                registros=total,
                tasa=_pct(r["presentes"] + r["tardanzas"], total),
            ))

        registros = sum(s.presentes + s.ausentes + s.tardanzas + s.justificadas for s in serie)
        asistidos = sum(s.presentes + s.tardanzas for s in serie)
        ausencias = int(embudo.get("ausencias") or 0)
        justificadas = int(embudo.get("justificadas") or 0)

        return AttendanceStats(
            periodo=p,
            tasa_global=_pct(asistidos, registros),
            registros=registros,
            serie=serie,
            por_salon=[GroupAttendance(
                group_id=g["group_id"], grado=g["grado"], salon=g["salon"],
                estudiantes=g["estudiantes"], registros=g["registros"], ausentes=g["ausentes"],
                tasa=_pct(g["asistidos"], g["registros"]),
            ) for g in grupos],
            por_dia_semana=[WeekdayAttendance(
                dia_semana=DIAS_SEMANA.get(d["dow"], str(d["dow"])),
                registros=d["registros"], tasa=_pct(d["asistidos"], d["registros"]),
            ) for d in semana],
            por_hora=[PeriodAttendance(
                orden=h["orden"], desde_hora=(h["desde_hora"] or "")[:5],
                registros=h["registros"], tasa=_pct(h["asistidos"], h["registros"]),
            ) for h in horas],
            bloques_programados=int(cob.get("programados") or 0),
            bloques_con_lista=int(cob.get("tomados") or 0),
            cobertura=_pct(cob.get("tomados") or 0, cob.get("programados") or 0),
            ausencias=ausencias,
            justificadas=justificadas,
            cerradas=int(embudo.get("cerradas") or 0),
            tasa_justificacion=_pct(justificadas, ausencias),
        )

    # ── PAE ───────────────────────────────────────────────────────────

    async def pae(self, institution_id: UUID, dias: int) -> PAEStats:
        p = self._periodo(dias)
        anio = p.hasta.year
        inscritos = await self.admin_repo.count_pae_enrolled(institution_id, anio)

        serie_raw = await self.repo.pae_daily(institution_id, p.desde, p.hasta, anio)
        cobertura = await self.repo.pae_coverage_by_grade(institution_id, anio)
        inactivos = await self.repo.pae_inactive_enrolled(
            institution_id, p.desde, p.hasta, anio, DIAS_PAE_INACTIVO)
        dias_servicio = await self.repo.pae_service_days(institution_id, p.desde, p.hasta)

        entregas = sum(r["entregas"] for r in serie_raw)
        # Divisor = días con servicio, no días del calendario: contar festivos y
        # fines de semana hunde el promedio y hace ver un problema donde no lo hay.
        promedio = round(entregas / dias_servicio, 1) if dias_servicio else 0.0

        return PAEStats(
            periodo=p,
            inscritos=inscritos,
            entregas=entregas,
            dias_con_servicio=dias_servicio,
            promedio_diario=promedio,
            tasa_reclamo=_pct(promedio, inscritos),
            # Lo que se pidió y no se recogió en los días que sí hubo servicio.
            raciones_no_reclamadas=max(inscritos * dias_servicio - entregas, 0),
            serie=[PAEDay(dia=r["dia"], entregas=r["entregas"],
                          tasa=_pct(r["entregas"], inscritos)) for r in serie_raw],
            cobertura_por_grado=[GradeCoverage(
                grado=c["grado"], matriculados=c["matriculados"], inscritos=c["inscritos"],
                cobertura=_pct(c["inscritos"], c["matriculados"]),
            ) for c in cobertura],
            inscritos_sin_reclamar=[PAEInactiveStudent(
                student_id=i["student_id"], nombre=i["nombre"], documento=i["documento"],
                grado=i["grado"], salon=i["salon"], ultima_entrega=i["ultima_entrega"],
                dias_sin_reclamar=((p.hasta - i["ultima_entrega"]).days
                                   if i["ultima_entrega"] else None),
            ) for i in inactivos],
        )

    # ── Convivencia ───────────────────────────────────────────────────

    async def discipline(self, institution_id: UUID, dias: int) -> DisciplineStats:
        p = self._periodo(dias)
        mensual = await self.repo.discipline_monthly(institution_id, p.desde, p.hasta)
        top = await self.repo.discipline_top_articles(institution_id, p.desde, p.hasta)
        reinc = await self.repo.discipline_repeat_students(institution_id, p.desde, p.hasta)

        return DisciplineStats(
            periodo=p,
            casos=sum(m["casos"] for m in mensual),
            leve=sum(m["leve"] for m in mensual),
            moderada=sum(m["moderada"] for m in mensual),
            grave=sum(m["grave"] for m in mensual),
            serie_mensual=[DisciplineMonth(**m) for m in mensual],
            top_articulos=[TopArticle(**t) for t in top],
            reincidentes=[RepeatStudent(**r) for r in reinc],
        )

    # ── Riesgo ────────────────────────────────────────────────────────

    def _risk_score(self, ausentismo: float, casos: int, salidas: int,
                    pae_sin_reclamar: bool) -> float:
        """Puntaje 0–100. Ponderación deliberada, no un promedio ingenuo.

        El ausentismo pesa el doble que todo lo demás junto porque es el predictor
        con evidencia; los otros tres son agravantes que ordenan entre estudiantes
        con ausentismo parecido. No pretende ser un modelo: es un criterio de
        priorización explícito y auditable, que es justo lo que un coordinador
        necesita para decidir a quién llama primero.
        """
        puntaje = min(ausentismo, 50) * 1.2          # hasta 60
        puntaje += min(casos, 4) * 5                  # hasta 20
        puntaje += min(salidas, 4) * 2.5              # hasta 10
        puntaje += 10 if pae_sin_reclamar else 0      # hasta 10
        return round(min(puntaje, 100), 1)

    async def risk(self, institution_id: UUID, dias: int) -> RiskStats:
        p = self._periodo(dias)
        anio = p.hasta.year
        filas = await self.repo.student_risk(
            institution_id, p.desde, p.hasta, MIN_REGISTROS_ESTUDIANTE
        )
        inactivos = {i["student_id"] for i in await self.repo.pae_inactive_enrolled(
            institution_id, p.desde, p.hasta, anio, DIAS_PAE_INACTIVO)}

        estudiantes: list[RiskStudent] = []
        for f in filas:
            registros = int(f["registros"] or 0)
            ausencias = int(f["ausencias"] or 0)
            casos = int(f["casos_convivencia"] or 0)
            salidas = int(f["salidas"] or 0)
            # Sin muestra suficiente el porcentaje no se calcula: se deja en 0 y
            # el estudiante solo aparece si tiene señales que no dependen de él
            # (casos de convivencia), nunca por un ausentismo inventado.
            ausentismo = _pct(ausencias, registros) if registros >= MIN_REGISTROS_ESTUDIANTE else 0.0
            sin_pae = f["student_id"] in inactivos
            puntaje = self._risk_score(ausentismo, casos, salidas, sin_pae)

            señales = []
            if ausentismo >= UMBRAL_AUSENTISMO_ALTO:
                señales.append(f"Ausentismo {ausentismo}%")
            elif ausentismo >= UMBRAL_AUSENTISMO_MEDIO:
                señales.append(f"Ausentismo {ausentismo}%")
            if casos:
                señales.append(f"{casos} caso{'s' if casos > 1 else ''} de convivencia")
            if salidas >= 2:
                señales.append(f"{salidas} salidas anticipadas")
            if sin_pae:
                señales.append("Inscrito al PAE sin reclamar")
            if not señales:
                continue    # sin ninguna señal no es un caso, es ruido en la tabla

            if ausentismo >= UMBRAL_AUSENTISMO_ALTO or puntaje >= 45:
                nivel = "alto"
            elif ausentismo >= UMBRAL_AUSENTISMO_MEDIO or casos >= 2 or puntaje >= 25:
                nivel = "medio"
            else:
                nivel = "seguimiento"

            estudiantes.append(RiskStudent(
                student_id=f["student_id"], nombre=f["nombre"], documento=f["documento"],
                grado=f["grado"], salon=f["salon"], registros=registros, ausencias=ausencias,
                tardanzas=int(f["tardanzas"] or 0), casos_convivencia=casos, salidas=salidas,
                pae_sin_reclamar=sin_pae, ausentismo=ausentismo, puntaje=puntaje,
                nivel=nivel, señales=señales,
            ))

        estudiantes.sort(key=lambda e: e.puntaje, reverse=True)
        return RiskStats(
            periodo=p,
            umbral_ausentismo=UMBRAL_AUSENTISMO_MEDIO,
            minimo_registros=MIN_REGISTROS_ESTUDIANTE,
            evaluados=len(filas),
            alto=sum(1 for e in estudiantes if e.nivel == "alto"),
            medio=sum(1 for e in estudiantes if e.nivel == "medio"),
            estudiantes=estudiantes[:100],
        )
