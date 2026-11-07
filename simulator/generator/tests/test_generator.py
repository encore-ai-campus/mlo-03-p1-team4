"""고정 방문량·과거 시각·중단 복구·MongoDB 부분 실패의 회귀 검증."""

import json
from collections import Counter
from datetime import date, datetime, timedelta
from unittest.mock import Mock
from uuid import UUID

import pytest
from pymongo.errors import BulkWriteError

from app.core import clock, event_document
from app.core.event_document import EVENT_DOCUMENT_FIELDS
from app.services import auth_service, reservation_service, review_service
from simulator.generator import cli
from simulator.generator.events import MongoSink, documents
from simulator.generator.plan import (
    CATEGORIES,
    Config,
    GeneratorError,
    candidates,
    make_sessions,
    members,
)
from simulator.generator.runtime import HistoricalRuntime
from simulator.generator.storage import Journal


def venue_snapshot():
    return [
        {
            "venue_id": index + 1,
            "name": f"가상 공간 {index + 1}",
            "category_code": category,
            "open_hour": 9,
            "close_hour": 23,
            "min_hours": 1,
            "capacity_max": 8,
            "price_per_hour": 10000,
        }
        for index, category in enumerate(CATEGORIES * 6)
    ]


def test_pilot_plan_is_exact_and_reproducible():
    config = Config(75, date(2026, 11, 7))
    sessions = make_sessions(config)
    assert sessions == make_sessions(config)
    assert len(sessions) == 1260
    assert set(Counter(session["at"][:10] for session in sessions).values()) == {42}
    assert sessions[0]["at"][:10] == "2026-10-08"
    assert sessions[-1]["at"][:10] == "2026-11-06"
    assert Counter(members(config)) == {
        "Student": 35,
        "Worker": 25,
        "Gathering": 20,
        "Explorer": 20,
    }
    assert Counter(session["persona"] for session in sessions) == {
        "Student": 441,
        "Worker": 315,
        "Gathering": 252,
        "Explorer": 252,
    }
    assert len({UUID(session["session_id"]) for session in sessions}) == 1260
    assert len({session["person"] for session in sessions}) == 100


def test_candidates_obey_personas_and_booking_rules():
    config = Config(75, date(2026, 11, 7))
    venues = venue_snapshot()
    for session in make_sessions(config):
        choices = candidates(config, session, venues)
        assert len(choices) <= 2
        if session["persona"] == "Explorer":
            assert choices == []
        for body in choices:
            day = date.fromisoformat(body["date"])
            starts = datetime.combine(day, datetime.min.time()).replace(hour=body["start_hour"])
            assert starts > datetime.fromisoformat(session["at"]) + timedelta(minutes=10)
            assert day < config.base_date
            assert body["start_hour"] + body["hours"] <= 23
            if session["persona"] == "Student":
                assert day.weekday() < 5 and 13 <= body["start_hour"] < 19
            if session["persona"] == "Worker":
                assert (day.weekday() < 5 and body["start_hour"] >= 19) or (
                    day.weekday() >= 5 and body["start_hour"] < 12
                )


def test_historical_runtime_restores_aliases_and_keeps_receive_clock(monkeypatch):
    before = clock.get_now
    receive_clock = event_document.get_event_time
    log = Mock(side_effect=AssertionError("운영 이벤트 호출"))
    counter = Mock()
    product_factory = Mock(side_effect=AssertionError("운영 상품 생성"))
    monkeypatch.setattr(reservation_service, "_log_reservation_event", log)
    monkeypatch.setattr(reservation_service, "reservation_counter", counter)
    historical = datetime.fromisoformat("2026-10-08T12:00:00")
    with HistoricalRuntime(historical) as runtime:
        assert clock.get_now() == historical
        assert auth_service.get_now() == historical
        assert review_service.get_today() == historical.date()
        assert reservation_service.get_now() == historical
        reservation_service._log_reservation_event("unused", product_factory=product_factory)
        reservation_service.reservation_counter.labels(result="ok").inc()
        runtime.now += timedelta(days=1)
        assert auth_service.get_now() == historical + timedelta(days=1)
        assert event_document.get_event_time is receive_clock
    assert clock.get_now is before
    assert reservation_service._log_reservation_event is log
    log.assert_not_called()
    counter.assert_not_called()
    product_factory.assert_not_called()


def test_runtime_restores_on_error():
    original = auth_service.get_now
    with (
        pytest.raises(RuntimeError),
        HistoricalRuntime(datetime.fromisoformat("2026-10-08T12:00:00")),
    ):
        raise RuntimeError("실행 중단")
    assert auth_service.get_now is original


def test_journal_recovers_commit_before_file_write_and_rejects_drift(tmp_path):
    manifest = {"seed": 75, "base_date": "2026-11-07"}
    journal = Journal(tmp_path, manifest)
    execute = Mock(side_effect=AssertionError("다시 커밋하면 안 됨"))
    assert journal.perform("booking:1", lambda: {"reservation_id": 7}, execute) == {
        "reservation_id": 7
    }
    resumed = Journal(tmp_path, manifest, resume=True)
    assert resumed.perform("booking:1", lambda: {"reservation_id": 7}, execute) == {
        "reservation_id": 7
    }
    with pytest.raises(GeneratorError, match="DB가 다릅니다"):
        resumed.perform("booking:1", lambda: None, execute)
    with pytest.raises(GeneratorError, match="버전"):
        Journal(tmp_path, {"seed": 76}, resume=True)
    with pytest.raises(GeneratorError, match="기존 실행"):
        Journal(tmp_path, manifest)


def test_event_builder_preserves_real_received_time_and_stable_ids():
    config = Config(75, date(2026, 11, 7))
    session = make_sessions(config)[0]
    record = {"key": "a", "session": 0, "name": "page_view", "at": session["at"], "page": "home"}
    before = clock.get_event_time()
    docs = list(documents(config, [session], list(range(100)), [record]))
    repeated = list(documents(config, [session], list(range(100)), [record]))
    document = docs[0]
    assert set(document) == EVENT_DOCUMENT_FIELDS
    assert document["server"] == "generator" and document["is_synthetic"] is True
    assert before <= document["received_at"] <= clock.get_event_time()
    assert document["occurred_at"].astimezone(clock.KST).date() == date(2026, 10, 8)
    assert document["event_id"] == repeated[0]["event_id"]
    assert document["user"]["session_sequence"] == 1


def test_mongo_sink_accepts_only_matching_event_id_duplicates():
    document = {"event_id": "stable", "event_name": "page_view"}
    failure = {
        "nInserted": 0,
        "writeErrors": [
            {
                "index": 0,
                "code": 11000,
                "errmsg": "uq_event_id",
            }
        ],
    }
    collection = Mock()
    collection.insert_many.side_effect = BulkWriteError(failure)
    collection.find_one.return_value = document.copy()
    assert MongoSink(collection).write([document]) == (0, 1)
    collection.find_one.return_value = {**document, "event_name": "search_submit"}
    with pytest.raises(GeneratorError, match="기존 문서"):
        MongoSink(collection).write([document])


@pytest.mark.parametrize(
    "error",
    [
        {"index": 0, "code": 121, "errmsg": "validator"},
        {"index": 0, "code": 11000, "errmsg": "other_index"},
    ],
)
def test_mongo_sink_does_not_hide_validation_or_other_unique_errors(error):
    collection = Mock()
    collection.insert_many.side_effect = BulkWriteError({"nInserted": 0, "writeErrors": [error]})
    with pytest.raises(BulkWriteError):
        MongoSink(collection).write([{"event_id": "id"}])


def test_mongo_preflight_checks_official_shape_and_indexes():
    collection = Mock()
    collection.options.return_value = {
        "validator": {
            "$and": [
                {"$jsonSchema": {"required": list(EVENT_DOCUMENT_FIELDS)}},
            ]
        }
    }
    indexes = [
        {"name": "uq_event_id", "key": {"event_id": 1}, "unique": True},
        {"name": "ttl", "key": {"received_at": 1}, "expireAfterSeconds": 31536000},
    ]
    collection.list_indexes.return_value = indexes
    MongoSink(collection).preflight()
    collection.list_indexes.return_value = indexes[:1]
    with pytest.raises(GeneratorError, match="TTL"):
        MongoSink(collection).preflight()


def test_dry_run_uses_snapshot_without_database_or_files(tmp_path, monkeypatch):
    snapshot = tmp_path / "venues.json"
    snapshot.write_text(json.dumps(venue_snapshot()), encoding="utf-8")
    monkeypatch.setattr(cli, "load_venues", Mock(side_effect=AssertionError("DB 호출")))
    args = cli.parser().parse_args(
        [
            "--seed",
            "75",
            "--base-date",
            "2026-11-07",
            "--snapshot",
            str(snapshot),
            "--output-root",
            str(tmp_path / "output"),
        ]
    )
    monkeypatch.setattr(cli, "get_today", lambda: date(2026, 11, 7))
    report = cli.execute(args)
    assert report["sessions"] == 1260 and report["ready_venues"]
    assert not (tmp_path / "output").exists()
    args.apply = True
    with pytest.raises(GeneratorError, match="primary"):
        cli.execute(args)


def test_cli_hides_unexpected_error_details(monkeypatch, capsys):
    monkeypatch.setattr(cli, "execute", Mock(side_effect=ValueError("sensitive-value")))
    assert cli.main(["--seed", "75"]) == 1
    assert "sensitive-value" not in capsys.readouterr().err


def test_apply_refuses_incomplete_space_supply():
    assert cli.validate_venues(venue_snapshot(), apply=True)
    with pytest.raises(GeneratorError, match="공간 보충"):
        cli.validate_venues(venue_snapshot()[:5], apply=True)


@pytest.mark.parametrize(
    "values",
    [
        {"seed": -1},
        {"users": 0},
        {"days": 0},
        {"days": 366},
        {"sessions_per_day": 121},
    ],
)
def test_invalid_config_stops_before_writes(values):
    with pytest.raises(GeneratorError):
        Config(**{"seed": 75, "base_date": date(2026, 11, 7), **values})
