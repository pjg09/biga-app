"""Encolado escalonado de los avisos de no reclamo del PAE.

Lo que se prueba aquí es la corrección del *reparto*: que cada correo sea su
propia tarea, que salgan espaciadas y que la fila de `notifications_log` se cree
al encolar (no al enviar), que es lo que hace idempotente al barrido de cada 15
minutos.
"""
from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.enums import NotificationStatus, NotificationType
from app.services.pae_notifier import PAENotifier


def make_notifier(pares, entregas_del_dia=5):
    notifier = PAENotifier(MagicMock(), MagicMock())
    notifier.repo = AsyncMock()
    notifier.notif_repo = AsyncMock()
    notifier.repo.count_deliveries_on.return_value = entregas_del_dia
    notifier.repo.get_no_claim_students_with_guardians.return_value = pares
    notifier.notif_repo.create_log.side_effect = lambda **kw: MagicMock(id=uuid4(), **kw)
    return notifier


def make_par(nombre="Ana"):
    student = MagicMock(id=uuid4(), first_name=nombre, last_name="Gómez")
    guardian = MagicMock(id=uuid4(), email=f"{nombre.lower()}@acudiente.co")
    return student, guardian


async def test_encola_una_tarea_por_correo_y_las_espacia(monkeypatch):
    """Un job por destinatario, no un bucle dentro de un job: con el bucle, 14
    envíos seguidos hicieron que el proveedor rechazara 12."""
    encoladas = []
    tarea = MagicMock()
    tarea.apply_async.side_effect = lambda args, countdown: encoladas.append(countdown)
    monkeypatch.setattr("app.jobs.pae_jobs.send_pae_no_claim_email", tarea)

    notifier = make_notifier([make_par(f"E{i}") for i in range(5)])
    await notifier.notify_no_claims(uuid4(), date(2026, 8, 17))

    assert len(encoladas) == 5
    assert encoladas == sorted(encoladas)          # salida escalonada
    assert encoladas[0] == 0                       # el primero sale ya
    assert len(set(encoladas)) == 5                # ninguno comparte turno


async def test_registra_pending_al_encolar_no_al_enviar(monkeypatch):
    """La fila se crea antes de enviar: el barrido corre cada 15 min y los
    últimos correos salen minutos después, así que sin la marca previa el
    siguiente barrido volvería a encolar los mismos avisos."""
    monkeypatch.setattr("app.jobs.pae_jobs.send_pae_no_claim_email", MagicMock())
    notifier = make_notifier([make_par(), make_par("Luis")])

    await notifier.notify_no_claims(uuid4(), date(2026, 8, 17))

    assert notifier.notif_repo.create_log.await_count == 2
    for llamada in notifier.notif_repo.create_log.await_args_list:
        assert llamada.kwargs["status"] == NotificationStatus.PENDING
        assert llamada.kwargs["type"] == NotificationType.PAE_NO_CLAIM


async def test_no_notifica_si_no_hubo_ninguna_entrega(monkeypatch):
    """0 entregas = el PAE no operó (festivo). Notificar sería un falso positivo
    a todas las familias a la vez."""
    tarea = MagicMock()
    monkeypatch.setattr("app.jobs.pae_jobs.send_pae_no_claim_email", tarea)
    notifier = make_notifier([make_par()], entregas_del_dia=0)

    await notifier.notify_no_claims(uuid4(), date(2026, 8, 17))

    tarea.apply_async.assert_not_called()
    notifier.notif_repo.create_log.assert_not_called()


async def test_suprime_el_aviso_si_el_estudiante_reclamo_mientras_esperaba():
    """Entre encolar y enviar pasan minutos. Si reclamó en ese rato, el correo
    sería falso: se marca SUPPRESSED (no se intentó a propósito), que es
    distinto de FAILED."""
    notifier = PAENotifier(MagicMock(), MagicMock())
    notifier.repo = AsyncMock()
    notifier.notif_repo = AsyncMock()
    log = MagicMock(status=NotificationStatus.PENDING, email_to="a@b.co", subject="s")
    notifier.notif_repo.get_log.return_value = log
    notifier.repo.has_delivery_on.return_value = True     # reclamó entre medias

    await notifier.send_no_claim_email(uuid4(), uuid4(), uuid4(), date(2026, 8, 17))

    notifier.email.send.assert_not_called()
    assert notifier.notif_repo.mark_result.await_args.args[1] == NotificationStatus.SUPPRESSED


async def test_no_reenvia_una_notificacion_ya_cerrada():
    """Si la tarea se repite (reintento de Celery, doble encolado), la fila ya no
    está PENDING y no se manda un segundo correo a la familia."""
    notifier = PAENotifier(MagicMock(), MagicMock())
    notifier.repo = AsyncMock()
    notifier.notif_repo = AsyncMock()
    notifier.notif_repo.get_log.return_value = MagicMock(status=NotificationStatus.SENT)

    await notifier.send_no_claim_email(uuid4(), uuid4(), uuid4(), date(2026, 8, 17))

    notifier.email.send.assert_not_called()
    notifier.notif_repo.mark_result.assert_not_called()


async def test_registra_failed_con_el_error_del_proveedor():
    notifier = PAENotifier(MagicMock(), MagicMock())
    notifier.repo = AsyncMock()
    notifier.notif_repo = AsyncMock()
    notifier.notif_repo.get_log.return_value = MagicMock(
        status=NotificationStatus.PENDING, email_to="a@b.co", subject="s")
    notifier.repo.has_delivery_on.return_value = False
    notifier.repo.get_active_student.return_value = MagicMock(first_name="Ana", last_name="Gómez")
    notifier.email.send.side_effect = RuntimeError("550 buzón lleno")

    await notifier.send_no_claim_email(uuid4(), uuid4(), uuid4(), date(2026, 8, 17))

    kwargs = notifier.notif_repo.mark_result.await_args.kwargs
    assert notifier.notif_repo.mark_result.await_args.args[1] == NotificationStatus.FAILED
    assert "550 buzón lleno" in kwargs["error_message"]
