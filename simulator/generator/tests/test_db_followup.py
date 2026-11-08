"""#19 DB 후속 산출물의 오프라인 계약 검증."""

import csv
import json
from datetime import UTC, date, datetime
from types import SimpleNamespace

from pydantic import SecretStr

from simulator.generator import analytics
from simulator.generator.analytics import EVENT_FIELDS, atomic_csv, export_event_rows, period_bounds
from simulator.generator.audit import inspect
from simulator.generator.topup import prepare


class Cursor(list):
    def sort(self, *_args):
        return self


class Events:
    def __init__(self, rows):
        self.rows = rows

    def find(self, *_args):
        return Cursor(self.rows)

    def aggregate(self, *_args, **_kwargs):
        return [
            {
                "date": "2026-11-07",
                "event_type": "product_view",
                "venue_id": "21",
                "is_synthetic": True,
                "count": 1,
            }
        ]


def test_kst_period_and_csv_audit(tmp_path):
    start, start_utc, end_utc = period_bounds(date(2026, 11, 8), 1)
    assert start == date(2026, 11, 7)
    assert start_utc == datetime(2026, 11, 6, 15, tzinfo=UTC)
    assert end_utc == datetime(2026, 11, 7, 15, tzinfo=UTC)

    events = Events(
        [
            {
                "event_id": "event-1",
                "occurred_at": datetime(2026, 11, 6, 15, 1, tzinfo=UTC),
                "event_name": "product_view",
                "user": {
                    "session_id": "session-1",
                    "user_id": "7",
                    "anonymous_id": "anon-1",
                    "session_sequence": 1,
                },
                "products": [{"product_id": "21"}, {"product_id": "21"}],
                "page": {"page_type": "product_detail"},
                "properties": {"source": "test"},
                "is_synthetic": True,
            }
        ]
    )
    rows = export_event_rows(events, start_utc, end_utc)
    assert len(rows) == 1
    assert rows[0]["occurred_at(KST)"] == "2026-11-07T00:01:00+09:00"
    event_csv = tmp_path / "events.csv"
    daily_csv = tmp_path / "daily.csv"
    atomic_csv(event_csv, EVENT_FIELDS, rows)
    atomic_csv(
        daily_csv,
        ("date", "event_type", "venue_id", "is_synthetic", "count"),
        [
            {
                "date": "2026-11-07",
                "event_type": "product_view",
                "venue_id": "21",
                "is_synthetic": True,
                "count": 1,
            }
        ],
    )
    with event_csv.open(encoding="utf-8-sig", newline="") as stream:
        assert next(iter(csv.DictReader(stream)))["properties(JSON)"] == json.dumps(
            {"source": "test"}, ensure_ascii=False, sort_keys=True
        )
    result = inspect(
        {"events": 1, "sessions": 1, "period_start": "2026-11-07", "period_end": "2026-11-07"},
        event_csv,
        daily_csv,
    )
    assert all(result["checks"].values())
    assert result["daily_event_types"] == {"product_view": 1}


def test_topup_deterministic_and_contract():
    source = {
        "category_code": "cafe",
        "source_site": "shareit",
        "source_id": "123",
        "verified": True,
        "is_active": True,
        "sido": "서울",
        "sigungu": "종로구",
        "capacity_max": 12,
        "price_per_hour": 20000,
        "min_hours": 1,
        "open_hour": 9,
        "close_hour": 23,
        "facilities": [],
    }
    others = [
        {**source, "category_code": category, "source_id": f"{category}-{n}"}
        for category in ("studyroom", "studio", "lectureroom", "partyroom")
        for n in range(3)
    ]
    snapshot = {"venues": [source, *others]}
    first = prepare(snapshot, target=3, seed=75)
    second = prepare(snapshot, target=3, seed=75)
    assert first == second
    assert len(first["requests"]) == 2
    assert first["requests"][0]["source_site"] == "synthetic"
    assert first["requests"][0]["images"] == ["art:cafe-0"]
    resumed = prepare(
        {"venues": [*snapshot["venues"], {**first["requests"][0], "is_active": True}]},
        target=3,
        seed=75,
    )
    assert len(resumed["requests"]) == 1
    assert resumed["requests"][0]["source_id"] != first["requests"][0]["source_id"]


def test_aggregate_rerun_replaces_daily_count(monkeypatch, tmp_path):
    event = {
        "event_id": "event-1",
        "occurred_at": datetime(2026, 11, 7, 1, tzinfo=UTC),
        "event_name": "product_view",
        "user": {"session_id": "session-1", "anonymous_id": "anon-1", "session_sequence": 1},
        "products": [{"product_id": "21"}],
        "page": {"page_type": "product_detail"},
        "properties": {},
        "is_synthetic": True,
    }

    class Daily:
        def __init__(self):
            self.rows = [{"date": "2026-11-07", "event_type": "old", "count": 9}]

        def index_information(self):
            return {
                "unique": {
                    "key": [("date", 1), ("event_type", 1), ("venue_id", 1), ("is_synthetic", 1)],
                    "unique": True,
                }
            }

        def delete_many(self, *_args):
            self.rows.clear()

        def insert_many(self, rows, **_kwargs):
            self.rows.extend(rows)

        def find(self, *_args):
            return Cursor(self.rows)

    daily = Daily()

    class Client:
        admin = SimpleNamespace(command=lambda *_args: None)

        def __getitem__(self, _name):
            return {"events": Events([event]), "event_daily": daily}

        def close(self):
            pass

    monkeypatch.setattr(analytics, "MongoClient", lambda *_args, **_kwargs: Client())
    monkeypatch.setattr(
        analytics,
        "aggregate_day",
        lambda _database, _day: {"date": "2026-11-07", "groups": 1},
    )

    def export_daily(_database, _days, path):
        atomic_csv(
            path,
            ("date", "event_type", "venue_id", "is_synthetic", "count"),
            Events([]).aggregate(),
        )
        return 1

    monkeypatch.setattr(analytics, "export_csv", export_daily)
    monkeypatch.setattr(
        analytics,
        "get_settings",
        lambda: SimpleNamespace(mongo_url=SecretStr("mongodb://example.invalid"), mongo_db="test"),
    )
    monkeypatch.setattr(analytics, "get_today", lambda: date(2026, 11, 8))
    argv = ["--base-date", "2026-11-08", "--days", "1", "--output-root", str(tmp_path)]
    assert analytics.main(argv) == 0
    assert analytics.main(argv) == 0
    assert (tmp_path / "events-2026-11-07-2026-11-08-event-daily.csv").exists()
