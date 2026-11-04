"""스페이스클라우드 신규 스터디룸 크롤러 (MVP 시제품).

MVP 범위(docs/MVP_시뮬레이션_크롤링_수치.md):
- 사이트맵의 공간 id를 저장해 두고, 주 1회 다시 받아 새로 생긴 id만 찾는다.
- 새 id의 상세 페이지에서 공간유형·수용인원·시설·가격·영업시간만 뽑는다.
- 스터디룸 + 최대 10명 이하 + 서울인 공간 1개만 가상 신규 룸으로 등록한다.
- 사진·후기 본문·호스트 연락처는 저장하지 않는다.

사용법:
    uv run --with httpx --with beautifulsoup4 python spacecloud_crawler.py baseline
    uv run --with httpx --with beautifulsoup4 python spacecloud_crawler.py diff
    uv run --with httpx --with beautifulsoup4 python spacecloud_crawler.py fetch 53074
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.robotparser
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.spacecloud.kr"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
USER_AGENT = "PRO1-StudyroomBot/0.1 (bootcamp class project; weekly, 3s delay)"

REQUEST_DELAY_SEC = 3.0
MAX_DETAIL_PER_RUN = 20
REGISTER_PER_RUN = 1
MAX_VIRTUAL_ROOMS = 10
MAX_CAPACITY = 10
REGION_PREFIX = "서울"

DATA_DIR = Path(__file__).parent / "data"
SITEMAP_IDS_FILE = DATA_DIR / "sitemap_ids.json"
SPACES_DIR = DATA_DIR / "spaces"
STATE_FILE = DATA_DIR / "virtual_rooms_state.json"
NEW_ROOMS_LOG = DATA_DIR / "new_rooms.jsonl"

# 설계한 MVP 룸 6개. 신규 룸 번호는 층마다 최대 4개씩 이어 붙인다(303, 304, 401 ...).
INITIAL_ROOM_NUMBERS = [101, 102, 201, 202, 301, 302]
ROOMS_PER_FLOOR = 4

# 최대 인원 → 룸 유형 · 시간당 가격 · 이미지 풀(일러스트 종류, 색 변형)
ROOM_TYPES = [
    (2, "1인실", 3000, [("booth", 0), ("booth", 1)]),
    (4, "소형", 6000, [("duo", 0), ("lounge", 0), ("duo", 1), ("lounge", 1)]),
    (8, "중형", 10000, [("group", 0), ("seminar", 0), ("group", 1), ("seminar", 1)]),
    (MAX_CAPACITY, "대형", 20000, [("meeting", 0), ("meeting", 1)]),
]


@dataclass
class SpaceInfo:
    source_id: int
    name: str
    space_types: list[str]
    min_capacity: int | None
    max_capacity: int | None
    min_hours: int | None
    area_m2: float | None
    facilities: list[str]
    prices: list[dict]
    open_hours: str | None
    address_region: str | None
    rating: float | None
    review_count: int | None
    crawled_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class PoliteClient:
    """robots.txt를 지키고 요청 사이에 간격을 두는 HTTP 클라이언트."""

    def __init__(self) -> None:
        self.http = httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True
        )
        self.robots = urllib.robotparser.RobotFileParser()
        self.robots.parse(self.http.get(f"{BASE_URL}/robots.txt").text.splitlines())
        self._last_request = 0.0

    def get(self, url: str) -> str:
        if not self.robots.can_fetch(USER_AGENT, url):
            raise PermissionError(f"robots.txt disallows {url}")
        wait = REQUEST_DELAY_SEC - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()
        resp = self.http.get(url)
        resp.raise_for_status()
        return resp.text


def parse_sitemap_ids(xml: str) -> list[int]:
    return sorted(
        {int(m) for m in re.findall(r"<loc>https://www\.spacecloud\.kr/space/(\d+)</loc>", xml)}
    )


def _first_int(text: str, pattern: str) -> int | None:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


def parse_space(source_id: int, html: str) -> SpaceInfo:
    soup = BeautifulSoup(html, "html.parser")

    business = {}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        if data.get("@type") == "LocalBusiness":
            business = data
            break

    details = {}
    for li in soup.select("ul.list_detail li"):
        tit = li.select_one("span.tit")
        if tit:
            label = tit.get_text(strip=True)
            details[label] = li.get_text(" ", strip=True).removeprefix(label).strip()

    capacity = details.get("수용인원", "")
    area = re.search(r"([\d.]+)\s*㎡", details.get("공간면적", ""))

    prices = []
    for li in soup.select(".reserv_list li"):
        text = li.get_text(" ", strip=True)
        m = re.search(r"₩\s*([\d,]+)\s*/\s*(시간|패키지)\s*(\(인\))?", text)
        if m:
            prices.append(
                {
                    "amount": int(m.group(1).replace(",", "")),
                    "unit": m.group(2),
                    "per_person": bool(m.group(3)),
                }
            )

    hours = soup.select_one(".officehours li")
    street = business.get("address", {}).get("streetAddress", "")
    rating = business.get("aggregateRating", {})

    return SpaceInfo(
        source_id=source_id,
        name=business.get("name") or (soup.title.get_text(strip=True) if soup.title else ""),
        space_types=details.get("공간유형", "").split(),
        min_capacity=_first_int(capacity, r"최소\s*(\d+)"),
        max_capacity=_first_int(capacity, r"최대\s*(\d+)"),
        min_hours=_first_int(details.get("예약시간", ""), r"최소\s*(\d+)"),
        area_m2=float(area.group(1)) if area else None,
        facilities=[li.get_text("", strip=True) for li in soup.select("ul.facility_list li")],
        prices=prices,
        open_hours=hours.get_text(" ", strip=True).removeprefix("영업시간").strip()
        if hours
        else None,
        # 주소는 시·구까지만 남긴다.
        address_region=" ".join(street.split()[:2]) or None,
        rating=float(rating["ratingValue"]) if rating.get("ratingValue") else None,
        review_count=int(rating["reviewCount"]) if rating.get("reviewCount") else None,
    )


def is_target(space: SpaceInfo) -> bool:
    return (
        "스터디룸" in space.space_types
        and space.max_capacity is not None
        and space.max_capacity <= MAX_CAPACITY
        and (space.address_region or "").startswith(REGION_PREFIX)
    )


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def next_room_number(numbers: list[int]) -> int:
    last = max(numbers)
    floor, idx = divmod(last, 100)
    return last + 1 if idx < ROOMS_PER_FLOOR else (floor + 1) * 100 + 1


def to_virtual_room(space: SpaceInfo, state: dict) -> dict:
    """크롤링한 속성으로 가상 신규 룸을 만든다. 이미지는 유형별 풀에서 순서대로 돌려 쓴다."""
    # 인원이 들어가는 첫 유형, 없으면 가장 큰 유형
    _, room_type, price, pool = next(
        (t for t in ROOM_TYPES if space.max_capacity <= t[0]), ROOM_TYPES[-1]
    )
    turn = state["image_turns"].get(room_type, 0)
    kind, tone = pool[turn % len(pool)]
    state["image_turns"][room_type] = turn + 1

    number = next_room_number(state["room_numbers"])
    state["room_numbers"].append(number)
    return {
        "room_no": number,
        "room_type": room_type,
        "capacity": f"{space.min_capacity or 1}–{space.max_capacity}인",
        "price_per_hour": price,
        "facilities": space.facilities,
        "image": {"kind": kind, "tone": tone},
        "is_new": True,
        "opened_at": datetime.now(UTC).date().isoformat(),
        "source": {"site": "spacecloud", "source_id": space.source_id},
    }


def cmd_baseline(client: PoliteClient) -> None:
    ids = parse_sitemap_ids(client.get(SITEMAP_URL))
    save_json(SITEMAP_IDS_FILE, ids)
    print(f"baseline: 공간 id {len(ids):,}개 저장 (최대 id {ids[-1]})")


def cmd_diff(client: PoliteClient, max_detail: int) -> None:
    known = set(load_json(SITEMAP_IDS_FILE, []))
    if not known:
        sys.exit("먼저 baseline을 실행하세요.")
    state = load_json(STATE_FILE, {"room_numbers": INITIAL_ROOM_NUMBERS, "image_turns": {}})

    current = parse_sitemap_ids(client.get(SITEMAP_URL))
    new_ids = sorted(set(current) - known, reverse=True)
    print(f"diff: 새 공간 id {len(new_ids)}개")

    registered = 0
    for source_id in new_ids[:max_detail]:
        if registered >= REGISTER_PER_RUN or len(state["room_numbers"]) >= MAX_VIRTUAL_ROOMS:
            break
        try:
            space = parse_space(source_id, client.get(f"{BASE_URL}/space/{source_id}"))
        except (httpx.HTTPError, PermissionError) as exc:
            print(f"  {source_id}: 건너뜀 ({exc})")
            continue
        save_json(SPACES_DIR / f"{source_id}.json", asdict(space))
        if not is_target(space):
            print(
                f"  {source_id}: 대상 아님 {space.space_types} 최대 {space.max_capacity}명 {space.address_region}"
            )
            continue
        room = to_virtual_room(space, state)
        with NEW_ROOMS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(room, ensure_ascii=False) + "\n")
        registered += 1
        print(
            f"  {source_id}: 신규 룸 {room['room_no']}호 등록 ({room['room_type']}, 이미지 {room['image']})"
        )

    save_json(STATE_FILE, state)
    save_json(SITEMAP_IDS_FILE, current)


def cmd_fetch(client: PoliteClient, source_id: int) -> None:
    space = parse_space(source_id, client.get(f"{BASE_URL}/space/{source_id}"))
    print(json.dumps(asdict(space), ensure_ascii=False, indent=2))
    print("대상 여부:", is_target(space))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("baseline", help="사이트맵 id 목록을 기준선으로 저장")
    diff = sub.add_parser("diff", help="기준선 이후 새 id를 찾아 신규 룸 등록")
    diff.add_argument("--max-detail", type=int, default=MAX_DETAIL_PER_RUN)
    fetch = sub.add_parser("fetch", help="공간 하나를 파싱해 출력")
    fetch.add_argument("source_id", type=int)
    args = parser.parse_args()

    client = PoliteClient()
    if args.cmd == "baseline":
        cmd_baseline(client)
    elif args.cmd == "diff":
        cmd_diff(client, args.max_detail)
    else:
        cmd_fetch(client, args.source_id)


if __name__ == "__main__":
    main()
