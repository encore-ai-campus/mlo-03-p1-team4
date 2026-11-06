"""DB persistence following issue #10's crawl_raw and crawl_jobs contracts."""

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import pymysql
from pymongo import MongoClient, UpdateOne

from config import required_env


CREATE_CRAWL_JOBS_SQL = """
CREATE TABLE IF NOT EXISTS crawl_jobs (
    job_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    source_site VARCHAR(30) NOT NULL,
    started_at DATETIME NOT NULL,
    finished_at DATETIME NULL,
    new_ids INT NOT NULL DEFAULT 0,
    fetched INT NOT NULL DEFAULT 0,
    registered INT NOT NULL DEFAULT 0,
    status ENUM('running', 'done', 'failed') NOT NULL DEFAULT 'running'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""

CRAWL_RAW_COLLECTION = "crawl_raw"
ALLOWED_RAW_STATUSES = {"ok", "no_detail", "excluded", "registered"}
EXTRACTED_FIELDS = {
    "min_capacity",
    "max_capacity",
    "min_hours",
    "area_m2",
    "facilities",
    "prices",
    "open_hours",
    "address_region",
}
MAPPED_FIELDS = {
    "category_code",
    "sido",
    "sigungu",
    "capacity_max",
    "price_per_hour",
    "min_hours",
    "open_hour",
    "close_hour",
    "facilities",
}
SEOUL = timezone(timedelta(hours=9))


def _mariadb_time(value: datetime | None) -> datetime:
    timestamp = value or datetime.now(SEOUL)
    if timestamp.tzinfo is not None:
        return timestamp.astimezone(SEOUL).replace(tzinfo=None)
    return timestamp


def _mysql_connection():
    return pymysql.connect(
        host=required_env("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=required_env("DB_USER"),
        password=required_env("DB_PASSWORD"),
        database=required_env("DB_NAME"),
        charset="utf8mb4",
        autocommit=False,
    )


def _mongo_client() -> MongoClient:
    return MongoClient(required_env("MONGODB_URI"), serverSelectionTimeoutMS=10_000)


def _mongo_database_name() -> str:
    return os.getenv("MONGODB_NAME") or os.getenv("MONGODB_DATABASE") or "crawl"


def crawl_raw_namespace() -> str:
    """Return the database and collection used for raw crawler records."""
    return f"{_mongo_database_name()}.{CRAWL_RAW_COLLECTION}"


def _crawl_raw_collection(client: MongoClient):
    return client[_mongo_database_name()][CRAWL_RAW_COLLECTION]


def _safe_fields(value: dict[str, Any] | None, allowed: set[str]) -> dict[str, Any]:
    """Whitelist DB fields so source names, photos, contacts, and HTML cannot leak in."""
    if not value:
        return {}
    return {key: value[key] for key in allowed if key in value}


def start_crawl_job(source_site: str, *, started_at: datetime | None = None) -> int:
    """Create a running MariaDB crawl_jobs record and return its numeric ID."""
    connection = _mysql_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_CRAWL_JOBS_SQL)
            cursor.execute(
                "INSERT INTO crawl_jobs (source_site, started_at, status) VALUES (%s, %s, 'running')",
                (source_site, _mariadb_time(started_at)),
            )
            job_id = cursor.lastrowid
        connection.commit()
        return int(job_id)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def save_crawl_raw_records(job_id: int | None, source_site: str, records: list[dict[str, Any]]) -> int:
    """Upsert sanitized extraction records into MongoDB ``crawl_raw``."""
    client = _mongo_client()
    try:
        client.admin.command("ping")
        collection = _crawl_raw_collection(client)
        collection.create_index([("source_site", 1), ("source_id", 1)], unique=True)

        now = datetime.now(timezone.utc)
        operations = []
        for record in records:
            source_id = str(record["source_id"])
            status = record.get("status", "ok")
            if status not in ALLOWED_RAW_STATUSES:
                raise ValueError(f"Unsupported crawl_raw status: {status}")
            document = {
                "source_site": source_site,
                "source_id": source_id,
                "crawled_at": now,
                "status": status,
                "space_types": [
                    str(value)[:100]
                    for value in (record.get("space_types") or [])
                    if isinstance(value, (str, int, float))
                ],
                "extracted": _safe_fields(record.get("extracted"), EXTRACTED_FIELDS),
                "mapped": _safe_fields(record.get("mapped"), MAPPED_FIELDS),
                "exclude_reason": record.get("exclude_reason"),
            }
            if job_id is not None:
                document["job_id"] = job_id
            if record.get("venue_id") is not None:
                document["venue_id"] = int(record["venue_id"])
            operations.append(
                UpdateOne(
                    {"source_site": source_site, "source_id": source_id},
                    {"$set": document},
                    upsert=True,
                )
            )

        if operations:
            collection.bulk_write(operations, ordered=False)
        return len(operations)
    finally:
        client.close()


def count_new_source_ids(source_site: str, source_ids: list[str | int]) -> int:
    """Count IDs not yet present in crawl_raw; used for this run's new_ids metric."""
    normalized_ids = {str(source_id) for source_id in source_ids}
    if not normalized_ids:
        return 0

    client = _mongo_client()
    try:
        collection = _crawl_raw_collection(client)
        existing = set(
            collection.distinct(
                "source_id",
                {"source_site": source_site, "source_id": {"$in": list(normalized_ids)}},
            )
        )
        return len(normalized_ids - existing)
    finally:
        client.close()


def mark_crawl_record_registered(
    source_site: str, source_id: str | int, venue_id: int
) -> None:
    """Record the /internal/venues upsert result in the matching crawl_raw row."""
    client = _mongo_client()
    try:
        result = _crawl_raw_collection(client).update_one(
            {"source_site": source_site, "source_id": str(source_id)},
            {"$set": {"status": "registered", "venue_id": int(venue_id)}},
        )
        if result.matched_count != 1:
            raise LookupError(f"crawl_raw row not found for {source_site}:{source_id}")
    finally:
        client.close()


def finish_crawl_job(
    job_id: int,
    *,
    new_ids: int,
    fetched: int,
    registered: int,
    status: str = "done",
    finished_at: datetime | None = None,
) -> int:
    """Finish the run and return the active venue count for the three-count report."""
    if status not in {"done", "failed"}:
        raise ValueError("Final crawl job status must be 'done' or 'failed'")

    connection = _mysql_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE crawl_jobs
                   SET finished_at = %s, new_ids = %s, fetched = %s,
                       registered = %s, status = %s
                   WHERE job_id = %s""",
                (
                    _mariadb_time(finished_at),
                    new_ids,
                    fetched,
                    registered,
                    status,
                    job_id,
                ),
            )
            cursor.execute("SELECT COUNT(*) FROM venues WHERE is_active = TRUE")
            total_demo_venues = int(cursor.fetchone()[0])
        connection.commit()
        return total_demo_venues
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
