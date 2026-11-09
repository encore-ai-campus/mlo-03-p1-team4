"""F-61: 외부 요청 없이 수집 상한·개인정보 제외·매핑·재시도를 검증한다."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import deque
from dataclasses import asdict
from pathlib import Path

import httpx
import pytest

from app.schemas.internal import InternalVenueUpsert
from crawler.crawl_venues import (
    CrawlerRunError,
    CrawlerStageError,
    _empty_registration_result,
    candidate_ids,
    crawl_details,
    raw_document,
    read_state,
    register_pending,
    run,
)
from crawler.preprocess import SeedMaps, map_space, venue_payload
from crawler.shareit_crawler import parse_shareit
from crawler.spacecloud_crawler import (
    PoliteClient,
    SpaceInfo,
    parse_space,
    sanitized_dict,
    sitemap_links,
)


def test_crawler_cli_imports_from_repository_root():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-m", "crawler.crawl_venues", "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "baseline" in result.stdout


def test_spacecloud_parser_uses_region_and_locality_without_detail_address():
    html = """
    <script type="application/ld+json">{
      "@type":"LocalBusiness","name":"실제 업체 이름",
      "address":{"streetAddress":"서울특별시 영등포구 상세로 123",
                 "addressRegion":"서울특별시","addressLocality":"마포구"},
      "aggregateRating":{"ratingValue":"4.5","reviewCount":"12"}
    }</script>
    <ul class="list_detail">
      <li><span class="tit">공간유형</span> 스터디룸</li>
      <li><span class="tit">수용인원</span> 최대 8명</li>
      <li><span class="tit">예약시간</span> 최소 2시간</li>
    </ul>
    <ul class="reserv_list"><li>₩ 12,000 / 시간</li></ul>
    <ul class="facility_list"><li>와이파이</li></ul>
    <ul class="officehours"><li>영업시간 09:00~23:00</li></ul>
    """
    space = parse_space("53074", html)
    row = asdict(space)
    assert space.address_region == "서울특별시 마포구"
    assert space.prices == [{"amount": 12000, "unit": "시간", "per_person": False}]
    assert "name" not in row
    assert "상세로" not in json.dumps(row, ensure_ascii=False)
    assert "실제 업체" not in json.dumps(row, ensure_ascii=False)


def test_spacecloud_parser_keeps_city_and_legal_dong_only():
    html = """
    <script type="application/ld+json">{
      "@type":"LocalBusiness","name":"실제 업체 이름",
      "address":{"addressRegion":"서울","addressLocality":"봉천동",
                 "streetAddress":"서울특별시 영등포구 상세로 123"}
    }</script>
    """
    space = parse_space("53074", html)
    assert space.address_region == "서울 봉천동"
    assert "상세로" not in json.dumps(asdict(space), ensure_ascii=False)


def test_shareit_uses_only_explicit_hourly_goods():
    data = {
        "props": {
            "pageProps": {
                "spaceMetaData": {
                    "resource": {
                        "mainZone3Types": [{"type": "강의실"}],
                        "legalAddress": {"name": "경기도 고양시 덕양구 상세로 2"},
                        "name": "실제 쉐어잇 업체",
                    }
                },
                "goods": [
                    {
                        "saleInfo": {
                            "price": 55000,
                            "timeUnitMinute": 60,
                            "minimumSalesTimeRangeMinute": 120,
                            "ruleType": 1,
                        },
                        "personnelConfig": {"maximumNumberPersonnel": 20},
                    },
                    {
                        "saleInfo": {"price": 200000, "timeUnitMinute": 1440, "ruleType": 2},
                        "personnelConfig": {"maximumNumberPersonnel": 20},
                    },
                ],
                "placeInfo": {"addressDetail": "상세 호수"},
            }
        }
    }
    html = f'<script id="__NEXT_DATA__">{json.dumps(data, ensure_ascii=False)}</script>'
    row = asdict(parse_shareit("1321", html))
    assert row["space_types"] == ["강의실"]
    assert row["max_capacity"] == 20
    assert row["min_hours"] == 2
    assert row["prices"] == [
        {
            "amount": 55000,
            "unit": "시간",
            "per_person": False,
            "min_hours": 2,
            "capacity_max": 20,
        }
    ]
    assert row["address_region"] == "경기도 고양시"
    assert "실제 쉐어잇" not in str(row)
    assert "상세 호수" not in str(row)


def test_mapping_and_generated_venue_payload():
    maps = SeedMaps.load()
    space = SpaceInfo(
        "53074",
        ["스터디룸"],
        8,
        2,
        ["와이파이", "화이트보드"],
        [{"amount": 12000, "unit": "시간", "per_person": False}],
        "09:00~23:00",
        "서울특별시 마포구",
    )
    mapped, reason = map_space("spacecloud", space, maps)
    assert reason is None
    assert mapped["category"] == "studyroom"
    assert (mapped["sido"], mapped["sigungu"]) == ("서울", "마포구")
    assert mapped["facilities"] == ["인터넷/WIFI", "화이트보드"]
    body = venue_payload("spacecloud", "53074", mapped)
    assert body["name"] == "마포구 스터디룸 53074호"
    assert len(body["images"]) == 3
    assert all(image.startswith("art:") for image in body["images"])
    assert body["source_id"] == "53074"
    assert InternalVenueUpsert.model_validate(body).category_code == "studyroom"


def test_shareit_mapping_keeps_price_capacity_and_minimum_from_one_good():
    maps = SeedMaps.load()
    space = SpaceInfo(
        "1321",
        ["강의실"],
        50,
        1,
        [],
        [
            {
                "amount": 30000,
                "unit": "시간",
                "per_person": False,
                "min_hours": 3,
                "capacity_max": 6,
            },
            {
                "amount": 50000,
                "unit": "시간",
                "per_person": False,
                "min_hours": 1,
                "capacity_max": 50,
            },
        ],
        None,
        "경기도 고양시",
    )
    mapped, reason = map_space("shareit", space, maps)
    assert reason is None
    assert (mapped["price_per_hour"], mapped["min_hours"], mapped["capacity_max"]) == (30000, 3, 6)

    space.prices[0]["capacity_max"] = None
    mapped, reason = map_space("shareit", space, maps)
    assert reason is None
    assert (mapped["price_per_hour"], mapped["min_hours"], mapped["capacity_max"]) == (50000, 1, 50)


def test_raw_document_keeps_only_normalized_free_text():
    maps = SeedMaps.load()
    space = SpaceInfo(
        "53074",
        ["스터디룸"],
        8,
        1,
        ["와이파이 010-1234-5678"],
        [{"amount": 12000, "unit": "시간", "per_person": False}],
        "09:00~23:00 문의 010-1234-5678",
        "서울특별시 마포구 서교동 123-4",
    )
    mapped, reason = map_space("spacecloud", space, maps)
    assert reason is None
    row = raw_document("spacecloud", space, 1, mapped, None)
    assert row["extracted"]["facilities"] == ["인터넷/WIFI"]
    assert row["extracted"]["open_hours"] == "09:00~23:00"
    assert row["extracted"]["address_region"] == "서울 마포구"
    assert "010-1234-5678" not in str(row)
    assert "서교동" not in str(row)
    assert "010-1234-5678" not in str(sanitized_dict(space))


def test_unknown_or_ambiguous_region_is_excluded():
    maps = SeedMaps.load()
    space = SpaceInfo(
        "1",
        ["카페"],
        5,
        1,
        [],
        [{"amount": 10000, "unit": "시간", "per_person": False}],
        None,
        "인천광역시 중구",
    )
    mapped, reason = map_space("spacecloud", space, maps)
    assert mapped is None
    assert "나뉜 옛 구" in reason


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("서울 봉천동", ("서울", "관악구")),
        ("천안 두정동", ("충남", "천안시")),
        ("서울 양평동1가", ("서울", "영등포구")),
        ("인천 가정동", ("인천", "서해구")),
        ("인천 가좌동", ("인천", "서해구")),
        ("인천 원당동", ("인천", "검단구")),
    ],
)
def test_official_legal_dong_mapping(address, expected):
    maps = SeedMaps.load()
    space = SpaceInfo(
        "1",
        ["카페"],
        5,
        1,
        [],
        [{"amount": 10000, "unit": "시간", "per_person": False}],
        None,
        address,
    )
    mapped, reason = map_space("spacecloud", space, maps)
    assert reason is None
    assert (mapped["sido"], mapped["sigungu"]) == expected


def test_ambiguous_and_missing_legal_dong_have_distinct_exclusion_reasons():
    maps = SeedMaps.load()
    space = SpaceInfo(
        "1",
        ["카페"],
        5,
        1,
        [],
        [{"amount": 10000, "unit": "시간", "per_person": False}],
        None,
        "서울 신사동",
    )
    mapped, reason = map_space("spacecloud", space, maps)
    assert mapped is None
    assert reason == "동 이름 겹침"

    space.address_region = "서울 등록되지않은동"
    mapped, reason = map_space("spacecloud", space, maps)
    assert mapped is None
    assert reason == "동 대응 없음"


def test_sitemap_index_and_detail_ids():
    index = (
        "<sitemapindex><sitemap><loc>https://shareit.kr/venue-1.xml</loc></sitemap></sitemapindex>"
    )
    children, ids = sitemap_links(index, "shareit")
    assert children == ["https://shareit.kr/venue-1.xml"]
    assert ids == []
    urls = (
        "<urlset><url><loc>https://shareit.kr/venue/1321</loc></url>"
        "<url><loc>https://shareit.kr/venue/1321</loc></url>"
        "<url><loc>https://other.test/venue/1</loc></url></urlset>"
    )
    assert sitemap_links(urls, "shareit") == ([], ["1321"])


def test_sitemap_rejects_dtd_entities():
    xml = '<!DOCTYPE urlset [<!ENTITY name "x">]><urlset>&name;</urlset>'
    with pytest.raises(ValueError, match="XML 선언"):
        sitemap_links(xml, "spacecloud")


def test_robots_are_site_specific_and_redirect_is_checked():
    requested = []

    def respond(request):
        requested.append(str(request.url))
        path = request.url.path
        if path == "/robots.txt":
            blocked = "/venue/" if request.url.host == "shareit.kr" else "/search"
            return httpx.Response(200, text=f"User-agent: *\nDisallow: {blocked}\n")
        if path == "/space/1":
            return httpx.Response(302, headers={"location": "https://shareit.kr/venue/1"})
        return httpx.Response(200, text="ok")

    http = httpx.Client(transport=httpx.MockTransport(respond))
    with PoliteClient(http=http, delay=0) as client:
        with pytest.raises(PermissionError):
            client.get("https://www.spacecloud.kr/space/1")
        with pytest.raises(PermissionError):
            client.get("https://shareit.kr/venue/1")
    assert requested == [
        "https://www.spacecloud.kr/robots.txt",
        "https://www.spacecloud.kr/space/1",
        "https://shareit.kr/robots.txt",
    ]


def test_crawler_rejects_other_ports_before_request():
    requested = []

    def respond(request):
        requested.append(str(request.url))
        return httpx.Response(200, text="ok")

    with (
        PoliteClient(http=httpx.Client(transport=httpx.MockTransport(respond))) as client,
        pytest.raises(PermissionError, match="허용하지 않은 수집 사이트"),
    ):
        client.get("https://www.spacecloud.kr:444/space/1")
    assert requested == []
    assert sitemap_links(
        "<urlset><url><loc>https://shareit.kr:444/venue/1</loc></url></urlset>",
        "shareit",
    ) == ([], [])


def test_robots_request_and_first_detail_obey_delay(monkeypatch):
    waited = []
    monkeypatch.setattr("crawler.spacecloud_crawler.time.monotonic", lambda: 10.0)
    monkeypatch.setattr("crawler.spacecloud_crawler.time.sleep", waited.append)

    def respond(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /\n")
        return httpx.Response(200, text="ok")

    with PoliteClient(http=httpx.Client(transport=httpx.MockTransport(respond))) as client:
        assert client.get("https://www.spacecloud.kr/space/1") == "ok"
    assert waited == [3.0]


class FakeRaw:
    def __init__(self):
        self.rows = {}
        self.fail_venue_write = False

    def find_one(self, query, *_):
        return self.rows.get((query["source_site"], query["source_id"]))

    def update_one(self, query, update, upsert=False):
        if "_id" in query:
            if self.fail_venue_write:
                raise RuntimeError("Mongo 기록 실패")
            row = next(value for value in self.rows.values() if value["_id"] == query["_id"])
            row.update(update["$set"])
        else:
            key = (query["source_site"], query["source_id"])
            self.rows[key] = {"_id": key, **update["$set"]}

    def find(self, query):
        rows = [
            row
            for row in self.rows.values()
            if row["source_site"] in query["source_site"]["$in"]
            and row["status"] == "ok"
            and row.get("mapped") is not None
        ]
        return FakeCursor(rows)

    def count_documents(self, query):
        return sum(
            row["source_site"] == query["source_site"] and row["status"] == query["status"]
            for row in self.rows.values()
        )


class FakeCursor(list):
    def sort(self, *_):
        return self


class FakeApi:
    def __init__(self):
        self.calls = []

    def post(self, _url, *, headers, json, timeout):
        self.calls.append(json)
        assert headers["X-Internal-Key"] == "test-key"
        return httpx.Response(
            201,
            json={"venue_id": 123, "ignored_facilities": []},
            request=httpx.Request("POST", _url),
        )


def test_failed_venue_id_write_can_retry_same_source():
    raw, api = FakeRaw(), FakeApi()
    maps = SeedMaps.load()
    space = SpaceInfo(
        "53074",
        ["스터디룸"],
        8,
        1,
        [],
        [{"amount": 10000, "unit": "시간", "per_person": False}],
        None,
        "서울 마포구",
    )
    mapped, _ = map_space("spacecloud", space, maps)
    raw.update_one(
        {"source_site": "spacecloud", "source_id": "53074"},
        {"$set": raw_document("spacecloud", space, 1, mapped, None)},
        upsert=True,
    )
    raw.fail_venue_write = True
    with pytest.raises(RuntimeError, match="Mongo 기록 실패"):
        register_pending(
            raw, api, "test-key", "http://test/internal/venues", 1, True, ("spacecloud",)
        )
    assert raw.rows[("spacecloud", "53074")]["status"] == "ok"
    raw.fail_venue_write = False
    assert (
        register_pending(
            raw, api, "test-key", "http://test/internal/venues", 1, True, ("spacecloud",)
        )["studyroom"]
        == 1
    )
    assert raw.rows[("spacecloud", "53074")]["venue_id"] == 123
    assert len(api.calls) == 2
    assert api.calls[0]["source_id"] == api.calls[1]["source_id"]


def test_register_pending_accepts_legacy_mapped_category_code():
    raw = _pending_raw()
    row = raw.rows[("spacecloud", "53074")]
    row["mapped"]["category_code"] = row["mapped"].pop("category")
    api = FakeApi()

    registered = register_pending(
        raw, api, "test-key", "http://test/internal/venues", 1, True, ("spacecloud",)
    )

    assert registered["studyroom"] == 1
    assert api.calls[0]["category_code"] == "studyroom"
    assert "category" not in row["mapped"]


def test_unprocessed_new_ids_remain_for_next_run(tmp_path, monkeypatch):
    raw = FakeRaw()
    site_ids = {"spacecloud": ["1", "2", "3"]}
    state = {"spacecloud": set()}
    candidates, new_counts = candidate_ids(site_ids, state, "weekly")
    assert new_counts == {"spacecloud": 3}
    html = '<ul class="list_detail"><li><span class="tit">공간유형</span> 연습실</li></ul>'

    class Client:
        def get(self, _url):
            return html

    monkeypatch.setattr("crawler.crawl_venues.get_event_time", lambda: "utc")
    path = tmp_path / "state.json"
    counts = crawl_details(
        Client(), raw, SeedMaps.load(), candidates, state, {"spacecloud": 1}, 1, path
    )
    assert counts == {"spacecloud": 1}
    assert read_state(path) == {"spacecloud": {"3"}}
    assert set(site_ids["spacecloud"]) - read_state(path)["spacecloud"] == {"1", "2"}
    assert raw.rows[("spacecloud", "3")]["status"] == "excluded"


def test_opened_detail_is_counted_if_parsing_fails(tmp_path, monkeypatch):
    class Client:
        def get(self, _url):
            return "<html></html>"

    def fail_parse(*_args):
        raise ValueError("파서 실패")

    monkeypatch.setattr("crawler.crawl_venues.parse_detail", fail_parse)
    fetched = {"spacecloud": 0}
    with pytest.raises(ValueError, match="파서 실패"):
        crawl_details(
            Client(),
            FakeRaw(),
            SeedMaps.load(),
            {"spacecloud": deque(["53074"])},
            {"spacecloud": set()},
            {"spacecloud": 1},
            1,
            tmp_path / "state.json",
            fetched,
        )
    assert fetched == {"spacecloud": 1}


def test_run_rejects_more_than_twenty_details_before_any_io():
    with pytest.raises(ValueError, match="0~20"):
        run(
            sites=("spacecloud",),
            mode="bootstrap",
            max_detail=21,
            max_register=0,
            client=None,
            raw=None,
            engine=None,
            api=None,
            key="",
        )


def test_weekly_run_allows_zero_new_registrations(tmp_path, monkeypatch):
    state_path = tmp_path / "sitemap_ids.json"
    state_path.write_text('{"spacecloud":["53074"]}', encoding="utf-8")
    monkeypatch.setattr("crawler.crawl_venues.fetch_sitemap_ids", lambda _client, _site: ["53074"])
    monkeypatch.setattr("crawler.crawl_venues.start_job", lambda _engine, _site: 1)
    finished = []
    monkeypatch.setattr(
        "crawler.crawl_venues.finish_job",
        lambda _engine, job_id, counts, status: finished.append((job_id, counts.copy(), status)),
    )
    result = run(
        sites=("spacecloud",),
        mode="weekly",
        max_detail=20,
        max_register=5,
        client=object(),
        raw=FakeRaw(),
        engine=None,
        api=FakeApi(),
        key="test-key",
        state_path=state_path,
    )
    assert result["jobs"] == {"spacecloud": {"new_ids": 0, "fetched": 0, "registered": 0}}
    assert finished == [(1, result["jobs"]["spacecloud"], "done")]


def _pending_raw():
    raw = FakeRaw()
    space = SpaceInfo(
        "53074",
        ["스터디룸"],
        8,
        1,
        [],
        [{"amount": 10000, "unit": "시간", "per_person": False}],
        None,
        "서울 마포구",
    )
    mapped, _ = map_space("spacecloud", space, SeedMaps.load())
    raw.update_one(
        {"source_site": "spacecloud", "source_id": "53074"},
        {"$set": raw_document("spacecloud", space, 1, mapped, None)},
        upsert=True,
    )
    return raw


@pytest.mark.parametrize("status,expected", [(200, 0), (201, 1)])
def test_pipeline_counts_only_http_201(monkeypatch, status, expected):
    api = FakeApi()
    monkeypatch.setattr(
        api,
        "post",
        lambda url, **kwargs: httpx.Response(
            status,
            json={"venue_id": 123, "ignored_facilities": []},
            request=httpx.Request("POST", url),
        ),
    )
    outcome = _empty_registration_result()
    register_pending(
        _pending_raw(),
        api,
        "test-key",
        "http://test/internal/venues",
        1,
        True,
        ("spacecloud",),
        outcome=outcome,
    )
    assert outcome["newly_registered_by_category"]["studyroom"] == expected
    assert outcome["registered_by_category"]["studyroom"] == 1
    assert len(outcome["newly_registered_by_category"]) == 5


def test_pipeline_keeps_confirmed_201_when_mongo_write_fails():
    raw = _pending_raw()
    raw.fail_venue_write = True
    outcome = _empty_registration_result()
    with pytest.raises(CrawlerStageError) as failure:
        register_pending(
            raw,
            FakeApi(),
            "test-key",
            "http://test/internal/venues",
            1,
            True,
            ("spacecloud",),
            outcome=outcome,
        )
    assert outcome["newly_registered_by_category"]["studyroom"] == 1
    assert outcome["confirmed_registrations"][0]["venue_id"] == 123
    assert outcome["registered_by_category"]["studyroom"] == 0
    assert failure.value.failure["kind"] == "internal"


def test_pipeline_marks_lost_registration_response_uncertain(monkeypatch):
    api = FakeApi()

    def no_response(url, **kwargs):
        raise httpx.ReadTimeout("test", request=httpx.Request("POST", url))

    monkeypatch.setattr(api, "post", no_response)
    outcome = _empty_registration_result()
    with pytest.raises(CrawlerStageError):
        register_pending(
            _pending_raw(),
            api,
            "test-key",
            "http://test/internal/venues",
            1,
            True,
            ("spacecloud",),
            outcome=outcome,
        )
    assert len(outcome["uncertain_registrations"]) == 1
    assert sum(outcome["newly_registered_by_category"].values()) == 0


def test_pipeline_run_error_preserves_partial_201_and_job_id(tmp_path, monkeypatch):
    raw = _pending_raw()
    raw.fail_venue_write = True
    monkeypatch.setattr("crawler.crawl_venues.start_job", lambda *args: 42)
    monkeypatch.setattr("crawler.crawl_venues.finish_job", lambda *args: None)
    monkeypatch.setattr("crawler.crawl_venues.fetch_sitemap_ids", lambda *args: [])
    with pytest.raises(CrawlerRunError) as failure:
        run(
            sites=("spacecloud",),
            mode="bootstrap",
            max_detail=0,
            max_register=20,
            client=object(),
            raw=raw,
            engine=None,
            api=FakeApi(),
            key="test-key",
            state_path=tmp_path / "sitemap.json",
        )
    result = failure.value.result
    assert result["newly_registered_by_category"]["studyroom"] == 1
    assert result["job_ids"] == {"spacecloud": 42}
    assert result["ok"] is False


def test_minimum_booking_time_cannot_exceed_business_hours():
    space = SpaceInfo(
        "53074",
        ["스터디룸"],
        8,
        4,
        [],
        [{"amount": 10000, "unit": "시간", "per_person": False}],
        "09:00~11:00",
        "서울 마포구",
    )
    mapped, reason = map_space("spacecloud", space, SeedMaps.load())
    assert mapped is None
    assert reason == "최소 이용시간이 영업시간보다 김"


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("서울 봉천동", "서울 관악구"),
        ("천안 두정동", "충남 천안시"),
        ("서울 신사동", None),
        ("서울 등록되지않은동", None),
    ],
)
def test_sample_output_normalizes_or_omits_legal_dong(address, expected):
    space = SpaceInfo("1", [], None, None, [], [], None, address)
    data = sanitized_dict(space)
    assert data["address_region"] == expected
    assert address.split()[-1] not in json.dumps(data, ensure_ascii=False)


def test_spacecloud_parser_uses_region_and_locality_without_street():
    """11-07(#10): streetAddress가 빠진 새 JSON-LD는 addressRegion + addressLocality만 쓴다."""
    html = """
    <script type="application/ld+json">{
      "@type":"LocalBusiness","name":"실제 업체 이름",
      "address":{"addressRegion":"서울","addressLocality":"양평동1가"}
    }</script>
    <ul class="reserv_list"><li>₩ 12,000 / 시간</li></ul>
    """
    space = parse_space("53074", html)
    assert space.address_region == "서울 양평동1가"
    assert sanitized_dict(space)["address_region"] == "서울 영등포구"


def _space_at(address):
    return SpaceInfo(
        "1",
        ["카페"],
        5,
        1,
        [],
        [{"amount": 10000, "unit": "시간", "per_person": False}],
        None,
        address,
    )


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("서울 봉천동", ("서울", "관악구")),
        ("천안 두정동", ("충남", "천안시")),
        ("서울 양평동1가", ("서울", "영등포구")),
        ("인천 가정동", ("인천", "서해구")),
        ("서울특별시 마포구", ("서울", "마포구")),
    ],
)
def test_legal_dong_resolves_to_sigungu(address, expected):
    mapped, reason = map_space("spacecloud", _space_at(address), SeedMaps.load())
    assert reason is None
    assert (mapped["sido"], mapped["sigungu"]) == expected


def test_legal_dong_ambiguous_or_unknown_is_excluded():
    maps = SeedMaps.load()
    # 서울에 신사동은 강남구·은평구 두 곳이 있다.
    mapped, reason = map_space("spacecloud", _space_at("서울 신사동"), maps)
    assert mapped is None and reason == "동 이름 겹침"
    mapped, reason = map_space("spacecloud", _space_at("서울 없는동"), maps)
    assert mapped is None and reason == "동 대응 없음"


def test_legal_ri_resolves_with_city_name():
    mapped, reason = map_space("spacecloud", _space_at("김포 석모리"), SeedMaps.load())
    assert reason is None
    assert (mapped["sido"], mapped["sigungu"]) == ("경기", "김포시")
