"""F-61 쉐어잇 상세의 __NEXT_DATA__에서 허용한 속성만 추출한다."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from bs4 import BeautifulSoup

from crawler.spacecloud_crawler import SpaceInfo


def _objects(value: Any) -> Iterator[dict]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _objects(child)


def _first_dict_with(data: dict, key: str) -> dict | None:
    return next((part for part in _objects(data) if isinstance(part.get(key), dict)), None)


def _first_list_with(data: dict, key: str) -> list | None:
    return next((part[key] for part in _objects(data) if isinstance(part.get(key), list)), None)


def _type_name(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        for key in ("type", "name", "typeName"):
            if isinstance(value.get(key), str):
                return value[key].strip() or None
    return None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def parse_shareit(source_id: str | int, html: str) -> SpaceInfo:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return SpaceInfo(str(source_id), [], None, None, [], [], None, None)
    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        return SpaceInfo(str(source_id), [], None, None, [], [], None, None)
    if not isinstance(data, dict):
        return SpaceInfo(str(source_id), [], None, None, [], [], None, None)

    holder = _first_dict_with(data, "spaceMetaData")
    metadata = holder["spaceMetaData"] if holder else {}
    resource = metadata.get("resource") or {}
    if not isinstance(resource, dict):
        resource = {}
    raw_types = resource.get("mainZone3Types") or resource.get("zone3Types") or []
    if not isinstance(raw_types, list):
        raw_types = []
    space_types = list(dict.fromkeys(name for raw in raw_types if (name := _type_name(raw))))

    legal = resource.get("legalAddress") or {}
    if not isinstance(legal, dict):
        legal = {}
    place_holder = _first_dict_with(data, "placeInfo")
    place = place_holder["placeInfo"] if place_holder else {}
    address = legal.get("name") or place.get("address") or ""
    region = " ".join(str(address).split()[:2]) or None

    goods = _first_list_with(data, "goods") or []
    capacities, prices, min_hours = [], [], []
    for good in goods:
        if not isinstance(good, dict):
            continue
        sale = good.get("saleInfo") or {}
        people = good.get("personnelConfig") or {}
        if not isinstance(sale, dict) or not isinstance(people, dict):
            continue
        capacity = _positive_int(people.get("maximumNumberPersonnel"))
        if capacity:
            capacities.append(capacity)
        # ruleType 1·2의 단위가 확정되지 않았다. 명시적 60분 상품만 시간당 가격으로 쓴다.
        if _positive_int(sale.get("timeUnitMinute")) != 60:
            continue
        amount = _positive_int(sale.get("price"))
        minutes = _positive_int(sale.get("minimumSalesTimeRangeMinute"))
        if sale.get("minimumSalesTimeRangeMinute") is not None and (
            minutes is None or minutes % 60 != 0
        ):
            continue
        if amount:
            prices.append(
                {
                    "amount": amount,
                    "unit": "시간",
                    "per_person": False,
                    "min_hours": minutes // 60 if minutes else 1,
                    "capacity_max": capacity,
                }
            )
        if minutes:
            min_hours.append(minutes // 60)

    return SpaceInfo(
        source_id=str(source_id),
        space_types=space_types,
        max_capacity=max(capacities, default=None),
        min_hours=min(min_hours, default=None),
        facilities=[],
        prices=prices,
        open_hours=None,
        address_region=region,
    )
