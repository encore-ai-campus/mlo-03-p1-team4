"""이슈 #1: 이벤트 문서 계약과 MongoDB 장애·재적재 동작."""

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
from app.main import create_app
from app.schemas.events import EventBatchCreate

SESSION = "4b1c0000-0000-4000-8000-000000000001"


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
    event = {"event_type": "search"}
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
    write_event = events.write_event

    def file_first(document):
        write_event(document)
        order.append("file")

    def failing_mongo(_documents):
        order.append("mongo")
        attempted.set()
        raise RuntimeError("simulated MongoDB outage")

    monkeypatch.setattr(events, "write_event", file_first)
    monkeypatch.setattr(events, "insert_event_documents", failing_mongo)
    response = http.post(
        "/events",
        json={
            "session_id": SESSION,
            "events": [
                {"event_type": "search", "payload": {"sido": "서울"}},
            ],
        },
    )
    assert response.status_code == 202
    assert response.json() == {"accepted": 1, "ignored": []}
    assert attempted.wait(5)
    assert order == ["file", "mongo"]
    document = json.loads((log_dir / "events.log").read_text(encoding="utf-8").splitlines()[0])
    assert document["session_id"] == SESSION
    assert document["event_type"] == "search"
    assert str(UUID(document["event_id"])) == document["event_id"]
    assert set(document) == events.EVENT_DOCUMENT_FIELDS


def test_mongo_duplicate_error_counts_as_replayed_duplicate(monkeypatch):
    class Collection:
        def insert_many(self, _documents, ordered):
            assert ordered is False
            raise BulkWriteError({"nInserted": 0, "writeErrors": [{"code": 11000}]})

    monkeypatch.setattr(events, "get_event_collection", lambda: Collection())
    assert events.insert_event_documents([{"event_id": SESSION}]) == (0, 1)


def test_replay_preserves_original_event_id_and_counts_duplicates(tmp_path, monkeypatch):
    path = tmp_path / "events.log"
    path.write_text(
        json.dumps(
            {
                "event_id": SESSION,
                "ts": "2026-11-04T10:00:00+00:00",
                "event_type": "search",
                "type": "legacy",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    received = []

    def capture(documents):
        received.extend(documents)
        return 0, len(documents)

    monkeypatch.setattr(replay_events, "insert_event_documents", capture)
    assert replay_events.replay(path, None) == {"inserted": 0, "duplicates": 1, "invalid": 0}
    assert received[0]["event_id"] == SESSION
    assert "type" not in received[0]
