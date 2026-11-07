"""F-61 두 사이트의 사이트맵 → crawl_raw → 내부 공간 등록 실행기.

루트에서 실행: conda run -n pro_1 --no-capture-output python -m crawler.crawl_venues ...
"""

from __future__ import annotations

import argparse
import json
from collections import deque
from contextlib import suppress
from pathlib import Path

import httpx
from pymongo import MongoClient
from sqlalchemy import create_engine, text

from app.core.clock import get_event_time, get_now
from app.core.config import get_settings
from crawler.preprocess import SeedMaps, map_space, venue_payload
from crawler.shareit_crawler import parse_shareit
from crawler.spacecloud_crawler import (
    MAX_DETAIL_PER_RUN,
    SHAREIT_BASE_URL,
    SPACE_BASE_URL,
    PoliteClient,
    SpaceInfo,
    fetch_sitemap_ids,
    parse_space,
    sanitized_dict,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "crawler" / "data"
SITEMAP_STATE = DATA_DIR / "sitemap_ids.json"
SITES = ("spacecloud", "shareit")
CATEGORIES = ("studyroom", "studio", "cafe", "lectureroom", "partyroom")
API_URL = "http://127.0.0.1:8000/internal/venues"


def read_state(path: Path = SITEMAP_STATE) -> dict[str, set[str]]:
    if not path.exists():
        return {}
    state = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(state, list):  # 10-30 시제품의 단일 사이트 기준선을 읽는다.
        return {"spacecloud": {str(value) for value in state}}
    return {
        site: {str(value) for value in values}
        for site, values in state.items()
        if site in SITES and isinstance(values, list)
    }


def write_state(state: dict[str, set[str]], path: Path = SITEMAP_STATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    data = {site: sorted(values, key=int) for site, values in state.items()}
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def detail_url(site: str, source_id: str) -> str:
    if site not in SITES or not source_id.isdecimal():
        raise ValueError("수집원 또는 출처 ID가 올바르지 않습니다.")
    base, segment = (
        (SPACE_BASE_URL, "space") if site == "spacecloud" else (SHAREIT_BASE_URL, "venue")
    )
    return f"{base}/{segment}/{source_id}"


def parse_detail(site: str, source_id: str, html: str) -> SpaceInfo:
    return parse_space(source_id, html) if site == "spacecloud" else parse_shareit(source_id, html)


def raw_document(
    site: str, space: SpaceInfo, job_id: int, mapped: dict | None, reason: str | None
) -> dict:
    extracted = sanitized_dict(space)
    extracted.pop("source_id")
    extracted.pop("space_types")
    # 자유 문구에 상세 주소·연락처가 섞여도 MongoDB에는 정규화한 속성만 남긴다.
    extracted["facilities"] = mapped["facilities"] if mapped else []
    extracted["open_hours"] = (
        f"{mapped['open_hour']:02d}:00~{mapped['close_hour']:02d}:00" if mapped else None
    )
    extracted["address_region"] = f"{mapped['sido']} {mapped['sigungu']}" if mapped else None
    return {
        "source_site": site,
        "source_id": space.source_id,
        "job_id": job_id,
        "crawled_at": get_event_time(),
        "status": "excluded" if reason else ("ok" if space.space_types else "no_detail"),
        "space_types": space.space_types,
        "extracted": extracted,
        "mapped": mapped,
        "exclude_reason": reason,
        "venue_id": None,
    }


def start_job(engine, site: str) -> int:
    with engine.begin() as db:
        result = db.execute(
            text(
                "INSERT INTO crawl_jobs (source_site, started_at, status) "
                "VALUES (:site, :now, 'running')"
            ),
            {"site": site, "now": get_now()},
        )
        return int(result.lastrowid)


def finish_job(engine, job_id: int, counts: dict, status: str) -> None:
    with engine.begin() as db:
        db.execute(
            text(
                "UPDATE crawl_jobs SET finished_at=:now, new_ids=:new_ids, "
                "fetched=:fetched, registered=:registered, status=:status "
                "WHERE job_id=:job_id"
            ),
            {"now": get_now(), "status": status, "job_id": job_id, **counts},
        )


def register_pending(
    raw,
    api: httpx.Client,
    key: str,
    api_url: str,
    limit: int,
    per_category: bool,
    sites: tuple[str, ...],
) -> dict[str, int]:
    """저장된 후보를 보내며 실패 시 ok 상태를 유지해 다음 실행에 재시도한다."""
    registered = dict.fromkeys(CATEGORIES, 0)
    cursor = raw.find(
        {"source_site": {"$in": list(sites)}, "status": "ok", "mapped": {"$ne": None}}
    ).sort([("crawled_at", 1), ("source_site", 1), ("source_id", 1)])
    for document in cursor:
        if sum(registered.values()) >= limit:
            break
        category = document["mapped"]["category"]
        if per_category and registered[category]:
            continue
        payload = venue_payload(document["source_site"], document["source_id"], document["mapped"])
        response = api.post(api_url, headers={"X-Internal-Key": key}, json=payload, timeout=30)
        if response.status_code == 400:
            code = response.json().get("code")
            if code in {"UNKNOWN_REGION", "UNKNOWN_CATEGORY"}:
                raw.update_one(
                    {"_id": document["_id"]},
                    {"$set": {"status": "excluded", "exclude_reason": code}},
                )
                continue
        response.raise_for_status()
        if response.status_code not in {200, 201}:
            raise ValueError("등록 API가 예상하지 않은 상태를 반환했습니다.")
        venue_id = response.json().get("venue_id")
        if not isinstance(venue_id, int) or venue_id <= 0:
            raise ValueError("등록 API 응답에 venue_id가 없습니다.")
        raw.update_one(
            {"_id": document["_id"]},
            {"$set": {"status": "registered", "venue_id": venue_id}},
        )
        registered[category] += 1
    return registered


def candidate_ids(
    site_ids: dict[str, list[str]], state: dict[str, set[str]], mode: str
) -> tuple[dict[str, deque[str]], dict[str, int]]:
    candidates, new_counts = {}, {}
    for site, ids in site_ids.items():
        known = state.get(site, set())
        new = set(ids) - known
        new_counts[site] = len(new) if mode == "weekly" else 0
        chosen = new if mode == "weekly" else set(ids)
        candidates[site] = deque(sorted(chosen, key=int, reverse=True))
    return candidates, new_counts


def crawl_details(
    client: PoliteClient,
    raw,
    maps: SeedMaps,
    candidates: dict[str, deque[str]],
    state: dict[str, set[str]],
    job_ids: dict[str, int],
    max_detail: int,
    state_path: Path,
    fetched: dict[str, int] | None = None,
) -> dict[str, int]:
    if fetched is None:
        fetched = dict.fromkeys(candidates, 0)
    sites = list(candidates)
    while sum(fetched.values()) < max_detail and any(candidates.values()):
        for site in sites:
            if not candidates[site] or sum(fetched.values()) >= max_detail:
                continue
            source_id = candidates[site].popleft()
            existing = raw.find_one({"source_site": site, "source_id": source_id}, {"status": 1})
            if existing:
                state.setdefault(site, set()).add(source_id)
                write_state(state, state_path)
                continue
            try:
                html = client.get(detail_url(site, source_id))
            except httpx.HTTPStatusError as error:
                if error.response.status_code != 404:
                    raise
                fetched[site] += 1
                space = SpaceInfo(source_id, [], None, None, [], [], None, None)
            else:
                fetched[site] += 1
                space = parse_detail(site, source_id, html)
            mapped, reason = map_space(site, space, maps) if space.space_types else (None, None)
            document = raw_document(site, space, job_ids[site], mapped, reason)
            raw.update_one(
                {"source_site": site, "source_id": source_id},
                {"$set": document},
                upsert=True,
            )
            state.setdefault(site, set()).add(source_id)
            write_state(state, state_path)
    return fetched


def run(
    *,
    sites: tuple[str, ...],
    mode: str,
    max_detail: int,
    max_register: int,
    client: PoliteClient,
    raw,
    engine,
    api: httpx.Client,
    key: str,
    api_url: str = API_URL,
    state_path: Path = SITEMAP_STATE,
) -> dict:
    if not 0 <= max_detail <= MAX_DETAIL_PER_RUN:
        raise ValueError("상세 조회는 실행당 0~20건이어야 합니다.")
    if not 0 <= max_register <= (5 if mode == "weekly" else 20):
        raise ValueError("등록 상한이 모드 범위를 넘었습니다.")
    state = read_state(state_path)
    if mode == "weekly" and any(site not in state for site in sites):
        raise ValueError("먼저 baseline 명령으로 사이트맵 기준선을 만드세요.")
    maps = SeedMaps.load()
    job_ids, counts, before = {}, {}, {}
    fetched = dict.fromkeys(sites, 0)
    try:
        site_ids = {}
        for site in sites:
            job_ids[site] = start_job(engine, site)
            counts[site] = {"new_ids": 0, "fetched": 0, "registered": 0}
            site_ids[site] = fetch_sitemap_ids(client, site)
        candidates, new_counts = candidate_ids(site_ids, state, mode)
        for site in sites:
            counts[site]["new_ids"] = new_counts[site]
        crawl_details(
            client,
            raw,
            maps,
            candidates,
            state,
            job_ids,
            max_detail,
            state_path,
            fetched,
        )
        for site in sites:
            counts[site]["fetched"] = fetched[site]
        before = {
            site: raw.count_documents({"source_site": site, "status": "registered"})
            for site in sites
        }
        registered = register_pending(raw, api, key, api_url, max_register, mode == "weekly", sites)
        for site in sites:
            after = raw.count_documents({"source_site": site, "status": "registered"})
            counts[site]["registered"] = after - before[site]
        for site, job_id in job_ids.items():
            finish_job(engine, job_id, counts[site], "done")
        return {"jobs": counts, "registered_by_category": registered}
    except Exception:
        for site, job_id in job_ids.items():
            counts[site]["fetched"] = fetched[site]
            if site in before:
                with suppress(Exception):
                    counts[site]["registered"] = max(
                        0,
                        raw.count_documents({"source_site": site, "status": "registered"})
                        - before[site],
                    )
            with suppress(Exception):
                finish_job(engine, job_id, counts[site], "failed")
        raise


def _runtime():
    settings = get_settings()
    if not settings.db_write_url or not settings.mongo_url or not settings.internal_api_key:
        raise ValueError("DB_WRITE_URL, MONGO_URL, INTERNAL_API_KEY를 backend/.env에 설정하세요.")
    engine = create_engine(settings.db_write_url.get_secret_value(), pool_pre_ping=True)
    mongo = MongoClient(settings.mongo_url.get_secret_value(), serverSelectionTimeoutMS=3000)
    try:
        mongo.admin.command("ping")
        raw = mongo.get_database("crawl").get_collection("crawl_raw")
        if "crawl_raw" not in mongo.get_database("crawl").list_collection_names():
            raise ValueError("docs/db/mongo_init.js를 먼저 적용하세요.")
        with engine.connect() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        mongo.close()
        engine.dispose()
        raise
    return engine, mongo, raw, settings.internal_api_key.get_secret_value()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("baseline", "run", "fetch"):
        command = sub.add_parser(name)
        command.add_argument("--site", choices=(*SITES, "all"), default="all")
        if name == "run":
            command.add_argument("--mode", choices=("bootstrap", "weekly"), default="weekly")
            command.add_argument("--max-detail", type=int, default=MAX_DETAIL_PER_RUN)
            command.add_argument("--max-register", type=int)
        elif name == "fetch":
            command.add_argument("source_id")
    args = parser.parse_args()
    sites = SITES if args.site == "all" else (args.site,)
    if args.command == "run":
        max_register = args.max_register
        if max_register is None:
            max_register = 5 if args.mode == "weekly" else 20
        if not 0 <= args.max_detail <= MAX_DETAIL_PER_RUN:
            parser.error("--max-detail은 0~20이어야 합니다.")
        if not 0 <= max_register <= (5 if args.mode == "weekly" else 20):
            parser.error("--max-register 값이 모드 상한을 넘었습니다.")
        engine, mongo, raw, key = _runtime()
        try:
            with PoliteClient() as client, httpx.Client() as api:
                result = run(
                    sites=sites,
                    mode=args.mode,
                    max_detail=args.max_detail,
                    max_register=max_register,
                    client=client,
                    raw=raw,
                    engine=engine,
                    api=api,
                    key=key,
                )
            print(json.dumps(result, ensure_ascii=False))
        finally:
            mongo.close()
            engine.dispose()
        return
    with PoliteClient() as client:
        if args.command == "baseline":
            state = read_state()
            for site in sites:
                ids = fetch_sitemap_ids(client, site)
                state[site] = set(ids)
                print(f"{site}: 기준선 {len(ids)}개")
            write_state(state)
        else:
            if len(sites) != 1:
                parser.error("fetch에는 --site를 지정하세요.")
            site = sites[0]
            space = parse_detail(site, args.source_id, client.get(detail_url(site, args.source_id)))
            print(json.dumps(sanitized_dict(space), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
