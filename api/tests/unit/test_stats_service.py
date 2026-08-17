"""Tests del módulo de Estadísticas.

Se concentran en lo que **decide**: los umbrales de riesgo, la ponderación del
puntaje y las guardas contra porcentajes sobre muestras minúsculas. Las consultas
SQL no se testean aquí (necesitarían BD); lo que se prueba es que el service no
convierta 2 registros en un "50% de ausentismo" que encabece la lista.
"""
from datetime import date, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.stats_service import (
    DIAS_PAE_INACTIVO,
    MIN_REGISTROS_ESTUDIANTE,
    UMBRAL_COBERTURA,
    StatsService,
    _pct,
)


def make_service():
    repo, admin_repo = AsyncMock(), AsyncMock()
    return StatsService(repo, admin_repo), repo, admin_repo


def fila_riesgo(**over):
    base = dict(
        student_id=uuid4(), nombre="Ana Gómez", documento="1001", grado="Once", salon="A",
        registros=100, ausencias=0, tardanzas=0, casos_convivencia=0, salidas=0,
    )
    base.update(over)
    return base


# --- Guardas de división ---

def test_pct_no_divide_por_cero():
    """Un día sin registros debe dar 0.0, no reventar ni dar NaN: la serie diaria
    incluye a propósito los días sin toma de lista."""
    assert _pct(0, 0) == 0.0
    assert _pct(5, 0) == 0.0
    assert _pct(1, 3) == 33.3


# --- Períodos ---

def test_periodo_anterior_es_contiguo_y_de_igual_longitud():
    """La comparación pierde sentido si los dos períodos se solapan o miden
    distinto: el delta dejaría de ser "lo mismo que antes"."""
    service, *_ = make_service()
    p = service._periodo(30)
    desde, hasta = service._periodo_anterior(p)

    assert hasta == p.desde - timedelta(days=1)     # pegado, sin solapar
    assert (hasta - desde).days == (p.hasta - p.desde).days
    assert p.hasta == date.today()


def test_delta_no_disponible_sin_periodo_previo():
    """Sin datos anteriores no se inventa una variación: `disponible=False` y el
    front escribe "sin período comparable" en vez de un +340% falso."""
    service, *_ = make_service()
    d = service._delta(actual=90.0, previo=0.0, hubo_datos=False)
    assert d.disponible is False and d.valor == 0.0


# --- Puntaje de riesgo ---

def test_ausentismo_pesa_mas_que_el_resto_junto():
    """La ponderación es deliberada: sin esto, tres señales menores adelantarían
    a un estudiante que falta a la mitad de las clases."""
    service, *_ = make_service()
    solo_ausentismo = service._risk_score(ausentismo=40.0, casos=0, salidas=0,
                                          pae_sin_reclamar=False)
    todo_lo_demas = service._risk_score(ausentismo=0.0, casos=4, salidas=4,
                                        pae_sin_reclamar=True)
    assert solo_ausentismo > todo_lo_demas


def test_risk_score_esta_acotado_a_100():
    service, *_ = make_service()
    assert service._risk_score(100.0, 99, 99, True) == 100.0


# --- Clasificación ---

async def test_ausentismo_no_se_calcula_bajo_el_minimo_de_registros():
    """2 ausencias de 3 registros NO es 66% de ausentismo: es una muestra sin
    valor. El estudiante solo entra si tiene otra señal, y con ausentismo 0."""
    service, repo, admin_repo = make_service()
    repo.student_risk.return_value = [
        fila_riesgo(registros=3, ausencias=2, casos_convivencia=1)
    ]
    repo.pae_inactive_enrolled.return_value = []

    r = await service.risk(uuid4(), 30)

    assert len(r.estudiantes) == 1
    e = r.estudiantes[0]
    assert e.ausentismo == 0.0
    assert e.señales == ["1 caso de convivencia"]
    assert r.minimo_registros == MIN_REGISTROS_ESTUDIANTE


async def test_estudiante_sin_ninguna_senal_no_aparece():
    """La tabla es una lista de a quién llamar. Un estudiante sin señales sería
    ruido que empuja hacia abajo a los que sí importan."""
    service, repo, _ = make_service()
    repo.student_risk.return_value = [fila_riesgo(registros=100, ausencias=2)]
    repo.pae_inactive_enrolled.return_value = []

    r = await service.risk(uuid4(), 30)

    assert r.estudiantes == []
    assert r.evaluados == 1      # se evaluó, simplemente no dio señal


async def test_niveles_alto_y_medio_por_ausentismo():
    service, repo, _ = make_service()
    repo.student_risk.return_value = [
        fila_riesgo(registros=100, ausencias=25, nombre="Alto"),
        fila_riesgo(registros=100, ausencias=12, nombre="Medio"),
    ]
    repo.pae_inactive_enrolled.return_value = []

    r = await service.risk(uuid4(), 30)

    niveles = {e.nombre: e.nivel for e in r.estudiantes}
    assert niveles == {"Alto": "alto", "Medio": "medio"}
    assert r.alto == 1 and r.medio == 1
    # Ordenados por puntaje: el peor primero, que es el orden en que se llama.
    assert r.estudiantes[0].nombre == "Alto"


async def test_pae_sin_reclamar_es_una_senal_del_estudiante():
    service, repo, _ = make_service()
    fila = fila_riesgo(registros=100, ausencias=0)
    repo.student_risk.return_value = [fila]
    repo.pae_inactive_enrolled.return_value = [{"student_id": fila["student_id"]}]

    r = await service.risk(uuid4(), 30)

    assert r.estudiantes[0].pae_sin_reclamar is True
    assert "Inscrito al PAE sin reclamar" in r.estudiantes[0].señales
    # Y el umbral de inactividad viaja al repositorio, no se recalcula aparte.
    assert repo.pae_inactive_enrolled.await_args.args[-1] == DIAS_PAE_INACTIVO


# --- Alertas ---

def alertas(service, **over):
    base = dict(cobertura=95.0, tasa=92.0, tasa_prev=92.0, hubo_previo=True,
                salones=[], embudo={"ausencias": 0, "justificadas": 0},
                notif={"enviadas": 100, "fallidas": 0}, pae_inactivos=0)
    base.update(over)
    return service._alertas(**base)


def test_cobertura_baja_es_la_primera_alerta():
    """Si no se toma lista, ninguna otra cifra es fiable: esa alerta va antes que
    cualquier otra o el lector saca conclusiones de datos que no existen."""
    service, *_ = make_service()
    out = alertas(service, cobertura=UMBRAL_COBERTURA - 1, pae_inactivos=99)
    assert out[0].nivel == "critico"
    assert "lista" in out[0].titulo
    assert out[0].vista == "asistencia"


def test_sin_hallazgos_devuelve_una_alerta_informativa():
    """Nunca una lista vacía: "no hay alertas" es información, y una tarjeta en
    blanco se lee como que algo falló al cargar."""
    service, *_ = make_service()
    out = alertas(service)
    assert len(out) == 1 and out[0].nivel == "info"


def test_salon_muy_por_debajo_del_promedio_genera_alerta():
    service, *_ = make_service()
    out = alertas(service, tasa=92.0, salones=[
        {"grado": "Décimo", "salon": "A", "registros": 1800, "asistidos": 1400},  # 77.8%
        {"grado": "Once", "salon": "B", "registros": 1800, "asistidos": 1670},    # 92.8%
    ])
    assert any("Décimo A" in a.titulo for a in out)


def test_salon_sin_muestra_no_genera_alerta():
    """Un salón con 4 registros al 50% no puede disparar una intervención."""
    service, *_ = make_service()
    out = alertas(service, tasa=92.0, salones=[
        {"grado": "Once", "salon": "A", "registros": 4, "asistidos": 2},   # 50%
    ])
    assert all("Once A" not in a.titulo for a in out)


def test_notificaciones_fallidas_alertan_solo_si_son_proporcion_relevante():
    service, *_ = make_service()
    pocas = alertas(service, notif={"enviadas": 100, "fallidas": 2})
    muchas = alertas(service, notif={"enviadas": 100, "fallidas": 40})
    assert all("notificaciones" not in a.titulo for a in pocas)
    assert any("notificaciones" in a.titulo for a in muchas)
