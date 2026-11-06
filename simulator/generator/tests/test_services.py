"""실제 MariaDB의 서비스 트랜잭션·중단 복구·세션 전체 흐름 검증."""

import json
import os
import shutil
import subprocess
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.clock import KST
from app.core.event_document import EVENT_DOCUMENT_FIELDS
from app.core.metrics import reservation_counter
from app.repositories import reservation_repo
from simulator.generator.events import MongoSink
from simulator.generator.gateway import Gateway
from simulator.generator.plan import Config
from simulator.generator.runner import Runner
from simulator.generator.runtime import HistoricalRuntime
from simulator.generator.storage import Journal, atomic_json


@pytest.fixture
def database():
    raw = os.environ.get("CHECK_DB_URL")
    if not raw:
        pytest.skip("로컬 MariaDB CHECK_DB_URL이 없습니다.")
    url = make_url(raw)
    if (
        url.database != "spacecube_test"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or url.drivername != "mysql+pymysql"
    ):
        pytest.fail("생성기 테스트는 로컬 MariaDB spacecube_test에서만 실행합니다.")
    engine = create_engine(url, poolclass=NullPool, hide_parameters=True)
    with engine.connect() as connection:
        assert "MariaDB" in connection.scalar(text("SELECT VERSION()"))
        connection.execute(text("SET time_zone = '+09:00'"))
        connection.commit()
        outer = connection.begin()
        try:
            yield connection
        finally:
            outer.rollback()
    engine.dispose()


@pytest.fixture
def venues(database):
    categories = database.execute(
        text("SELECT category_id,code FROM categories ORDER BY category_id")
    ).all()
    assert len(categories) == 5
    region = database.scalar(text("SELECT MIN(region_id) FROM regions"))
    snapshot = []
    for category_id, code in categories:
        for _ in range(6):
            venue_id = database.execute(
                text(
                    "INSERT INTO venues (region_id,category_id,name,capacity_max,price_per_hour,min_hours,"
                    "open_hour,close_hour,source_site,source_id) "
                    "VALUES (:region,:category,'생성기 검증 공간',8,10000,1,9,23,'synthetic',:source)"
                ),
                {"region": region, "category": category_id, "source": uuid4().hex},
            ).lastrowid
            snapshot.append(
                {
                    "venue_id": venue_id,
                    "name": "생성기 검증 공간",
                    "category_code": code,
                    "capacity_max": 8,
                    "price_per_hour": 10000,
                    "min_hours": 1,
                    "open_hour": 9,
                    "close_hour": 23,
                }
            )
    return snapshot


def factory(database):
    return lambda: Session(
        bind=database, join_transaction_mode="create_savepoint", expire_on_commit=False
    )


class MemorySink:
    def __init__(self):
        self.items = {}

    def write(self, batch):
        duplicates = sum(document["event_id"] in self.items for document in batch)
        self.items.update((document["event_id"], document) for document in batch)
        return len(batch) - duplicates, duplicates


@pytest.fixture
def mongo_sink():
    """명시한 주소의 전용 테스트 컬렉션만 만든다. 운영 events와 기존 스키마는 보존한다."""
    raw = os.environ.get("CHECK_MONGO_URL")
    if not raw:
        yield None
        return
    node = shutil.which("node")
    assert node is not None, "공식 mongo_init.js 추출용 기존 Node 실행 경로가 필요합니다."
    root = Path(__file__).resolve().parents[3]
    schema = subprocess.run(  # noqa: S603 -- 저장소의 고정 스키마 추출 스크립트, shell 없음
        [
            node,
            str(Path(__file__).with_name("mongo_schema.cjs")),
            str(root / "docs/db/mongo_init.js"),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    definitions = json.loads(schema.stdout)
    client = MongoClient(raw, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, tz_aware=True)
    try:
        client.admin.command("ping")
    except Exception as error:
        client.close()
        pytest.fail(f"지정 MongoDB 연결 실패 ({type(error).__name__})", pytrace=False)
    name = f"generator_validation_{uuid4().hex}"
    collection = client["space_rental_analytics_test"].create_collection(
        name, **definitions["options"]
    )
    for index in definitions["indexes"]:
        collection.create_index(list(index["keys"].items()), **index["options"])
    sink = MongoSink(collection)
    sink.preflight()
    try:
        yield sink
    finally:
        # 원격 DROP·대량 DELETE는 하지 않고 DB 담당 확인용 검증 결과로 남긴다.
        client.close()


def test_real_services_recover_booking_cancel_and_review_commit_windows(database, venues, tmp_path):
    config = Config(int(uuid4().hex[:12], 16), date(2026, 11, 7))
    journal = Journal(tmp_path, {"config": config.document()})
    start = datetime.fromisoformat("2026-10-08T08:00:00")
    with HistoricalRuntime(start) as runtime:
        gateway = Gateway(journal, runtime, config, factory(database))
        user_id = gateway.signup(0, start)
        body = {
            "venue_id": venues[0]["venue_id"],
            "date": "2026-10-09",
            "start_hour": 13,
            "hours": 1,
            "headcount": 2,
            "method": "card",
        }
        booking = gateway.book("booking:0", user_id, "session", body, start, 10000)
        # SQL 커밋 후 파일 기록 전 중단을 재현한다.
        journal.operations.pop("booking:0")
        assert gateway.book("booking:0", user_id, "session", body, start, 10000) == booking
        reservation_id = booking["reservation_id"]
        gateway.cancel(reservation_id, user_id, "session", start + timedelta(minutes=1))
        journal.operations.pop(f"cancel:{reservation_id}")
        gateway.cancel(reservation_id, user_id, "session", start + timedelta(minutes=1))
        # 취소가 슬롯을 반납한 뒤에도 예약을 다시 만들지 않는다.
        journal.operations.pop("booking:0")
        assert gateway.book("booking:0", user_id, "session", body, start, 10000) == booking
        body["start_hour"] = 15
        next_booking = gateway.book(
            "booking:1", user_id, "session", body, start + timedelta(minutes=2), 10000
        )
        next_id = next_booking["reservation_id"]
        review_at = datetime.fromisoformat("2026-10-10T12:00:00")
        gateway.complete(next_id, user_id, review_at)
        result = gateway.review(next_id, user_id, 5, "생성기 검증 후기", review_at)
        journal.operations.pop(f"review:{next_id}")
        assert gateway.review(next_id, user_id, 5, "생성기 검증 후기", review_at) == result
        assert (
            database.scalar(
                text("SELECT COUNT(*) FROM reservations WHERE user_id=:user"), {"user": user_id}
            )
            == 2
        )
        assert (
            database.scalar(
                text("SELECT COUNT(*) FROM reviews WHERE user_id=:user"), {"user": user_id}
            )
            == 1
        )


@pytest.mark.parametrize("pilot", [False, True], ids=["small", "100-users-30-days"])
def test_full_service_flow_and_resume_preserve_counts_and_metrics(
    database, venues, tmp_path, pilot, request
):
    options = {} if pilot else {"users": 8, "days": 14, "sessions_per_day": 12}
    config = Config(int(uuid4().hex[:12], 16), date(2026, 11, 7), **options)
    manifest = {"config": config.document(), "venues": venues}
    journal = Journal(tmp_path, manifest)
    remote_sink = request.getfixturevalue("mongo_sink") if pilot else None
    sink = remote_sink or MemorySink()
    before = reservation_counter.labels(result="ok")._value.get()
    with HistoricalRuntime(datetime.fromisoformat("2026-10-24T00:00:00")) as runtime:
        gateway = Gateway(journal, runtime, config, factory(database))
        runner = Runner(config, venues, gateway, journal, sink)
        report = runner.run()
        if remote_sink is not None:
            sink.items = {document["event_id"]: document for document in sink.collection.find({})}
        assert report["sessions"] == config.days * config.sessions_per_day
        assert report["users"] == config.users
        assert report["reservations"] > 10
        assert report["cancelled"] == report["reservations"] // 10
        assert report["completed"] == report["reservations"] - report["cancelled"]
        assert report["reviews"] == report["completed"] // 4
        assert reservation_counter.labels(result="ok")._value.get() == before
        assert all(
            set(document) - {"_id"} == EVENT_DOCUMENT_FIELDS for document in sink.items.values()
        )
        assert all(
            document["is_synthetic"] and document["server"] == "generator"
            for document in sink.items.values()
        )
        personas = {session["session_id"]: session["persona"] for session in runner.sessions}
        assert not any(
            document["event_name"] == "reservation_start"
            and personas[document["user"]["session_id"]] == "Explorer"
            for document in sink.items.values()
        )
        per_session = Counter(document["user"]["session_id"] for document in sink.items.values())
        for session_id, count in per_session.items():
            assert sorted(
                document["user"]["session_sequence"]
                for document in sink.items.values()
                if document["user"]["session_id"] == session_id
            ) == list(range(1, count + 1))
        # 리뷰 시각은 이용 종료 뒤, 생성 기간 안이다.
        reviews = [
            document
            for document in sink.items.values()
            if document["event_name"] == "review_create"
        ]
        assert reviews
        assert all(
            document["occurred_at"] > document["products"][0]["rental_conditions"]["end_at"]
            for document in reviews
        )
        assert all(
            document["occurred_at"].astimezone(KST).date() < config.base_date
            for document in reviews
        )
        resumed = Journal(tmp_path, manifest, resume=True)
        gateway = Gateway(resumed, runtime, config, factory(database))
        again = Runner(config, venues, gateway, resumed, sink).run()
        assert again["reservations"] == report["reservations"]
        assert again["events"] == report["events"]
        assert again["mongo_inserted"] == 0
        assert again["mongo_duplicates"] == report["events"]
        for booking in runner.created:
            with Session(bind=database, join_transaction_mode="create_savepoint") as db:
                owned = reservation_repo.get_owned(
                    db, booking["user_id"], booking["reservation_id"]
                )
            assert owned[5] == ("cancelled" if booking["cancelled"] else "completed")
        if remote_sink is not None:
            assert sink.collection.count_documents({}) == report["events"]
            with pytest.raises(BulkWriteError) as invalid:
                sink.write([{"event_id": str(uuid4()), "is_synthetic": True}])
            assert invalid.value.details["writeErrors"][0]["code"] == 121
            output = (
                Path(__file__).resolve().parents[3]
                / "logs"
                / f"generator-validation-{config.run_id}"
            )
            output.mkdir(parents=True, exist_ok=True)
            artifact = {
                **report,
                "resume": again,
                "mongo_collection": sink.collection.full_name,
                "official_validator": "passed",
                "invalid_document_code": 121,
                "mariadb": "spacecube_test: outer transaction rollback",
            }
            atomic_json(output / "report.json", artifact)
            print(
                json.dumps(
                    {
                        "report": str(output / "report.json"),
                        "collection": sink.collection.full_name,
                        "sessions": report["sessions"],
                        "events": report["events"],
                        "resume_inserted": again["mongo_inserted"],
                    },
                    ensure_ascii=False,
                )
            )
