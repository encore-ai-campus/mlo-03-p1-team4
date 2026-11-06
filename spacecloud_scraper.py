"""Collect public Spacecloud venue details from its sitemap and detail pages."""

import re
from typing import Any
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from scraper import PoliteClient, SPACES_PER_RUN


BASE_URL = "https://www.spacecloud.kr"
SPACE_URL = re.compile(r"https://www\.spacecloud\.kr/space/(\d+)/?")
HOURLY_PRICE = re.compile(r"₩\s*([\d,]+)\s*/\s*시간\s*(\(\s*인\s*\))?")


def search_spacecloud_spaces(client: PoliteClient, page_number: int = 1) -> list[str]:
    if page_number < 1:
        raise ValueError("page_number must be 1 or greater")
    sitemap = client.get(f"{BASE_URL}/sitemap.xml").text()
    root = ElementTree.fromstring(sitemap)
    source_ids = set()
    for loc in root.findall(".//{*}loc"):
        match = SPACE_URL.fullmatch((loc.text or "").strip())
        if match:
            source_ids.add(match.group(1))
    if not source_ids:
        raise RuntimeError("Spacecloud sitemap has no space URLs")
    ordered = sorted(source_ids, key=int, reverse=True)
    start = (page_number - 1) * SPACES_PER_RUN
    return ordered[start:start + SPACES_PER_RUN]


def parse_spacecloud_detail(html: str, source_id: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    details: dict[str, str] = {}
    for item in soup.select("ul.list_detail > li"):
        content = item.get_text(" ", strip=True)
        for label in ("공간유형", "공간면적", "예약시간", "수용인원"):
            if content.startswith(label):
                details[label] = content[len(label):].strip()
                break

    if not details:
        return {"source_id": source_id, "status": "no_detail", "space_types": [], "extracted": {}}

    capacity = re.search(r"최대\s*(\d+)\s*명", details.get("수용인원", ""))
    minimum_capacity = re.search(r"최소\s*(\d+)\s*명", details.get("수용인원", ""))
    minimum_hours = re.search(r"최소\s*(\d+)\s*시간", details.get("예약시간", ""))
    area = re.search(r"([\d.]+)\s*㎡", details.get("공간면적", ""))

    prices = []
    for item in soup.select("ul.reserv_list > li"):
        price_element = item.select_one(".align_right")
        if price_element is None:
            continue
        match = HOURLY_PRICE.search(price_element.get_text(" ", strip=True))
        if match and not match.group(2):
            prices.append({"amount": int(match.group(1).replace(",", "")),
                           "rule_type": 1, "unit_minutes": 60})

    address = soup.select_one(".sp_location .sp_address")
    region_parts = address.get_text(" ", strip=True).split() if address else []
    # 공개 위치가 동 단위라면 시군구를 추측하지 않고 지역 매핑에서 제외한다.
    region = " ".join(region_parts[:2]) if len(region_parts) >= 2 and re.search(
        r"(?:시|군|구)$", region_parts[1]
    ) else None

    extracted = {
        "min_capacity": int(minimum_capacity.group(1)) if minimum_capacity else None,
        "max_capacity": int(capacity.group(1)) if capacity else None,
        "min_hours": int(minimum_hours.group(1)) if minimum_hours else None,
        "area_m2": float(area.group(1)) if area else None,
        "prices": prices,
        "facilities": [item.get_text(" ", strip=True)[:100]
                       for item in soup.select("ul.facility_list > li")],
        "open_hours": [item.get_text(" ", strip=True)[:100]
                       for item in soup.select("ul.officehours > li")],
        "address_region": region,
    }
    return {
        "source_id": source_id,
        "status": "ok",
        "space_types": details.get("공간유형", "").split(),
        "extracted": extracted,
    }


def crawl_spacecloud_detail(client: PoliteClient, source_id: str) -> dict[str, Any]:
    html = client.get(f"{BASE_URL}/space/{source_id}").text()
    return parse_spacecloud_detail(html, source_id)
