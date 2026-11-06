"""F-60 새 MongoDB events 문서의 검증·개인정보 제거·조립."""

import re
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

from app.core.clock import get_event_time
from app.core.config import get_settings

FE_EVENTS = frozenset(
    {
        "page_view",
        "product_impression",
        "product_view",
        "product_section_click",
        "search_submit",
        "availability_view",
        "rental_slot_select",
        "reservation_start",
        "reservation_cancel_attempt",
        "review_create",
        "login",
        "signup",
    }
)
SERVER_EVENTS = frozenset(
    {
        "reservation_complete",
        "reservation_conflict",
        "reservation_cancel_complete",
    }
)
PRODUCT_EVENTS = (FE_EVENTS | SERVER_EVENTS) - {"page_view", "search_submit", "login", "signup"}
EVENT_DOCUMENT_FIELDS = frozenset(
    {
        "event_id",
        "schema_version",
        "event_name",
        "occurred_at",
        "received_at",
        "is_synthetic",
        "server",
        "user",
        "site",
        "acquisition",
        "page",
        "navigation",
        "products",
        "properties",
    }
)
_PLATFORMS = {"desktop_web", "mobile_web", "ios", "android"}
_NAVIGATION = {"external", "internal", "direct", "reload", "history"}
_BILLING = {"hour", "day", "night", "session", "total"}
_PAGE_TYPES = {
    "home",
    "search_results",
    "product_detail",
    "checkout",
    "my_page",
    "auth",
    "reviews",
    "other",
}
_CATEGORIES = {"studyroom", "studio", "cafe", "lectureroom", "partyroom"}
_SORTS = {"default", "popular", "price", "rating", "recent", "high", "low"}


def _plain(value, *, limit=255):
    return (
        isinstance(value, str)
        and 0 < len(value) <= limit
        and bool(re.fullmatch(r"[A-Za-z0-9_.:-]+", value))
    )


def _url(value):
    if not isinstance(value, str):
        return None
    parts = urlsplit(value)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
    ):
        return None
    if not re.fullmatch(r"[A-Za-z0-9.:-]+", parts.netloc):
        return None
    # path에도 이름·토큰을 넣을 수 있으므로 알려진 화면 경로만 보존한다.
    path = parts.path or "/"
    if not re.fullmatch(
        r"/(?:search|login|signup|me|reviews|reserve)?/?", path
    ) and not re.fullmatch(r"/venues/[0-9]+/?", path):
        path = "/"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _page(value):
    if not isinstance(value, dict):
        raise ValueError("page")
    url = _url(value.get("url"))
    page_type = value.get("page_type")
    if not url or not _plain(value.get("page_view_id")) or page_type not in _PAGE_TYPES:
        raise ValueError("page")
    # title은 자유 문자열이므로 화면 종류의 고정 이름으로 대체한다.
    return {
        "page_view_id": value["page_view_id"],
        "page_type": page_type,
        "url": url,
        "path": urlsplit(url).path or "/",
        "title": page_type,
    }


def _navigation_page(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("navigation")
    url = _url(value.get("url"))
    if not url:
        raise ValueError("navigation")
    return {
        "page_view_id": value.get("page_view_id") if _plain(value.get("page_view_id")) else None,
        "site_id": value.get("site_id") if value.get("site_id") == "main" else None,
        "url": url,
        "path": urlsplit(url).path or "/",
    }


def _context(event_name, context):
    if event_name in SERVER_EVENTS and not context:
        return None, None, None, None
    if not isinstance(context, dict):
        raise ValueError("브라우저 문맥")
    site, acquisition = context.get("site"), context.get("acquisition")
    navigation = context.get("navigation")
    if (
        not isinstance(site, dict)
        or site.get("site_id") != "main"
        or site.get("platform") not in _PLATFORMS
    ):
        raise ValueError("site")
    hostname = site.get("hostname")
    if not isinstance(hostname, str) or not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", hostname):
        raise ValueError("hostname")
    if not isinstance(acquisition, dict) or not _url(acquisition.get("landing_url")):
        raise ValueError("acquisition")
    if not isinstance(navigation, dict) or navigation.get("navigation_type") not in _NAVIGATION:
        raise ValueError("navigation")
    to = _navigation_page(navigation.get("to"))
    if to is None:
        raise ValueError("navigation.to")
    referrer = acquisition.get("referrer_url")
    return (
        {"site_id": "main", "hostname": hostname, "platform": site["platform"]},
        {
            "landing_url": _url(acquisition["landing_url"]),
            "referrer_url": _url(referrer) if referrer else None,
            # UTM 허용 목록은 미확정. 개인정보를 저장하지 않도록 우선 제외한다.
            "utm_source": None,
            "utm_medium": None,
            "utm_campaign": None,
        },
        _page(context.get("page")),
        {
            "from": _navigation_page(navigation.get("from")),
            "to": to,
            "navigation_type": navigation["navigation_type"],
        },
    )


def _time(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("datetime")
    return value.astimezone(UTC)


def validate_products(event_name, products):
    if (
        not isinstance(products, list)
        or (event_name in PRODUCT_EVENTS and not products)
        or (event_name not in PRODUCT_EVENTS and products)
    ):
        raise ValueError("products")
    result = []
    for item in products:
        if not isinstance(item, dict) or not _plain(item.get("product_id")):
            raise ValueError("product_id")
        name, price, rental = (
            item.get("product_name"),
            item.get("price"),
            item.get("rental_conditions"),
        )
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError("product_name")
        if not isinstance(price, dict) or not isinstance(rental, dict):
            raise ValueError("product")
        amount = price.get("displayed_amount_minor")
        if (
            price.get("currency") != "KRW"
            or type(amount) is not int
            or amount < 0
            or price.get("billing_unit") not in _BILLING
        ):
            raise ValueError("price")
        start, end = _time(rental.get("start_at")), _time(rental.get("end_at"))
        guests = rental.get("guest_count")
        options = rental.get("option_ids")
        if (
            (start is None) != (end is None)
            or (start and end <= start)
            or (guests is not None and (type(guests) is not int or guests < 1))
            or not isinstance(options, list)
            or any(not _plain(option) for option in options)
        ):
            raise ValueError("rental_conditions")
        # 표시 문자열은 금액에서 직접 만든다. 외부 자유 문자열은 저장하지 않는다.
        text = f"{amount:,}원 / 시간" if price["billing_unit"] == "hour" else f"{amount:,}원"
        result.append(
            {
                "product_id": item["product_id"],
                "product_name": name,
                "price": {
                    "currency": "KRW",
                    "displayed_amount_minor": amount,
                    "displayed_text": text,
                    "billing_unit": price["billing_unit"],
                },
                "rental_conditions": {
                    "start_at": start,
                    "end_at": end,
                    "timezone": "Asia/Seoul",
                    "guest_count": guests,
                    "option_ids": options,
                },
            }
        )
    return result


def build_document(
    *,
    event_id,
    session_id,
    user_id,
    event_name,
    occurred_at=None,
    anonymous_id=None,
    session_sequence=None,
    context=None,
    products=None,
    properties=None,
    is_synthetic=False,
):
    if event_name not in FE_EVENTS | SERVER_EVENTS:
        raise ValueError("event_name")
    if event_name in FE_EVENTS and (
        not _plain(anonymous_id) or type(session_sequence) is not int or session_sequence < 1
    ):
        raise ValueError("user")
    if not _plain(session_id):
        raise ValueError("session_id")
    site, acquisition, page, navigation = _context(event_name, context)
    received = get_event_time().astimezone(UTC)
    return {
        "event_id": event_id,
        "schema_version": 1,
        "event_name": event_name,
        "occurred_at": _time(occurred_at) or received,
        "received_at": received,
        "is_synthetic": bool(is_synthetic),
        "server": get_settings().server_name,
        "user": {
            "user_id": str(user_id) if user_id is not None else None,
            "anonymous_id": anonymous_id if _plain(anonymous_id) else None,
            "session_id": session_id,
            "session_sequence": session_sequence
            if type(session_sequence) is int and session_sequence >= 1
            else None,
        },
        "site": site,
        "acquisition": acquisition,
        "page": page,
        "navigation": navigation,
        "products": validate_products(event_name, products or []),
        "properties": properties or {},
    }
