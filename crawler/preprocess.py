"""F-61 추출 속성을 seed 표와 API 계약에 맞춘다."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from crawler.spacecloud_crawler import SpaceInfo
from db.loaders.load_seed import resolve

ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "db" / "seed"
CATEGORY_PRIORITY = ("cafe", "lectureroom", "studyroom", "studio", "partyroom")
CATEGORY_NAMES = {
    "studyroom": "스터디룸",
    "studio": "스튜디오",
    "cafe": "카페",
    "lectureroom": "강의실",
    "partyroom": "파티룸",
}
ART_IMAGES = {
    "studyroom": ["art:group-0", "art:group-1", "art:seminar-0"],
    "studio": ["art:studio-0", "art:studio-1", "art:meeting-0"],
    "cafe": ["art:lounge-0", "art:lounge-1", "art:duo-0"],
    "lectureroom": ["art:seminar-0", "art:seminar-1", "art:meeting-0"],
    "partyroom": ["art:partyroom-0", "art:partyroom-1", "art:lounge-0"],
}
FACILITY_ALIASES = {
    "와이파이": "인터넷/WIFI",
    "wifi": "인터넷/WIFI",
    "wi-fi": "인터넷/WIFI",
    "빔프로젝터": "TV/프로젝터",
    "프로젝터": "TV/프로젝터",
    "마이크": "음향/마이크",
    "화이트보드": "화이트보드",
    "주차": "주차",
    "노트북": "PC/노트북",
}


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


@dataclass
class SeedMaps:
    categories: dict[tuple[str, str], str]
    sido_alias: dict[str, str]
    sigungu_alias: dict[tuple[str, str], str]
    legal_dong: dict[tuple[str, str, str], tuple[str, str] | None]
    legal_dong_city_aliases: set[str]
    regions: set[tuple[str, str]]
    facilities: set[str]
    # (시·도, 법정동) → 시·군·구들, (시 이름, 법정동) → (시·도, 시·군·구)들. db/seed/dong_sigungu.csv(#10)
    dong_index: dict[tuple[str, str], set[str]] = field(default_factory=dict)
    city_index: dict[tuple[str, str], set[tuple[str, str]]] = field(default_factory=dict)

    @classmethod
    def load(cls, seed_dir: Path = SEED_DIR) -> SeedMaps:
        legal_dong_rows = _csv_rows(seed_dir / "legal_dong.csv")
        return cls(
            categories={
                (row["source_site"], row["source_type"]): row["category_code"]
                for row in _csv_rows(seed_dir / "category_map.csv")
            },
            sido_alias={
                row["alias"]: row["sido"] for row in _csv_rows(seed_dir / "sido_alias.csv")
            },
            sigungu_alias={
                (row["sido"], row["alias"]): row["sigungu"]
                for row in _csv_rows(seed_dir / "sigungu_alias.csv")
            },
            legal_dong={
                (row["scope"], row["alias"], row["locality"]): (
                    (row["sido"], row["sigungu"]) if row["status"] == "unique" else None
                )
                for row in legal_dong_rows
            },
            legal_dong_city_aliases={
                row["alias"] for row in legal_dong_rows if row["scope"] == "city"
            },
            regions={(row["sido"], row["sigungu"]) for row in _csv_rows(seed_dir / "regions.csv")},
            facilities={row["name"] for row in _csv_rows(seed_dir / "facilities.csv")},
            **_dong_indexes(seed_dir / "dong_sigungu.csv"),
        )


def _dong_indexes(path: Path) -> dict:
    dong_index: dict[tuple[str, str], set[str]] = {}
    city_index: dict[tuple[str, str], set[tuple[str, str]]] = {}
    if not path.exists():
        return {"dong_index": dong_index, "city_index": city_index}
    for row in _csv_rows(path):
        sido, sigungu, dong = row["sido"], row["sigungu"], row["dong"]
        dong_index.setdefault((sido, dong), set()).add(sigungu)
        city = re.sub(r"(시|군)$", "", sigungu)
        if city != sigungu:
            city_index.setdefault((city, dong), set()).add((sido, sigungu))
    return {"dong_index": dong_index, "city_index": city_index}


def resolve_region(address: str, maps: SeedMaps) -> tuple[tuple[str, str] | None, str]:
    """'서울특별시 마포구'는 기존 resolve()로, '서울 봉천동'·'천안 두정동'(시·도 또는 시 + 법정동)은
    법정동 대응표로 푼다. 같은 동 이름이 여러 시·군·구에 있으면 고르지 않고 제외한다."""
    region, reason = resolve(address, maps.sido_alias, maps.sigungu_alias, maps.regions)
    if region is not None or reason.startswith("나뉜 옛 구"):
        return region, reason
    parts = address.split()
    if len(parts) != 2 or not re.search(r"(동|가|읍|면|로|리)$", parts[1]):
        return region, reason
    head, dong = parts
    sido = maps.sido_alias.get(head)
    if sido is not None:
        found = {(sido, sigungu) for sigungu in maps.dong_index.get((sido, dong), ())}
    else:
        found = set(maps.city_index.get((head, dong), ()))
    found = {item for item in found if item in maps.regions}
    if len(found) == 1:
        return found.pop(), ""
    return None, "동 이름 겹침" if found else "동 대응 없음"


def _business_hours(value: str | None) -> tuple[int, int] | None:
    if not value:
        return 9, 23
    match = re.search(
        r"(\d{1,2})(?::(\d{2}))?\s*[~\-–]\s*(\d{1,2})(?::(\d{2}))?",
        value,
    )
    if not match:
        return None
    start_h, start_m, end_h, end_m = (
        int(match.group(1)),
        int(match.group(2) or 0),
        int(match.group(3)),
        int(match.group(4) or 0),
    )
    if start_h > 24 or end_h > 24 or start_m > 59 or end_m > 59:
        return None
    start = max(9, start_h + (start_m > 0))
    end = min(23, end_h)
    return (start, end) if end > start else None


def _facilities(names: list[str], allowed: set[str]) -> list[str]:
    found = set()
    for name in names:
        if name in allowed:
            found.add(name)
            continue
        lower = name.lower()
        for needle, mapped in FACILITY_ALIASES.items():
            if needle in lower and mapped in allowed:
                found.add(mapped)
    return sorted(found)


def map_space(site: str, space: SpaceInfo, maps: SeedMaps) -> tuple[dict | None, str | None]:
    """매핑하지 못한 값의 이유를 반환하고, 사이트 원문은 반환하지 않는다."""
    categories = {maps.categories.get((site, source_type)) for source_type in space.space_types}
    categories.discard(None)
    categories.discard("")
    category = next((code for code in CATEGORY_PRIORITY if code in categories), None)
    if category is None:
        return None, "대상 유형 없음"
    prices = [
        price
        for price in space.prices
        if price.get("unit") == "시간"
        and not price.get("per_person")
        and isinstance(price.get("amount"), int)
        and 0 < price["amount"] <= 2147483647
    ]
    if not prices:
        return None, "고정 시간당 가격 없음"
    prices = [
        price for price in prices if 1 <= (price.get("min_hours") or space.min_hours or 1) <= 4
    ]
    if not prices:
        return None, "최소 예약시간 범위 밖"
    if site == "shareit":
        prices = [
            price
            for price in prices
            if isinstance(price.get("capacity_max"), int) and 1 <= price["capacity_max"] <= 32767
        ]
        if not prices:
            return None, "수용인원 이상"
    chosen_price = min(prices, key=lambda price: price["amount"])
    capacity = (
        chosen_price.get("capacity_max")
        if site == "shareit"
        else chosen_price.get("capacity_max") or space.max_capacity
    )
    if not capacity or not 1 <= capacity <= 32767:
        return None, "수용인원 이상"
    min_hours = chosen_price.get("min_hours") or space.min_hours or 1
    address = space.address_region or ""
    region, reason = resolve(
        address,
        maps.sido_alias,
        maps.sigungu_alias,
        maps.regions,
        maps.legal_dong,
        maps.legal_dong_city_aliases,
    )
    if region is None:
        if reason in {"동 이름 겹침", "동 대응 없음"}:
            return None, reason
        # resolve()의 상세 이유에는 입력 주소 일부가 들어가므로 고정 문구만 저장한다.
        if reason == "동 이름 겹침":
            return None, "동 이름 겹침"
        if reason == "동 대응 없음":
            return None, "동 대응 없음"
        if reason.startswith("나뉜 옛 구"):
            return None, "나뉜 옛 구"
        if reason.startswith("모르는 시·도"):
            return None, "모르는 시·도"
        if reason.startswith("regions에 없음"):
            return None, "지원하지 않는 시·군·구"
        return None, "주소가 시·도 하나뿐"
    hours = _business_hours(space.open_hours)
    if hours is None:
        return None, "영업시간 이상"
    sido, sigungu = region
    return {
        "category": category,
        "sido": sido,
        "sigungu": sigungu,
        "capacity_max": capacity,
        "price_per_hour": chosen_price["amount"],
        "min_hours": min_hours,
        "open_hour": hours[0],
        "close_hour": hours[1],
        "facilities": _facilities(space.facilities, maps.facilities),
    }, None


def venue_payload(site: str, source_id: str, mapped: dict) -> dict:
    category = mapped["category"]
    title = CATEGORY_NAMES[category]
    return {
        "source_site": site,
        "source_id": source_id,
        "name": f"{mapped['sigungu']} {title} {source_id}호",
        "category_code": category,
        "sido": mapped["sido"],
        "sigungu": mapped["sigungu"],
        "capacity_max": mapped["capacity_max"],
        "price_per_hour": mapped["price_per_hour"],
        "min_hours": mapped["min_hours"],
        "open_hour": mapped["open_hour"],
        "close_hour": mapped["close_hour"],
        "description": f"{mapped['sigungu']}의 {title} 시연용 공간입니다.",
        "notice": "실제 업체의 예약 상품이 아닌 시연용 공간입니다.",
        "facilities": mapped["facilities"],
        "images": ART_IMAGES[category],
    }
