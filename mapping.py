"""Turn allowed crawler attributes into the F-61 venue request."""

from typing import Any


SIDO_ALIASES = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구",
    "인천광역시": "인천", "광주광역시": "전남광주통합특별시",
    "광주": "전남광주통합특별시", "전라남도": "전남광주통합특별시",
    "전남": "전남광주통합특별시", "대전광역시": "대전",
    "울산광역시": "울산", "세종특별자치시": "세종",
    "세종시": "세종", "경기도": "경기", "강원특별자치도": "강원",
    "강원도": "강원", "충청북도": "충북", "충청남도": "충남",
    "전라북도": "전북", "전북특별자치도": "전북",
    "경상북도": "경북", "경상남도": "경남",
    "제주특별자치도": "제주", "제주도": "제주",
}
VALID_SIDO = {
    "서울", "부산", "대구", "인천", "전남광주통합특별시", "대전",
    "울산", "세종", "경기", "강원", "충북", "충남", "전북",
    "경북", "경남", "제주",
}
CATEGORY_RULES = (
    ("cafe", "카페", ("카페",)),
    ("lectureroom", "강의실", ("강의실", "세미나실", "강당", "컨퍼런스")),
    ("studyroom", "스터디룸", ("스터디룸", "회의실")),
    ("studio", "스튜디오", ("촬영", "스튜디오", "호리존")),
    ("partyroom", "파티룸", ("파티룸", "공유주방")),
)


def make_venue_payload(
    record: dict[str, Any], source_site: str = "shareit"
) -> tuple[dict[str, Any] | None, str | None]:
    if record.get("status") != "ok":
        return None, "no_detail"

    types = record.get("space_types") or []
    category = next(
        ((code, label) for code, label, words in CATEGORY_RULES
         if any(word in source_type for source_type in types for word in words)),
        None,
    )
    if category is None:
        return None, "unsupported_category"

    region_parts = (record.get("extracted", {}).get("address_region") or "").split()
    if len(region_parts) < 2:
        return None, "unknown_region"
    sido = SIDO_ALIASES.get(region_parts[0], region_parts[0])
    sigungu = region_parts[1]
    if sido not in VALID_SIDO:
        return None, "unknown_region"
    if sido == "세종":
        sigungu = "세종시"
    elif sido == "인천" and sigungu in {"중구", "서구"}:
        return None, "ambiguous_region"
    elif sido == "인천" and sigungu == "동구":
        sigungu = "제물포구"

    extracted = record["extracted"]
    capacity = extracted.get("max_capacity")
    if not isinstance(capacity, int) or not 1 <= capacity <= 32767:
        return None, "invalid_capacity"
    min_hours = extracted.get("min_hours")
    if not isinstance(min_hours, int) or not 1 <= min_hours <= 4:
        return None, "invalid_min_hours"

    hourly_prices = []
    for item in extracted.get("prices") or []:
        amount, unit = item.get("amount"), item.get("unit_minutes")
        if item.get("rule_type") == 1 and isinstance(amount, int) and amount > 0 \
                and isinstance(unit, int) and unit > 0:
            hourly_prices.append(round(amount * 60 / unit))
    hourly_prices = [price for price in hourly_prices if 0 < price <= 2147483647]
    if not hourly_prices:
        return None, "unsupported_price"

    code, label = category
    mapped = {
        "category_code": code,
        "sido": sido,
        "sigungu": sigungu,
        "capacity_max": capacity,
        "price_per_hour": min(hourly_prices),
        "min_hours": min_hours,
        "open_hour": 9,
        "close_hour": 23,
        "facilities": [],
    }
    payload = {
        "source_site": source_site,
        "source_id": str(record["source_id"]),
        "name": f"{sigungu} {label} {record['source_id']}",
        **mapped,
        "description": f"{label} 시연용 공간입니다.",
        "notice": "시연용 공간입니다.",
        "images": ["art:group-0"],
    }
    record["mapped"] = mapped
    return payload, None
