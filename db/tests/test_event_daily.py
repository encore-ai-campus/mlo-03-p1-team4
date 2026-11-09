"""event_daily 집계의 날짜 경계·행 변환·CSV (MongoDB 없이)."""

import csv
import importlib.util
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("event_daily", ROOT / "db/aggregate/event_daily.py")
event_daily = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(event_daily)


def test_day_range_is_korean_midnight_to_midnight():
    start, end = event_daily.day_range(date(2026, 11, 7))
    assert start.isoformat() == "2026-11-07T00:00:00+09:00"
    assert end - start == timedelta(days=1)


def test_target_days_counts_back_from_today():
    today = date(2026, 11, 7)
    assert event_daily.target_days(on=None, days=2, today=today) == [date(2026, 11, 6), today]
    assert event_daily.target_days(on=date(2026, 1, 1), days=30, today=today) == [date(2026, 1, 1)]


def test_target_days_rejects_zero():
    try:
        event_daily.target_days(on=None, days=0, today=date(2026, 11, 7))
    except ValueError:
        return
    raise AssertionError("days=0은 거부해야 한다")


def test_pipeline_matches_range_and_unwinds_products_keeping_empty():
    start, end = event_daily.day_range(date(2026, 11, 7))
    stages = event_daily.pipeline(start, end)
    assert stages[0] == {"$match": {"occurred_at": {"$gte": start, "$lt": end}}}
    assert stages[1]["$unwind"]["preserveNullAndEmptyArrays"] is True
    group = stages[2]["$group"]["_id"]
    assert group["date"]["$dateToString"]["timezone"] == "Asia/Seoul"


def test_to_rows_normalizes_types_and_sorts():
    groups = [
        {
            "_id": {
                "date": "2026-11-07",
                "event_type": "product_view",
                "venue_id": "7",
                "is_synthetic": True,
            },
            "count": 3,
        },
        {
            "_id": {
                "date": "2026-11-07",
                "event_type": "login",
                "venue_id": None,
                "is_synthetic": False,
            },
            "count": 2,
        },
    ]
    rows = event_daily.to_rows(groups)
    assert rows[0] == {
        "date": "2026-11-07",
        "event_type": "login",
        "venue_id": None,
        "is_synthetic": False,
        "count": 2,
    }
    assert rows[1]["venue_id"] == "7" and rows[1]["count"] == 3


def test_write_csv_has_four_columns_and_text_booleans(tmp_path):
    out = tmp_path / "out" / "daily.csv"
    event_daily.write_csv(
        [
            {
                "date": "2026-11-07",
                "event_type": "login",
                "is_synthetic": False,
                "count": 2,
            }
        ],
        out,
    )
    with out.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows == [
        {
            "date": "2026-11-07",
            "event_type": "login",
            "is_synthetic": "false",
            "count": "2",
        }
    ]


def test_export_csv_sums_venues_but_keeps_synthetic_separate(tmp_path):
    class Collection:
        def find(self, query, projection):
            assert query == {"date": {"$in": ["2026-11-07"]}}
            assert projection == {"_id": 0, **dict.fromkeys(event_daily.CSV_FIELDS, 1)}
            return [
                {
                    "date": "2026-11-07",
                    "event_type": "product_view",
                    "is_synthetic": True,
                    "count": 3,
                },
                {
                    "date": "2026-11-07",
                    "event_type": "product_view",
                    "is_synthetic": False,
                    "count": 2,
                },
                {
                    "date": "2026-11-07",
                    "event_type": "product_view",
                    "is_synthetic": True,
                    "count": 4,
                },
            ]

    class DB:
        event_daily = Collection()

    out = tmp_path / "event_daily.csv"
    assert event_daily.export_csv(DB, [date(2026, 11, 7)], out) == 2
    with out.open(encoding="utf-8-sig", newline="") as f:
        assert list(csv.DictReader(f)) == [
            {
                "date": "2026-11-07",
                "event_type": "product_view",
                "is_synthetic": "false",
                "count": "2",
            },
            {
                "date": "2026-11-07",
                "event_type": "product_view",
                "is_synthetic": "true",
                "count": "7",
            },
        ]


def test_aggregation_runs_against_fake_collection():
    """bulk_write·delete_many 호출 형태 확인(집계 결과 그대로 덮어쓰기)."""

    class Coll:
        def __init__(self):
            self.ops, self.deleted = [], None

        def aggregate(self, stages, allowDiskUse):
            return [
                {
                    "_id": {
                        "date": "2026-11-07",
                        "event_type": "page_view",
                        "venue_id": None,
                        "is_synthetic": False,
                    },
                    "count": 5,
                }
            ]

        def bulk_write(self, ops, ordered):
            self.ops = ops
            return type("R", (), {"upserted_count": len(ops)})()

        def delete_many(self, query):
            self.deleted = query
            return type("R", (), {"deleted_count": 0})()

    class DB:
        events = Coll()
        event_daily = Coll()

    result = event_daily.aggregate_day(DB, date(2026, 11, 7))
    assert result == {"date": "2026-11-07", "groups": 1, "new": 1, "removed": 0}
    op = DB.event_daily.ops[0]
    assert op._doc == {"$set": {"count": 5}} and op._upsert is True
    assert (
        DB.event_daily.deleted["date"] == "2026-11-07" and len(DB.event_daily.deleted["$nor"]) == 1
    )
