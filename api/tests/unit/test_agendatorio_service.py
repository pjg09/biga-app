from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.agendatorio import ConvivenciaArticle, DisciplineRecord
from app.models.guardian import Guardian
from app.schemas.agendatorio import ArticleUpdate, DisciplineRecordCreate
from app.services.agendatorio_service import AgendatorioService


def make_article(*, is_active: bool = True, code: str = "ART-1") -> ConvivenciaArticle:
    article = MagicMock(spec=ConvivenciaArticle)
    article.id = uuid4()
    article.code = code
    article.is_active = is_active
    return article


def make_record_data(article_ids: list) -> DisciplineRecordCreate:
    return DisciplineRecordCreate(
        student_id=uuid4(),
        article_ids=article_ids,
        observations="Uso del celular durante evaluación",
        date=date(2026, 5, 21),
    )


def make_service(
    *,
    agendatorio_repo: AsyncMock | None = None,
    student_repo: AsyncMock | None = None,
    guardian_repo: AsyncMock | None = None,
    storage: MagicMock | None = None,
) -> AgendatorioService:
    return AgendatorioService(
        agendatorio_repo=agendatorio_repo or AsyncMock(),
        student_repo=student_repo or AsyncMock(),
        guardian_repo=guardian_repo or AsyncMock(),
        storage=storage or MagicMock(),
    )


async def test_create_record_fails_if_article_ids_empty():
    data = DisciplineRecordCreate.model_construct(
        student_id=uuid4(),
        article_ids=[],
        observations="test",
        date=date(2026, 5, 21),
    )
    service = make_service()

    with pytest.raises(HTTPException) as exc_info:
        await service.create_record(data, b"png-bytes", uuid4(), uuid4())

    assert exc_info.value.status_code == 400


async def test_create_record_fails_if_article_not_in_institution():
    article_ids = [uuid4(), uuid4()]
    data = make_record_data(article_ids)

    agendatorio_repo = AsyncMock()
    # Solo uno de los dos artículos pertenece a la institución del usuario.
    agendatorio_repo.get_articles_by_ids.return_value = [make_article()]
    service = make_service(agendatorio_repo=agendatorio_repo)

    with pytest.raises(HTTPException) as exc_info:
        await service.create_record(data, b"png-bytes", uuid4(), uuid4())

    assert exc_info.value.status_code == 400


async def test_create_record_fails_if_article_inactive():
    article_id = uuid4()
    data = make_record_data([article_id])

    agendatorio_repo = AsyncMock()
    agendatorio_repo.get_articles_by_ids.return_value = [make_article(is_active=False)]
    service = make_service(agendatorio_repo=agendatorio_repo)

    with pytest.raises(HTTPException) as exc_info:
        await service.create_record(data, b"png-bytes", uuid4(), uuid4())

    assert exc_info.value.status_code == 400


async def test_create_record_enqueues_job_when_primary_guardian_exists():
    article_id = uuid4()
    data = make_record_data([article_id])

    record = MagicMock(spec=DisciplineRecord)
    record.id = uuid4()

    agendatorio_repo = AsyncMock()
    agendatorio_repo.get_articles_by_ids.return_value = [make_article()]
    agendatorio_repo.create_record.return_value = record

    guardian_repo = AsyncMock()
    guardian_repo.get_primary.return_value = MagicMock(spec=Guardian)

    service = make_service(agendatorio_repo=agendatorio_repo, guardian_repo=guardian_repo)
    institution_id = uuid4()

    with patch("app.services.agendatorio_service.notify_discipline_record") as mock_job:
        result = await service.create_record(data, b"png-bytes", institution_id, uuid4())

    assert result is record
    mock_job.delay.assert_called_once_with(str(record.id), str(institution_id))


async def test_create_record_does_not_enqueue_job_without_primary_guardian():
    article_id = uuid4()
    data = make_record_data([article_id])

    record = MagicMock(spec=DisciplineRecord)
    record.id = uuid4()

    agendatorio_repo = AsyncMock()
    agendatorio_repo.get_articles_by_ids.return_value = [make_article()]
    agendatorio_repo.create_record.return_value = record

    guardian_repo = AsyncMock()
    guardian_repo.get_primary.return_value = None

    service = make_service(agendatorio_repo=agendatorio_repo, guardian_repo=guardian_repo)

    with patch("app.services.agendatorio_service.notify_discipline_record") as mock_job:
        result = await service.create_record(data, b"png-bytes", uuid4(), uuid4())

    assert result is record
    mock_job.delay.assert_not_called()


async def test_create_record_persists_nothing_if_storage_upload_fails():
    article_id = uuid4()
    data = make_record_data([article_id])

    agendatorio_repo = AsyncMock()
    agendatorio_repo.get_articles_by_ids.return_value = [make_article()]

    storage = MagicMock()
    storage.upload.side_effect = RuntimeError("storage down")

    service = make_service(agendatorio_repo=agendatorio_repo, storage=storage)

    with pytest.raises(RuntimeError):
        await service.create_record(data, b"png-bytes", uuid4(), uuid4())

    agendatorio_repo.create_record.assert_not_called()


async def test_deactivate_article_raises_404_if_not_found():
    agendatorio_repo = AsyncMock()
    agendatorio_repo.get_article.return_value = None
    service = make_service(agendatorio_repo=agendatorio_repo)

    with pytest.raises(HTTPException) as exc_info:
        await service.deactivate_article(uuid4(), uuid4())

    assert exc_info.value.status_code == 404


async def test_update_article_allows_changing_code():
    article = make_article(code="ART-OLD")

    agendatorio_repo = AsyncMock()
    agendatorio_repo.get_article.return_value = article
    agendatorio_repo.get_article_by_code.return_value = None
    agendatorio_repo.update_article.return_value = article

    service = make_service(agendatorio_repo=agendatorio_repo)
    data = ArticleUpdate(code="ART-NEW")

    result = await service.update_article(article.id, data, uuid4())

    assert result is article
    agendatorio_repo.update_article.assert_called_once_with(article, {"code": "ART-NEW"})


async def test_update_article_fails_if_new_code_used_by_another_article():
    article = make_article(code="ART-OLD")
    other_article = make_article(code="ART-NEW")

    agendatorio_repo = AsyncMock()
    agendatorio_repo.get_article.return_value = article
    agendatorio_repo.get_article_by_code.return_value = other_article

    service = make_service(agendatorio_repo=agendatorio_repo)
    data = ArticleUpdate(code="ART-NEW")

    with pytest.raises(HTTPException) as exc_info:
        await service.update_article(article.id, data, uuid4())

    assert exc_info.value.status_code == 409
    agendatorio_repo.update_article.assert_not_called()


async def test_update_article_can_reactivate():
    article = make_article(is_active=False)

    agendatorio_repo = AsyncMock()
    agendatorio_repo.get_article.return_value = article
    agendatorio_repo.update_article.return_value = article

    service = make_service(agendatorio_repo=agendatorio_repo)
    data = ArticleUpdate(is_active=True)

    await service.update_article(article.id, data, uuid4())

    agendatorio_repo.update_article.assert_called_once_with(article, {"is_active": True})


async def test_list_records_without_student_id_lists_institution_records():
    agendatorio_repo = AsyncMock()
    agendatorio_repo.list_records.return_value = []

    service = make_service(agendatorio_repo=agendatorio_repo)
    institution_id = uuid4()

    result = await service.list_records(institution_id=institution_id)

    assert result == []
    agendatorio_repo.list_records.assert_called_once_with(
        institution_id=institution_id,
        student_id=None,
        article_id=None,
        date_from=None,
        date_to=None,
        skip=0,
        limit=20,
    )


async def test_list_records_validates_student_exists_when_student_id_given():
    student_repo = AsyncMock()
    student_repo.get_by_id.return_value = None

    service = make_service(student_repo=student_repo)

    with pytest.raises(HTTPException) as exc_info:
        await service.list_records(institution_id=uuid4(), student_id=uuid4())

    assert exc_info.value.status_code == 404


async def test_list_records_fails_if_date_from_after_date_to():
    service = make_service()

    with pytest.raises(HTTPException) as exc_info:
        await service.list_records(
            institution_id=uuid4(),
            date_from=date(2026, 6, 1),
            date_to=date(2026, 5, 1),
        )

    assert exc_info.value.status_code == 400
