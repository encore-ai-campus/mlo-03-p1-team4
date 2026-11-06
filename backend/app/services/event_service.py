"""F-60 프론트 이벤트 수집: 새 요청 검증과 B 공간 조회 연결."""

import logging
from collections import Counter
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from app.core.db import get_db_write
from app.core.errors import fail, invalid_field
from app.core.event_context import ClientEventContext, client_event_context
from app.core.event_document import FE_EVENTS, PRODUCT_EVENTS, build_document
from app.core.events import log_event, require_event_file, sanitize_payload
from app.repositories import venue_repo
from app.schemas.events import EventBatchCreate


def _products(items):
    ids = set()
    for item in items:
        if item.event_name not in PRODUCT_EVENTS:
            continue
        if len(item.products) != 1:
            raise invalid_field("products", "상품 ID 한 개")
        raw = item.products[0].product_id
        if not isinstance(raw, str) or not raw.isdecimal() or int(raw) < 1:
            raise invalid_field("products.product_id", "존재하는 공간 ID")
        ids.add(int(raw))
    if not ids:
        return {}
    # 수집 시점의 가격 스냅샷은 복제 지연이 없는 primary에서 읽는다.
    generator = get_db_write()
    try:
        db = next(generator)
        rows = {venue_id: venue_repo.get_detail(db, venue_id) for venue_id in ids}
    except SQLAlchemyError:
        raise fail("SERVICE_UNAVAILABLE", 503) from None
    finally:
        generator.close()
    if any(row is None for row in rows.values()):
        raise invalid_field("products.product_id", "존재하는 활성 공간 ID")
    result = {}
    for venue_id, row in rows.items():
        amount = row["price_per_hour"]
        result[venue_id] = {
            "product_id": str(venue_id),
            "product_name": row["name"],
            "price": {"currency": "KRW", "displayed_amount_minor": amount, "billing_unit": "hour"},
            "rental_conditions": {
                "start_at": None,
                "end_at": None,
                "guest_count": None,
                "option_ids": [],
            },
        }
    return result


def accept_events(body: EventBatchCreate, user_id: int | None, is_synthetic: bool) -> dict:
    """허용된 이벤트만 기록한다. 저장 불가능한 허용 이벤트는 400으로 돌려준다."""
    accepted = [item for item in body.events if item.event_name in FE_EVENTS]
    ignored = Counter(item.event_name for item in body.events if item.event_name not in FE_EVENTS)
    product_map = _products(accepted)
    prepared = []
    for item in accepted:
        if item.schema_version != 1 or item.user is None:
            raise invalid_field("events", "schema_version=1 및 user 문맥")
        user = item.user
        if user.session_id != str(body.session_id):
            raise invalid_field("user.session_id", "묶음 session_id와 일치")
        products = (
            [product_map[int(item.products[0].product_id)]]
            if item.event_name in PRODUCT_EVENTS
            else []
        )
        context = {
            "site": item.site.model_dump() if item.site is not None else None,
            "acquisition": item.acquisition.model_dump() if item.acquisition is not None else None,
            "page": item.page.model_dump() if item.page is not None else None,
            "navigation": item.navigation.model_dump(by_alias=True)
            if item.navigation is not None
            else None,
        }
        try:
            build_document(
                event_id=str(uuid4()),
                session_id=str(body.session_id),
                user_id=user_id,
                event_name=item.event_name,
                occurred_at=item.occurred_at,
                anonymous_id=user.anonymous_id,
                session_sequence=user.session_sequence,
                context=context,
                products=products,
                properties=sanitize_payload(item.properties, item.event_name),
                is_synthetic=is_synthetic,
            )
        except (ValueError, TypeError, KeyError):
            raise invalid_field("events", "새 이벤트 필수 문맥과 상품 형식") from None
        prepared.append((item, products, context))

    for item, products, context in prepared:
        token = client_event_context.set(
            ClientEventContext(
                occurred_at=item.occurred_at,
                anonymous_id=item.user.anonymous_id,
                session_sequence=item.user.session_sequence,
                browser_context=context,
            )
        )
        try:
            log_event(
                str(body.session_id),
                user_id,
                item.event_name,
                payload=item.properties,
                is_synthetic=is_synthetic,
                products=products,
            )
        finally:
            client_event_context.reset(token)
    if ignored:
        logging.getLogger("spacecube.app").warning(
            "허용 목록에 없는 프론트 이벤트 제외", extra={"count": sum(ignored.values())}
        )
    require_event_file()
    return {
        "accepted": len(prepared),
        "ignored": [{"event_type": name, "count": count} for name, count in ignored.items()],
    }
