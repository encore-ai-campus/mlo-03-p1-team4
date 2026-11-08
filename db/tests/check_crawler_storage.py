"""F-61 MongoDB crawl_raw·MariaDB crawl_jobs 실제 저장 확인(API 호출 없음).

루트에서 실행: conda run -n pro_1 --no-capture-output python -m db.tests.check_crawler_storage
DB_WRITE_URL은 반드시 spacecube_test를 가리킨다. 검사 행은 확인 뒤 각각 한 건만 지운다.
"""

from __future__ import annotations

from uuid import uuid4

from pymongo import MongoClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from crawler.crawl_venues import finish_job, raw_document, start_job
from crawler.preprocess import SeedMaps, map_space
from crawler.spacecloud_crawler import SpaceInfo


def main() -> None:
    settings = get_settings()
    if settings.db_write_url is None or settings.mongo_url is None:
        raise SystemExit("backend/.env에 DB_WRITE_URL·MONGO_URL을 설정하세요.")
    db_url = settings.db_write_url.get_secret_value()
    if make_url(db_url).database != "spacecube_test":
        raise SystemExit("저장 검증은 MariaDB spacecube_test에서만 실행합니다.")

    engine = create_engine(db_url, pool_pre_ping=True)
    mongo = MongoClient(settings.mongo_url.get_secret_value(), serverSelectionTimeoutMS=3000)
    job_id: int | None = None
    inserted = False
    source_id = str(uuid4().int)
    raw = mongo.get_database("crawl").get_collection("crawl_raw")
    try:
        mongo.admin.command("ping")
        if "crawl_raw" not in mongo.get_database("crawl").list_collection_names():
            raise RuntimeError("MongoDB crawl.crawl_raw가 없습니다. mongo_init.js를 확인하세요.")
        with engine.connect() as db:
            db.execute(text("SELECT 1 FROM crawl_jobs LIMIT 1"))

        space = SpaceInfo(
            source_id=source_id,
            space_types=["스터디룸"],
            max_capacity=4,
            min_hours=1,
            facilities=["와이파이"],
            prices=[{"amount": 10000, "unit": "시간", "per_person": False}],
            open_hours="09:00~23:00",
            address_region="서울 마포구",
        )
        mapped, reason = map_space("spacecloud", space, SeedMaps.load())
        if mapped is None or reason is not None:
            raise RuntimeError("검증용 공간 속성 매핑에 실패했습니다.")

        job_id = start_job(engine, "spacecloud")
        document = raw_document("spacecloud", space, job_id, mapped, None)
        # API 없이 저장 경로만 확인한다. 남더라도 등록 후보로 처리되지 않게 제외 상태로 둔다.
        document["status"] = "excluded"
        document["exclude_reason"] = "저장 검증용"
        raw.insert_one(document)
        inserted = True
        stored = raw.find_one({"source_site": "spacecloud", "source_id": source_id})
        if (
            stored is None
            or stored["job_id"] != job_id
            or stored["extracted"]["address_region"] != "서울 마포구"
            or stored["mapped"]["category"] != "studyroom"
            or stored["status"] != "excluded"
        ):
            raise RuntimeError("MongoDB crawl_raw 저장값이 예상과 다릅니다.")

        finish_job(engine, job_id, {"new_ids": 1, "fetched": 1, "registered": 0}, "done")
        with engine.connect() as db:
            row = db.execute(
                text(
                    "SELECT source_site, new_ids, fetched, registered, status "
                    "FROM crawl_jobs WHERE job_id = :job_id"
                ),
                {"job_id": job_id},
            ).one_or_none()
        if row is None or tuple(row) != ("spacecloud", 1, 1, 0, "done"):
            raise RuntimeError("MariaDB crawl_jobs 저장값이 예상과 다릅니다.")
    finally:
        try:
            if inserted:
                deleted = raw.delete_one({"source_site": "spacecloud", "source_id": source_id})
                if deleted.deleted_count != 1:
                    raise RuntimeError("MongoDB 검증 문서 정리 결과가 예상과 다릅니다.")
        finally:
            try:
                if job_id is not None:
                    with engine.begin() as db:
                        deleted = db.execute(
                            text("DELETE FROM crawl_jobs WHERE job_id = :job_id"),
                            {"job_id": job_id},
                        )
                        if deleted.rowcount != 1:
                            raise RuntimeError("MariaDB 검증 행 정리 결과가 예상과 다릅니다.")
            finally:
                mongo.close()
                engine.dispose()
    print("MongoDB crawl_raw·MariaDB crawl_jobs 각 1건 저장·재조회·정리 확인")


if __name__ == "__main__":
    main()
