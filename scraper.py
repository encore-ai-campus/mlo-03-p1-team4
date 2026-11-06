"""Polite site requests and Shareit listing/detail collection."""

import json
import re
import time
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from playwright.sync_api import APIRequestContext


SPACE_API_URL = "https://shareit-resource.shareit.kr/spaces"
SPACES_PER_RUN = 15
MAX_DETAIL_PER_RUN = 20
REQUEST_DELAY_SEC = 3.0
USER_AGENT = "PRO1-StudyroomBot/0.1 (bootcamp class project; weekly, 3s delay)"


class PoliteClient:
    def __init__(self, request: APIRequestContext):
        self.request = request
        self.robots: dict[str, RobotFileParser] = {}
        self.last_request = 0.0

    def _wait(self) -> None:
        delay = REQUEST_DELAY_SEC - (time.monotonic() - self.last_request)
        if delay > 0:
            time.sleep(delay)
        self.last_request = time.monotonic()

    def get(self, url: str, *, params: dict[str, Any] | None = None):
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self.robots:
            self._wait()
            robots_response = self.request.get(f"{origin}/robots.txt", timeout=30_000)
            parser = RobotFileParser()
            parser.parse(robots_response.text().splitlines() if robots_response.ok else [])
            self.robots[origin] = parser
        if not self.robots[origin].can_fetch(USER_AGENT, url):
            raise PermissionError(f"robots.txt disallows {url}")
        self._wait()
        response = self.request.get(url, params=params, timeout=60_000)
        if not response.ok:
            raise RuntimeError(f"Source returned HTTP {response.status} for {url}")
        return response


def search_spaces(client: PoliteClient, page_number: int = 1) -> list[str]:
    if page_number < 1:
        raise ValueError("page_number must be 1 or greater")
    params = {
        "keyword": "", "eventTypes": "", "equipments": "", "minPrice": 0,
        "maxPrice": -1, "discount": 0, "page": page_number,
        "sort": "popularity", "isSchool": "false", "work": "true",
        "life": "false", "size": SPACES_PER_RUN, "type": "search",
    }
    payload = client.get(SPACE_API_URL, params=params).json()
    resources = payload.get("content", {}).get("resources", [])
    if not isinstance(resources, list):
        raise RuntimeError("Shareit search response has no resources list")
    return [str(item["seq"]) for item in resources[:SPACES_PER_RUN] if item.get("seq") is not None]


def crawl_space_detail(client: PoliteClient, source_id: str) -> dict[str, Any]:
    html = client.get(f"https://shareit.kr/venue/{source_id}").text()
    script = re.search(
        r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.S
    )
    if not script:
        return {"source_id": source_id, "status": "no_detail", "space_types": [], "extracted": {}}

    page = json.loads(script.group(1)).get("props", {}).get("pageProps", {})
    resource = (page.get("spaceMetaData") or {}).get("resource") or {}
    types = [
        item.get("zone3Type", {}).get("type")
        for item in resource.get("mainZone3Types") or []
        if isinstance(item, dict)
    ]
    prices = []
    capacities = []
    minimum_minutes = []
    for good in page.get("goods") or []:
        sale = good.get("saleInfo") or {}
        personnel = good.get("personnelConfig") or {}
        prices.append({
            "amount": sale.get("price"),
            "rule_type": sale.get("ruleType"),
            "unit_minutes": sale.get("timeUnitMinute"),
        })
        if isinstance(personnel.get("maximumNumberPersonnel"), int):
            capacities.append(personnel["maximumNumberPersonnel"])
        if isinstance(sale.get("minimumSalesTimeRangeMinute"), int):
            minimum_minutes.append(sale["minimumSalesTimeRangeMinute"])

    address = (page.get("placeInfo") or {}).get("address") or ""
    extracted = {
        "max_capacity": max(capacities) if capacities else None,
        "prices": prices,
        "min_hours": (min(minimum_minutes) + 59) // 60 if minimum_minutes else None,
        "address_region": " ".join(address.split()[:2]) or None,
    }
    return {
        "source_id": source_id,
        "status": "ok",
        "space_types": [value for value in types if isinstance(value, str)],
        "extracted": extracted,
    }
