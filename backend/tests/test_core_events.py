"""F-60 새 이벤트 문서와 파일 우선·재적재 계약."""

import json
from threading import Event
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pymongo.errors import BulkWriteError
from scripts import replay_events

from app.core import events
from app.core.config import get_settings
from app.core.event_document import EVENT_DOCUMENT_FIELDS
from app.main import create_app
from app.schemas.events import EventBatchCreate

SESSION = "4b1c0000-0000-4000-8000-000000000001"


def frontend_event(name="search_submit", product_id=None):
    product = [{"product_id": str(product_id)}] if product_id else []
    return {
        "schema_version": 1,
        "event_name": name,
        "occurred_at": "2026-11-06T12:00:00+09:00",
        "user": {"anonymous_id": "anon_1", "session_id": SESSION, "session_sequence": 1},
        "site": {"site_id": "main", "hostname": "localhost", "platform": "desktop_web"},
        "acquisition": {
            "landing_url": "http://localhost/search?q=secret",
            "referrer_url": None,
            "utm_source": "private",
            "utm_medium": None,
            "utm_campaign": None,
        },
        "page": {
            "page_view_id": "page_1",
            "page_type": "search_results",
            "url": "http://localhost/search?q=secret#private",
            "path": "/search",
            "title": "개인정보",
        },
        "navigation": {
            "from": None,
            "to": {
                "page_view_id": "page_1",
                "site_id": "main",
                "url": "http://localhost/search?q=secret",
                "path": "/search",
            },
            "navigation_type": "direct",
        },
        "products": product,
        "properties": {"q": "secret", "page": 1},
    }


@pytest.fixture
def event_app(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_WRITE_URL", "mysql+pymysql://unused@127.0.0.1/spacecube_test")
    monkeypatch.setenv("DB_READ_URL", "mysql+pymysql://unused@127.0.0.1/spacecube_test")
    monkeypatch.setenv("MONGO_URL", "mongodb://127.0.0.1:1")
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as http:
            yield http, tmp_path
    finally:
        get_settings.cache_clear()


def test_documented_event_batch_limits_and_required_session():
    event = frontend_event()
    assert (
        len(EventBatchCreate.model_validate({"session_id": SESSION, "events": [event] * 50}).events)
        == 50
    )
    with pytest.raises(ValidationError):
        EventBatchCreate.model_validate({"session_id": SESSION, "events": [event] * 51})
    with pytest.raises(ValidationError):
        EventBatchCreate.model_validate({"events": [event]})


def test_mongo_failure_preserves_event_file_and_api_success(event_app, monkeypatch):
    http, log_dir = event_app
    attempted = Event()
    order = []
    original = events.write_event

    def file_first(document):
        original(document)
        order.append("file")

    def failing_mongo(_documents):
        order.append("mongo")
        attempted.set()
        raise RuntimeError("simulated")

    monkeypatch.setattr(events, "write_event", file_first)
    monkeypatch.setattr(events, "insert_event_documents", failing_mongo)
    response = http.post("/events", json={"session_id": SESSION, "events": [frontend_event()]})
    assert response.status_code == 202
    assert response.json() == {"accepted": 1, "ignored": []}
    assert attempted.wait(5)
    assert order == ["file", "mongo"]
    document = json.loads((log_dir / "events.log").read_text(encoding="utf-8").splitlines()[0])
    assert document["user"]["session_id"] == SESSION
    assert document["event_name"] == "search_submit"
    assert str(UUID(document["event_id"])) == document["event_id"]
    assert set(document) == EVENT_DOCUMENT_FIELDS
    assert document["page"]["url"] == "http://localhost/search"
    assert document["acquisition"]["utm_source"] is None
    assert document["properties"] == {"page": 1}


def test_mongo_duplicate_error_counts_as_replayed_duplicate(monkeypatch):
    class Collection:
        def insert_many(self, _documents, ordered):
            assert ordered is False
            raise BulkWriteError({"nInserted": 0, "writeErrors": [{"code": 11000}]})

    monkeypatch.setattr(events, "get_event_collection", lambda: Collection())
    assert events.insert_event_documents([{"event_id": SESSION}]) == (0, 1)


def test_replay_skips_legacy_and_preserves_new_event_id(tmp_path, monkeypatch):
    from app.core.event_document import build_document

    path = tmp_path / "events.log"
    new = build_document(
        event_id=SESSION,
        session_id=SESSION,
        user_id=None,
        event_name="search_submit",
        anonymous_id="anon_1",
        session_sequence=1,
        context={
            key: frontend_event()[key] for key in ("site", "acquisition", "page", "navigation")
        },
    )
    old = {"event_id": SESSION, "ts": "2026-11-04T10:00:00+00:00", "event_type": "search"}
    path.write_text(json.dumps(old) + "\n" + json.dumps(new, default=str) + "\n", encoding="utf-8")
    received = []

    def capture(documents):
        received.extend(documents)
        return 0, len(documents)

    monkeypatch.setattr(replay_events, "insert_event_documents", capture)
    assert replay_events.replay(path, None) == {"inserted": 0, "duplicates": 1, "invalid": 1}
    assert received[0]["event_id"] == SESSION
    assert set(received[0]) == EVENT_DOCUMENT_FIELDS
