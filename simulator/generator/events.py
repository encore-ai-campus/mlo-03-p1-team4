"""공식 문서 빌더와 MongoDB 중복 처리를 사용하는 생성기 이벤트 출력."""

from datetime import datetime, time

from pymongo.errors import BulkWriteError

from app.core.clock import KST
from app.core.event_document import EVENT_DOCUMENT_FIELDS, build_document

from .plan import GeneratorError


def browser_context(config, session, page_type, venue_id=None):
    path = {
        "home": "/",
        "search_results": "/search",
        "product_detail": f"/venues/{venue_id}",
        "checkout": "/reserve",
        "my_page": "/me",
        "reviews": "/reviews",
    }[page_type]
    url = "http://generator.invalid" + path
    page_id = config.identifier(f"page:{session['index']}:{path}")
    return {
        "site": {"site_id": "main", "hostname": "generator.invalid", "platform": "desktop_web"},
        "acquisition": {"landing_url": "http://generator.invalid/", "referrer_url": None},
        "page": {"page_view_id": page_id, "page_type": page_type, "url": url},
        "navigation": {
            "from": None,
            "to": {"page_view_id": page_id, "site_id": "main", "url": url},
            "navigation_type": "internal" if page_type != "home" else "direct",
        },
    }


def product(venue, body=None):
    starts_at = ends_at = None
    if body is not None:
        day = datetime.fromisoformat(body["date"]).date()
        starts_at = datetime.combine(day, time(body["start_hour"]), tzinfo=KST)
        ends_at = starts_at.replace(hour=body["start_hour"] + body["hours"])
    return {
        "product_id": str(venue["venue_id"]),
        "product_name": venue["name"],
        "price": {
            "currency": "KRW",
            "displayed_amount_minor": venue["price_per_hour"],
            "billing_unit": "hour",
        },
        "rental_conditions": {
            "start_at": starts_at,
            "end_at": ends_at,
            "timezone": "Asia/Seoul",
            "guest_count": body["headcount"] if body else None,
            "option_ids": [],
        },
    }


def documents(config, sessions, user_ids, records):
    """후속 후기까지 확정된 후 세션별 순서를 고정해 event_id를 만든다."""
    grouped = {session["index"]: [] for session in sessions}
    for record in records:
        grouped[record["session"]].append(record)
    for session in sessions:
        ordered = sorted(grouped[session["index"]], key=lambda row: (row["at"], row["key"]))
        for sequence, record in enumerate(ordered, 1):
            document = build_document(
                event_id=config.identifier(f"event:{session['index']}:{sequence}"),
                session_id=session["session_id"],
                user_id=user_ids[session["person"]],
                anonymous_id=config.identifier(f"anonymous:{session['person']}"),
                session_sequence=sequence,
                event_name=record["name"],
                occurred_at=datetime.fromisoformat(record["at"]).replace(tzinfo=KST),
                context=browser_context(config, session, record["page"], record.get("venue_id")),
                products=record.get("products", []),
                properties=record.get("properties", {}),
                is_synthetic=True,
            )
            document["server"] = "generator"
            yield document


class MongoSink:
    def __init__(self, collection):
        self.collection = collection

    def preflight(self):
        self.collection.database.client.admin.command("ping")
        options = self.collection.options()
        validator = options.get("validator", {})
        schemas = validator.get("$and", [validator])
        if not any(
            set(item.get("$jsonSchema", {}).get("required", [])) >= EVENT_DOCUMENT_FIELDS
            for item in schemas
        ):
            raise GeneratorError("공식 events validator를 먼저 적용해야 합니다(#71).")
        if (
            options.get("validationAction", "error") != "error"
            or options.get("validationLevel", "strict") != "strict"
        ):
            raise GeneratorError("events validator는 strict/error여야 합니다.")
        indexes = list(self.collection.list_indexes())
        if not any(
            index.get("name") == "uq_event_id"
            and dict(index["key"]) == {"event_id": 1}
            and index.get("unique")
            for index in indexes
        ):
            raise GeneratorError("uq_event_id UNIQUE 인덱스가 필요합니다.")
        if not any(
            dict(index["key"]) == {"received_at": 1}
            and index.get("expireAfterSeconds") == 365 * 86400
            for index in indexes
        ):
            raise GeneratorError("received_at 기준 365일 TTL 인덱스가 필요합니다.")

    def write(self, batch):
        try:
            result = self.collection.insert_many(batch, ordered=False)
            return len(result.inserted_ids), 0
        except BulkWriteError as error:
            details = error.details
            errors = details.get("writeErrors", [])
            if not errors or details.get("writeConcernErrors"):
                raise
            for item in errors:
                if item.get("code") != 11000 or not (
                    item.get("keyPattern") == {"event_id": 1}
                    or "uq_event_id" in item.get("errmsg", "")
                ):
                    raise
                expected = batch[item["index"]]
                stored = self.collection.find_one({"event_id": expected["event_id"]})
                # 같은 ID인데 내용이 다르면 다른 실행/손상이다. 수신 시각만 재적재와 다를 수 있다.
                comparable = EVENT_DOCUMENT_FIELDS - {"received_at"}
                if stored is None or any(
                    stored.get(key) != expected.get(key) for key in comparable
                ):
                    raise GeneratorError(
                        "중복 event_id의 기존 문서가 이번 실행과 다릅니다."
                    ) from None
            inserted = details.get("nInserted", 0)
            if inserted + len(errors) != len(batch):
                raise
            return inserted, len(errors)
