import uuid

import pytest

from scraping.checkpoint import ScraperCheckpoint


@pytest.fixture(autouse=True)
def clear_checkpoints_cache():
    from django.core.cache import cache

    cache.clear()


@pytest.mark.django_db
def test_checkpoint_saves_and_restores_state():
    run_id = str(uuid.uuid4())
    cp = ScraperCheckpoint("courses", run_id)
    cp.set("page_cursor", 12)
    cp.set("items_processed", 240)
    cp.set("last_source", "mit_ocw")

    cp2 = ScraperCheckpoint("courses", run_id)
    assert cp2.get("page_cursor") == 12
    assert cp2.get("items_processed") == 240
    assert cp2.get("last_source") == "mit_ocw"


@pytest.mark.django_db
def test_checkpoint_source_tracking():
    run_id = str(uuid.uuid4())
    cp = ScraperCheckpoint("tools", run_id)

    cp.mark_source_done("hf_models")
    cp.mark_source_done("github_orgs")
    cp.mark_source_done("paperswithcode")

    assert cp.is_source_done("hf_models") is True
    assert cp.is_source_done("github_orgs") is True
    assert cp.is_source_done("paperswithcode") is True
    assert cp.is_source_done("masakhane") is False


@pytest.mark.django_db
def test_checkpoint_is_resuming_false_when_empty():
    run_id = str(uuid.uuid4())
    cp = ScraperCheckpoint("institutions", run_id)

    assert cp.is_resuming() is False


@pytest.mark.django_db
def test_checkpoint_clear_removes_data():
    run_id = str(uuid.uuid4())
    cp = ScraperCheckpoint("courses", run_id)
    cp.set("page_cursor", 3)
    cp.set("items_processed", 60)

    cp.clear()

    cp2 = ScraperCheckpoint("courses", run_id)
    assert cp2.is_resuming() is False


@pytest.mark.django_db
def test_checkpoint_survives_cache_failure(monkeypatch):
    import scraping.checkpoint as checkpoint_module

    def _raise(*args, **kwargs):
        raise Exception("cache is down")

    monkeypatch.setattr(checkpoint_module.cache, "get", _raise)

    run_id = str(uuid.uuid4())
    cp = ScraperCheckpoint("tools", run_id)

    assert cp.is_resuming() is False
    assert cp.get("any_key") is None
