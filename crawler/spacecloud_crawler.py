"""F-61 스페이스클라우드 속성 파서와 두 수집원이 공유하는 요청 클라이언트."""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.robotparser
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

SPACE_BASE_URL = "https://www.spacecloud.kr"
SHAREIT_BASE_URL = "https://shareit.kr"
USER_AGENT = "PRO1-SpaceCubeCrawler/0.2 (class project; weekly; 3s delay)"
REQUEST_DELAY_SEC = 3.0
MAX_DETAIL_PER_RUN = 20
ALLOWED_HOSTS = {"www.spacecloud.kr", "spacecloud.kr", "shareit.kr", "www.shareit.kr"}


@dataclass
class SpaceInfo:
    source_id: str
    space_types: list[str]
    max_capacity: int | None
    min_hours: int | None
    facilities: list[str]
    prices: list[dict]
    open_hours: str | None
    address_region: str | None
    area_m2: float | None = None
    rating: float | None = None
    review_count: int | None = None


class PoliteClient:
    """요청마다 간격을 지키고 요청 대상 사이트의 robots.txt를 확인한다."""

    def __init__(self, http: httpx.Client | None = None, delay: float = REQUEST_DELAY_SEC):
        self.http = http or httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=False
        )
        self.delay = delay
        self.robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last_request: float | None = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.http.close()

    def _request(self, url: str) -> httpx.Response:
        if self._last_request is not None:
            wait = self.delay - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
        self._last_request = time.monotonic()
        response = self.http.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=False)
        if response.status_code not in {301, 302, 303, 307, 308}:
            response.raise_for_status()
        return response

    def get(self, url: str) -> str:
        source_host = urlsplit(url).hostname
        source_domain = source_host.removeprefix("www.") if source_host else ""
        for _ in range(6):
            parts = urlsplit(url)
            if (
                parts.scheme != "https"
                or parts.hostname not in ALLOWED_HOSTS
                or parts.netloc != parts.hostname
            ):
                raise PermissionError("허용하지 않은 수집 사이트")
            if parts.hostname.removeprefix("www.") != source_domain:
                raise PermissionError("다른 수집 사이트로 이동하는 응답")
            origin = f"{parts.scheme}://{parts.netloc}"
            if origin not in self.robots:
                robots_response = self._request(f"{origin}/robots.txt")
                if robots_response.status_code != 200:
                    raise PermissionError("robots.txt 확인 실패")
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(robots_response.text.splitlines())
                self.robots[origin] = parser
                self.delay = max(self.delay, parser.crawl_delay(USER_AGENT) or 0)
            if not self.robots[origin].can_fetch(USER_AGENT, url):
                raise PermissionError(f"robots.txt 차단: {parts.path}")
            response = self._request(url)
            if response.status_code not in {301, 302, 303, 307, 308}:
                return response.text
            location = response.headers.get("location")
            if not location:
                raise ValueError("이동할 주소가 없는 응답")
            url = urljoin(url, location)
        raise ValueError("리디렉션 5회 초과")


def sitemap_links(xml: str, site: str) -> tuple[list[str], list[str]]:
    """사이트맵 색인 주소와 해당 사이트의 공간 ID만 반환한다."""
    if len(xml) > 20_000_000 or re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", xml, re.I):
        raise ValueError("사이트맵 크기 또는 XML 선언이 허용 범위를 벗어났습니다.")
    root = ElementTree.fromstring(xml)  # noqa: S314 크기 제한과 DTD·ENTITY 차단 뒤 파싱
    children, ids = [], []
    hosts = (
        {"shareit.kr", "www.shareit.kr"}
        if site == "shareit"
        else {"www.spacecloud.kr", "spacecloud.kr"}
    )
    prefix = "venue" if site == "shareit" else "space"
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] != "loc" or not node.text:
            continue
        url = node.text.strip()
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.hostname not in hosts or parts.netloc != parts.hostname:
            continue
        match = re.fullmatch(rf"/{prefix}/(\d+)/?", parts.path)
        if match:
            ids.append(match.group(1))
        elif parts.path.endswith(".xml"):
            children.append(url)
    return children, sorted(set(ids), key=int)


def fetch_sitemap_ids(client: PoliteClient, site: str) -> list[str]:
    base = SHAREIT_BASE_URL if site == "shareit" else SPACE_BASE_URL
    pending = [f"{base}/sitemap.xml"]
    visited, ids = set(), set()
    while pending:
        url = pending.pop(0)
        if url in visited:
            continue
        if len(visited) >= 100:
            raise ValueError("사이트맵 100개 초과")
        visited.add(url)
        children, found = sitemap_links(client.get(url), site)
        ids.update(found)
        pending.extend(child for child in children if child not in visited)
    if not ids:
        raise ValueError(f"{site} 사이트맵에 공간 상세 ID가 없습니다.")
    return sorted(ids, key=int)


def _first_int(text: str, pattern: str) -> int | None:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else None


def _optional_float(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_int(value) -> int | None:
    try:
        return int(str(value).replace(",", "")) if value is not None else None
    except (TypeError, ValueError):
        return None


def parse_space(source_id: str | int, html: str) -> SpaceInfo:
    """허용한 속성만 추출한다. 업체 이름과 원문 소개는 보존하지 않는다."""
    soup = BeautifulSoup(html, "html.parser")
    business = {}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            graph = data.get("@graph")
            candidates = [data, *(graph if isinstance(graph, list) else [])]
            business = next(
                (
                    item
                    for item in candidates
                    if isinstance(item, dict) and item.get("@type") == "LocalBusiness"
                ),
                {},
            )
            if business:
                break
    details = {}
    for li in soup.select("ul.list_detail li"):
        title = li.select_one("span.tit")
        if title:
            label = title.get_text(strip=True)
            details[label] = li.get_text(" ", strip=True).removeprefix(label).strip()
    capacity = details.get("수용인원", "")
    area = re.search(r"([\d.]+)\s*㎡", details.get("공간면적", ""))
    prices = []
    for li in soup.select(".reserv_list li"):
        match = re.search(
            r"₩\s*([\d,]+)\s*/\s*(시간|패키지)\s*(\(인\))?",
            li.get_text(" ", strip=True),
        )
        if match:
            prices.append(
                {
                    "amount": int(match.group(1).replace(",", "")),
                    "unit": match.group(2),
                    "per_person": bool(match.group(3)),
                }
            )
    hours = soup.select_one(".officehours li")
    address = business.get("address") or {}
    if not isinstance(address, dict):
        address = {}
    street = address.get("streetAddress") or ""
    if not isinstance(street, str):
        street = ""
    if not street.strip():
        # 11-07(#10): streetAddress가 빠지고 addressRegion(시·도 또는 시 이름)+addressLocality(법정동)만 온다.
        # 업체명·번지는 받지 않는다. 시·군·구는 전처리에서 법정동 대응표로 구한다.
        region = address.get("addressRegion")
        locality = address.get("addressLocality")
        if isinstance(region, str) and isinstance(locality, str):
            street = f"{region.strip()} {locality.strip()}"
    rating = business.get("aggregateRating") or {}
    if not isinstance(rating, dict):
        rating = {}
    return SpaceInfo(
        source_id=str(source_id),
        space_types=details.get("공간유형", "").split(),
        max_capacity=_first_int(capacity, r"최대\s*(\d+)"),
        min_hours=_first_int(details.get("예약시간", ""), r"최소\s*(\d+)"),
        facilities=[li.get_text("", strip=True) for li in soup.select("ul.facility_list li")],
        prices=prices,
        open_hours=(
            hours.get_text(" ", strip=True).removeprefix("영업시간").strip() if hours else None
        ),
        address_region=" ".join(street.split()[:2]) or None,
        area_m2=float(area.group(1)) if area else None,
        rating=_optional_float(rating.get("ratingValue")),
        review_count=_optional_int(rating.get("reviewCount")),
    )


def sanitized_dict(space: SpaceInfo) -> dict:
    """표본 파일·출력에도 허용한 속성만 남긴다."""
    data = asdict(space)
    # 시설 자유 문구는 매핑 단계에서만 사용한다. 저장 시에는 허용 시설명으로 대체한다.
    data["facilities"] = []
    hours = re.search(
        r"\d{1,2}(?::\d{2})?\s*[~\-–]\s*\d{1,2}(?::\d{2})?",
        space.open_hours or "",
    )
    data["open_hours"] = hours.group(0) if hours else None
    region = (space.address_region or "").split()[:2]
    data["address_region"] = (
        " ".join(region)
        if len(region) == 2 and all(re.fullmatch(r"[가-힣0-9]{2,20}", part) for part in region)
        else None
    )
    return data


def main() -> None:
    """기존 fetch/baseline/diff 명령을 새 실행기로 전달한다."""
    if len(sys.argv) < 2 or sys.argv[1] not in {"fetch", "baseline", "diff"}:
        raise SystemExit("사용법: spacecloud_crawler.py fetch <id> | baseline | diff")
    command = sys.argv[1]
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from crawler.crawl_venues import main as run_main

    sys.argv = [
        sys.argv[0],
        "run" if command == "diff" else command,
        "--site",
        "spacecloud",
        *(["--mode", "weekly"] if command == "diff" else []),
        *sys.argv[2:],
    ]
    run_main()


if __name__ == "__main__":
    main()
