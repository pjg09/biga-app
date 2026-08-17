"""Schemas del módulo de Estadísticas.

Convención de toda la sección: el backend devuelve **porcentajes ya calculados**
y no solo conteos crudos. La división vive en un sitio (el service) en vez de
repetirse en cada componente del front, que es donde se cuelan los "NaN%" por
dividir entre cero y los criterios divergentes de qué cuenta como asistencia.
"""
from datetime import date as PyDate
from uuid import UUID

from pydantic import BaseModel


class PeriodInfo(BaseModel):
    """Ventana analizada. Viaja en cada respuesta para que el front rotule los
    ejes con las fechas reales y no con el `days` que pidió."""
    desde: PyDate
    hasta: PyDate
    dias: int
    etiqueta: str


class Delta(BaseModel):
    """Variación contra el período inmediatamente anterior de igual longitud.

    `disponible=False` cuando el período anterior no tiene datos suficientes: una
    flecha de "+340%" contra una semana sin registros es ruido con aspecto de
    señal.
    """
    valor: float
    disponible: bool = True


# ── Resumen ───────────────────────────────────────────────────────────

class OverviewKPI(BaseModel):
    clave: str
    etiqueta: str
    valor: float
    unidad: str            # "%", "" (conteo), "raciones"…
    delta: Delta | None = None
    # `True` cuando subir es bueno (asistencia); `False` cuando subir es malo
    # (casos de convivencia). El front colorea con esto, no adivinando por el nombre.
    subir_es_bueno: bool = True


class Alert(BaseModel):
    """Hallazgo accionable, no un dato. Cada alerta dice qué pasa, a quién afecta
    y a qué vista ir. Se generan en el service con umbrales explícitos."""
    nivel: str             # "critico" | "atencion" | "info"
    titulo: str
    detalle: str
    vista: str | None = None   # pestaña a la que llevar al usuario


class OverviewStats(BaseModel):
    periodo: PeriodInfo
    kpis: list[OverviewKPI]
    alertas: list[Alert]
    cobertura_registro: float      # % de bloques con lista tomada
    estudiantes_activos: int
    notificaciones_enviadas: int
    notificaciones_fallidas: int


# ── Asistencia ────────────────────────────────────────────────────────

class AttendanceDay(BaseModel):
    dia: PyDate
    presentes: int
    ausentes: int
    tardanzas: int
    justificadas: int
    # Total del día. Va en la respuesta para que el front distinga "no se tomó
    # lista" de "asistencia 0%": sin esto, un domingo o un festivo se dibuja como
    # una caída a cero y parece que el colegio se vació.
    registros: int
    tasa: float            # (presentes + tardanzas) / total


class GroupAttendance(BaseModel):
    group_id: UUID
    grado: str
    salon: str
    estudiantes: int
    registros: int
    ausentes: int
    tasa: float


class WeekdayAttendance(BaseModel):
    dia_semana: str
    registros: int
    tasa: float


class PeriodAttendance(BaseModel):
    orden: int
    desde_hora: str
    registros: int
    tasa: float


class AttendanceStats(BaseModel):
    periodo: PeriodInfo
    tasa_global: float
    registros: int
    serie: list[AttendanceDay]
    por_salon: list[GroupAttendance]
    por_dia_semana: list[WeekdayAttendance]
    por_hora: list[PeriodAttendance]
    # Cobertura de toma de lista: valida todo lo anterior (ver el repositorio).
    bloques_programados: int
    bloques_con_lista: int
    cobertura: float
    # Embudo de justificación
    ausencias: int
    justificadas: int
    cerradas: int
    tasa_justificacion: float


# ── PAE ───────────────────────────────────────────────────────────────

class PAEDay(BaseModel):
    dia: PyDate
    entregas: int
    tasa: float            # entregas / inscritos activos


class GradeCoverage(BaseModel):
    grado: str
    matriculados: int
    inscritos: int
    cobertura: float


class PAEInactiveStudent(BaseModel):
    student_id: UUID
    nombre: str
    documento: str
    grado: str | None = None
    salon: str | None = None
    ultima_entrega: PyDate | None = None
    dias_sin_reclamar: int | None = None


class PAEStats(BaseModel):
    periodo: PeriodInfo
    inscritos: int
    entregas: int
    dias_con_servicio: int
    promedio_diario: float
    tasa_reclamo: float            # promedio diario / inscritos
    raciones_no_reclamadas: int    # inscritos*dias_servicio - entregas
    serie: list[PAEDay]
    cobertura_por_grado: list[GradeCoverage]
    inscritos_sin_reclamar: list[PAEInactiveStudent]


# ── Convivencia ───────────────────────────────────────────────────────

class DisciplineMonth(BaseModel):
    mes: PyDate
    casos: int
    leve: int
    moderada: int
    grave: int


class TopArticle(BaseModel):
    codigo: str
    titulo: str
    gravedad: str
    casos: int


class RepeatStudent(BaseModel):
    student_id: UUID
    nombre: str
    grado: str | None = None
    salon: str | None = None
    casos: int
    ultimo: PyDate


class DisciplineStats(BaseModel):
    periodo: PeriodInfo
    casos: int
    leve: int
    moderada: int
    grave: int
    serie_mensual: list[DisciplineMonth]
    top_articulos: list[TopArticle]
    reincidentes: list[RepeatStudent]


# ── Estudiantes en riesgo ─────────────────────────────────────────────

class RiskStudent(BaseModel):
    student_id: UUID
    nombre: str
    documento: str
    grado: str | None = None
    salon: str | None = None
    registros: int
    ausencias: int
    tardanzas: int
    casos_convivencia: int
    salidas: int
    pae_sin_reclamar: bool
    ausentismo: float      # % de ausencias sobre registros
    puntaje: float         # 0-100, ver `StatsService._risk_score`
    nivel: str             # "alto" | "medio" | "seguimiento"
    señales: list[str]


class RiskStats(BaseModel):
    periodo: PeriodInfo
    umbral_ausentismo: float
    minimo_registros: int
    evaluados: int
    alto: int
    medio: int
    estudiantes: list[RiskStudent]
