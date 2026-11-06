"""F-60 이벤트별 정보 신뢰 경계·검증·파일 장애 회귀."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from test_core_events import SESSION, frontend_event

from app.core import events
from app.core.event_document import FE_EVENTS, PRODUCT_EVENTS, SERVER_EVENTS, build_document
from app.schemas.events import EventBatchCreate
from app.services import event_service

pytest_plugins = ("test_core_events",)


def test_properties_keep_only_checked_values_and_conflict_code():
    payload = {
        "date": "2026-11-06",
        "start_hour": 14,
        "hours": 2,
        "reservation_id": 123,
        "category": "studio",
        "reason": "SLOT_TAKEN",
        "sido": "홍길동",
        "email": "a@example.com",
        "sort": "a@example.com",
        "hour": True,
        "slots": [14, "phone"],
    }
    assert events.sanitize_payload(payload) == {
        "date": "2026-11-06",
        "start_hour": 14,
        "hours": 2,
        "reservation_id": 123,
        "category": "studio",
    }
    assert events.sanitize_payload(payload, "reservation_conflict")["reason"] == "SLOT_TAKEN"
    assert events.sanitize_payload({"reason": "free text"}, "reservation_conflict") == {}
    assert events.sanitize_payload({"date": "2026-02-30", "rating": 6}) == {}


def test_mixed_batch_counts_only_allowed_events(monkeypatch):
    recorded = []
    monkeypatch.setattr(event_service, "log_event", lambda *args, **kwargs: recorded.append(args))
    body = EventBatchCreate.model_validate(
        {
            "session_id": SESSION,
            "events": [
                frontend_event("search_submit"),
                frontend_event("login"),
                {"event_name": "unknown"},
                {"event_name": "unknown"},
            ],
        }
    )
    assert event_service.accept_events(body, None, False) == {
        "accepted": 2,
        "ignored": [{"event_type": "unknown", "count": 2}],
    }
    assert len(recorded) == 2


def test_file_failure_rejects_api_and_never_queues_document(event_app, monkeypatch):
    http, _log_dir = event_app
    submitted = []
    monkeypatch.setattr(events, "write_event", lambda _document: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr(events, "submit_events", lambda docs: submitted.extend(docs))
    response = http.post("/events", json={"session_id": SESSION, "events": [frontend_event()]})
    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"
    assert submitted == []


def test_all_fifteen_names_build_with_correct_product_requirement():
    from test_core_events import frontend_event

    context = {key: frontend_event()[key] for key in ("site", "acquisition", "page", "navigation")}
    product = {
        "product_id": "7",
        "product_name": "테스트 공간",
        "price": {"currency": "KRW", "displayed_amount_minor": 10000, "billing_unit": "hour"},
        "rental_conditions": {
            "start_at": None,
            "end_at": None,
            "guest_count": None,
            "option_ids": [],
        },
    }
    assert len(FE_EVENTS) == 12 and len(SERVER_EVENTS) == 3
    for name in FE_EVENTS | SERVER_EVENTS:
        is_server = name in SERVER_EVENTS
        document = build_document(
            event_id=SESSION,
            session_id=SESSION,
            user_id=3,
            event_name=name,
            anonymous_id=None if is_server else "anon_1",
            session_sequence=None if is_server else 1,
            context=None if is_server else context,
            products=[product] if name in PRODUCT_EVENTS else [],
        )
        assert document["user"]["user_id"] == "3"
        assert len(document["products"]) == (1 if name in PRODUCT_EVENTS else 0)
        assert document["received_at"].tzinfo == UTC
        assert (document["site"] is None) == is_server
        if name in PRODUCT_EVENTS:
            with pytest.raises(ValueError):
                build_document(
                    event_id=SESSION,
                    session_id=SESSION,
                    user_id=None,
                    event_name=name,
                    anonymous_id="anon_1",
                    session_sequence=1,
                    context=context,
                    products=[],
                )


def test_server_product_snapshot_time_and_bad_types():
    product = {
        "product_id": "7",
        "product_name": "테스트 공간",
        "price": {"currency": "KRW", "displayed_amount_minor": 10000, "billing_unit": "hour"},
        "rental_conditions": {
            "start_at": "2026-11-07T14:00:00+09:00",
            "end_at": "2026-11-07T15:00:00+09:00",
            "guest_count": 2,
            "option_ids": [],
        },
    }
    document = build_document(
        event_id=SESSION,
        session_id="server",
        user_id=4,
        event_name="reservation_complete",
        products=[product],
    )
    assert document["products"][0]["rental_conditions"]["start_at"] == datetime(
        2026, 11, 7, 5, tzinfo=UTC
    )
    product["price"]["displayed_amount_minor"] = True
    with pytest.raises(ValueError):
        build_document(
            event_id=SESSION,
            session_id="server",
            user_id=4,
            event_name="reservation_complete",
            products=[product],
        )


def test_client_user_id_is_ignored_and_server_session_is_not_invented(event_app, monkeypatch):
    http, log_dir = event_app
    item = frontend_event()
    item["user"]["user_id"] = "999"
    assert http.post("/events", json={"session_id": SESSION, "events": [item]}).status_code == 202
    import json

    saved = json.loads((log_dir / "events.log").read_text(encoding="utf-8").splitlines()[0])
    assert saved["user"]["user_id"] is None

    recorded = []
    monkeypatch.setattr(events, "write_event", lambda document: recorded.append(document))
    events.log_event(None, 4, "reservation_complete", products=saved["products"])
    assert recorded == []


def test_event_api_rejects_51_and_missing_fe_context(event_app):
    http, _ = event_app
    item = frontend_event()
    assert (
        http.post("/events", json={"session_id": SESSION, "events": [item] * 51}).status_code == 400
    )
    item.pop("page")
    assert http.post("/events", json={"session_id": SESSION, "events": [item]}).status_code == 400


def test_fe_product_id_is_enriched_from_server_snapshot(monkeypatch):
    product = {
        "product_id": "7",
        "product_name": "서버 공간",
        "price": {"currency": "KRW", "displayed_amount_minor": 10000, "billing_unit": "hour"},
        "rental_conditions": {
            "start_at": None,
            "end_at": None,
            "guest_count": None,
            "option_ids": [],
        },
    }
    monkeypatch.setattr(event_service, "_products", lambda _items: {7: product})
    recorded = []
    monkeypatch.setattr(event_service, "log_event", lambda *args, **kwargs: recorded.append(kwargs))
    item = frontend_event("product_view", product_id=7)
    item["products"][0]["product_name"] = "가짜 이름"
    item["products"][0]["price"] = {"displayed_amount_minor": 1}
    with pytest.raises(ValidationError) as error:
        EventBatchCreate.model_validate({"session_id": SESSION, "events": [item]})
    assert {entry["loc"][-1] for entry in error.value.errors()} == {"product_name", "price"}
    item["products"] = [{"product_id": "7"}]
    body = EventBatchCreate.model_validate({"session_id": SESSION, "events": [item]})
    assert event_service.accept_events(body, None, False)["accepted"] == 1
    assert recorded[0]["products"] == [product]


def test_legacy_local_mongo_setting_targets_new_events(monkeypatch):
    from app.core import mongo
    from app.core.config import Settings

    settings = Settings(mongo_db="spacecube")
    assert settings.mongo_db == "space_rental_analytics"
    selected = []

    class Client:
        def __getitem__(self, name):
            selected.append(name)
            return self

    monkeypatch.setattr(mongo, "get_mongo_client", lambda: Client())
    monkeypatch.setattr(mongo, "get_settings", lambda: settings)
    assert mongo.get_event_collection() is not None
    assert selected == ["space_rental_analytics", "events"]


def test_http_retry_gets_new_event_id(event_app):
    import json

    http, log_dir = event_app
    body = {"session_id": SESSION, "events": [frontend_event()]}
    assert http.post("/events", json=body).status_code == 202
    assert http.post("/events", json=body).status_code == 202
    lines = (log_dir / "events.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event_id"] != json.loads(lines[1])["event_id"]
