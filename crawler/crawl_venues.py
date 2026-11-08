"""F-61 두 사이트의 사이트맵 → crawl_raw → 내부 공간 등록 실행기.

루트에서 실행: conda run -n pro_1 --no-capture-output python -m crawler.crawl_venues ...
"""

from __future__ import annotations

import argparse
import json
from collections import deque
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


class CrawlerStageError(RuntimeError):
    """실패 단계와 외부·내부 경계를 안전한 요약으로 보존한다."""

    def __init__(self, stage: str, kind: str, summary: str, cause: Exception):
        self.failure = {
            "stage": stage,
            "kind": kind,
            "error_type": type(cause).__name__,
            "summary": summary,
        }
        super().__init__(summary)


class CrawlerRunError(RuntimeError):
    """실패하더라도 통합 실행기가 확인된 부분 결과를 읽게 한다."""

    def __init__(self, result: dict):
        self.result = result
        summary = (result.get("failure") or {}).get("summary", "크롤러 실행에 실패했습니다.")
        super().__init__(summary)


def _empty_category_counts() -> dict[str, int]:
    return dict.fromkeys(CATEGORIES, 0)


def _empty_registration_result() -> dict:
    return {
        "registered_by_category": _empty_category_counts(),
        "newly_registered_by_category": _empty_category_counts(),
        "confirmed_registrations": [],
        "uncertain_registrations": [],
    }


def _empty_run_result(sites: tuple[str, ...]) -> dict:
    return {
        "ok": True,
        "job_ids": {},
        "jobs": {site: {"new_ids": 0, "fetched": 0, "registered": 0} for site in sites},
        **_empty_registration_result(),
        "failure": None,
    }


def _stage_call(
    stage: str,
    kind: str,
    summary: str,
    operation,
    context: dict | None = None,
    *,
    structured: bool = True,
):
    if not structured:
        return operation()
    try:
        return operation()
    except CrawlerStageError:
        raise
    except Exception as error:
        failure = CrawlerStageError(stage, kind, summary, error)
        if context:
            failure.failure.update(context)
        raise failure from error


def _validate_run_options(
    sites: tuple[str, ...], mode: str, max_detail: int, max_register: int
) -> None:
    if not sites or any(site not in SITES for site in sites):
        raise ValueError("수집원 설정을 확인해 주세요.")
    if mode not in {"bootstrap", "weekly"}:
        raise ValueError("크롤링 모드를 확인해 주세요.")
    if not 0 <= max_detail <= MAX_DETAIL_PER_RUN:
        raise ValueError("상세 조회는 실행당 0~20건이어야 합니다.")
    if not 0 <= max_register <= (5 if mode == "weekly" else 20):
        raise ValueError("등록 상한이 모드 범위를 넘었습니다.")


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
    outcome: dict | None = None,
) -> dict[str, int]:
    """후보를 등록하고 선택적으로 통합 실행기용 부분 결과를 갱신한다."""
    registered = dict.fromkeys(CATEGORIES, 0)
    cursor = _stage_call(
        "pending_read",
        "internal",
        "등록 대기 후보를 읽지 못했습니다.",
        lambda: raw.find(
            {"source_site": {"$in": list(sites)}, "status": "ok", "mapped": {"$ne": None}}
        ).sort([("crawled_at", 1), ("source_site", 1), ("source_id", 1)]),
        structured=outcome is not None,
    )
    try:
        for document in cursor:
            if sum(registered.values()) >= limit:
                break
            site, source_id = document["source_site"], document["source_id"]
            mapped = document["mapped"]
            category = mapped.get("category")
            if category is None:
                category = mapped.get("category_code")
                if category is not None:
                    mapped = {**mapped, "category": category}
            if category not in CATEGORIES:
                raise ValueError("지원하지 않는 크롤링 공간 유형입니다.")
            if per_category and registered[category]:
                continue
            context = {"source_site": site, "source_id": source_id}
            payload = _stage_call(
                "venue_api_payload",
                "internal",
                "내부 공간 등록 요청을 구성하지 못했습니다.",
                lambda site=site, source_id=source_id, mapped=mapped: venue_payload(
                    site, source_id, mapped
                ),
                context,
                structured=outcome is not None,
            )
            try:
                response = api.post(
                    api_url, headers={"X-Internal-Key": key}, json=payload, timeout=30
                )
            except Exception as error:
                if outcome is None:
                    raise
                if outcome is not None:
                    outcome["uncertain_registrations"].append(
                        {
                            "source_site": site,
                            "source_id": source_id,
                            "category": category,
                            "reason": "no_response",
                        }
                    )
                failure = CrawlerStageError(
                    "venue_api", "internal", "내부 공간 등록 API에서 응답을 받지 못했습니다.", error
                )
                failure.failure.update(context)
                raise failure from error

            if response.status_code >= 500:
                if outcome is None:
                    response.raise_for_status()
                if outcome is not None:
                    outcome["uncertain_registrations"].append(
                        {
                            "source_site": site,
                            "source_id": source_id,
                            "category": category,
                            "reason": "server_error_response",
                        }
                    )
                error = ValueError("registration server error")
                failure = CrawlerStageError(
                    "venue_api", "internal", "내부 공간 등록 API가 서버 오류를 반환했습니다.", error
                )
                failure.failure.update(context)
                raise failure from error

            if response.status_code == 400:
                code = _stage_call(
                    "venue_api_response",
                    "internal",
                    "내부 공간 등록 API 응답을 해석하지 못했습니다.",
                    lambda response=response: response.json().get("code"),
                    context,
                    structured=outcome is not None,
                )
                if code in {"UNKNOWN_REGION", "UNKNOWN_CATEGORY"}:
                    _stage_call(
                        "registration_state_write",
                        "internal",
                        "제외된 후보 상태를 MongoDB에 기록하지 못했습니다.",
                        lambda document=document, code=code: raw.update_one(
                            {"_id": document["_id"]},
                            {"$set": {"status": "excluded", "exclude_reason": code}},
                        ),
                        context,
                        structured=outcome is not None,
                    )
                    continue

            if response.status_code not in {200, 201}:
                if outcome is None:
                    response.raise_for_status()
                error = ValueError("registration request failed")
                failure = CrawlerStageError(
                    "venue_api",
                    "internal",
                    "내부 공간 등록 API가 등록을 완료하지 못했습니다.",
                    error,
                )
                failure.failure.update(context)
                raise failure from error

            if response.status_code == 201:
                if outcome is not None:
                    outcome["newly_registered_by_category"][category] += 1
                    outcome["confirmed_registrations"].append(
                        {
                            "source_site": site,
                            "source_id": source_id,
                            "category": category,
                            "venue_id": None,
                            "status_code": 201,
                        }
                    )
                confirmed = outcome["confirmed_registrations"][-1] if outcome is not None else None
            else:
                confirmed = None

            body = _stage_call(
                "venue_api_response",
                "internal",
                "내부 공간 등록 API 응답을 해석하지 못했습니다.",
                response.json,
                context,
                structured=outcome is not None,
            )
            venue_id = body.get("venue_id") if isinstance(body, dict) else None
            if not isinstance(venue_id, int) or isinstance(venue_id, bool) or venue_id <= 0:
                if outcome is None:
                    raise ValueError("등록 API 응답에 venue_id가 없습니다.")
                error = ValueError("venue_id missing")
                failure = CrawlerStageError(
                    "venue_api_response",
                    "internal",
                    "내부 공간 등록 API 응답에 유효한 공간 ID가 없습니다.",
                    error,
                )
                failure.failure.update(context)
                raise failure from error
            if confirmed is not None:
                confirmed["venue_id"] = venue_id
            elif outcome is not None:
                outcome["confirmed_registrations"].append(
                    {
                        "source_site": site,
                        "source_id": source_id,
                        "category": category,
                        "venue_id": venue_id,
                        "status_code": 200,
                    }
                )

            _stage_call(
                "registration_state_write",
                "internal",
                "등록 결과를 MongoDB에 기록하지 못했습니다.",
                lambda document=document, venue_id=venue_id: raw.update_one(
                    {"_id": document["_id"]},
                    {"$set": {"status": "registered", "venue_id": venue_id}},
                ),
                context,
                structured=outcome is not None,
            )
            registered[category] += 1
            if outcome is not None:
                outcome["registered_by_category"][category] += 1
    except CrawlerStageError:
        raise
    except Exception as error:
        if outcome is None:
            raise
        raise CrawlerStageError(
            "pending_read", "internal", "등록 대기 후보를 처리하지 못했습니다.", error
        ) from error
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
    *,
    structured: bool = False,
) -> dict[str, int]:
    if fetched is None:
        fetched = dict.fromkeys(candidates, 0)

    def stage_call(stage: str, kind: str, summary: str, operation, context: dict):
        return _stage_call(stage, kind, summary, operation, context, structured=structured)

    sites = list(candidates)
    while sum(fetched.values()) < max_detail and any(candidates.values()):
        for site in sites:
            if not candidates[site] or sum(fetched.values()) >= max_detail:
                continue
            source_id = candidates[site].popleft()
            context = {"source_site": site, "source_id": source_id}
            existing = stage_call(
                "crawl_raw_read",
                "internal",
                "기존 크롤링 기록을 읽지 못했습니다.",
                lambda site=site, source_id=source_id: raw.find_one(
                    {"source_site": site, "source_id": source_id}, {"status": 1}
                ),
                context,
            )
            if existing:
                state.setdefault(site, set()).add(source_id)
                stage_call(
                    "state_write",
                    "internal",
                    "사이트맵 처리 상태를 저장하지 못했습니다.",
                    lambda: write_state(state, state_path),
                    context,
                )
                continue

            def fetch_detail(site: str = site, source_id: str = source_id):
                try:
                    return client.get(detail_url(site, source_id))
                except httpx.HTTPStatusError as error:
                    if error.response.status_code == 404:
                        return None
                    raise

            html = stage_call(
                "detail_fetch",
                "external",
                "외부 상세 페이지를 가져오지 못했습니다.",
                fetch_detail,
                context,
            )
            if html is None:
                fetched[site] += 1
                space = SpaceInfo(source_id, [], None, None, [], [], None, None)
            else:
                fetched[site] += 1
                space = stage_call(
                    "detail_parse",
                    "external",
                    "외부 상세 페이지를 해석하지 못했습니다.",
                    lambda site=site, source_id=source_id, html=html: parse_detail(
                        site, source_id, html
                    ),
                    context,
                )
            mapped, reason = stage_call(
                "detail_preprocess",
                "external",
                "외부 공간 속성을 정규화하지 못했습니다.",
                lambda site=site, space=space: (
                    map_space(site, space, maps) if space.space_types else (None, None)
                ),
                context,
            )
            document = stage_call(
                "detail_prepare",
                "internal",
                "정규화한 크롤링 기록을 구성하지 못했습니다.",
                lambda site=site, space=space, mapped=mapped, reason=reason: raw_document(
                    site, space, job_ids[site], mapped, reason
                ),
                context,
            )
            stage_call(
                "crawl_raw_write",
                "internal",
                "정규화한 크롤링 결과를 MongoDB에 저장하지 못했습니다.",
                lambda site=site, source_id=source_id, document=document: raw.update_one(
                    {"source_site": site, "source_id": source_id},
                    {"$set": document},
                    upsert=True,
                ),
                context,
            )
            state.setdefault(site, set()).add(source_id)
            stage_call(
                "state_write",
                "internal",
                "사이트맵 처리 상태를 저장하지 못했습니다.",
                lambda: write_state(state, state_path),
                context,
            )
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
    _validate_run_options(sites, mode, max_detail, max_register)
    result = _empty_run_result(sites)
    fetched = dict.fromkeys(sites, 0)
    before = {}
    try:
        state = _stage_call(
            "state_read",
            "internal",
            "사이트맵 처리 상태를 읽지 못했습니다.",
            lambda: read_state(state_path),
        )
        if mode == "weekly" and any(site not in state for site in sites):
            raise CrawlerStageError(
                "baseline_required",
                "internal",
                "먼저 baseline 명령으로 사이트맵 기준선을 만드세요.",
                ValueError(),
            )
        maps = _stage_call(
            "seed_load", "internal", "공간 매핑 기준표를 읽지 못했습니다.", SeedMaps.load
        )
        site_ids = {}
        for site in sites:
            result["job_ids"][site] = _stage_call(
                "job_start",
                "internal",
                "크롤링 작업을 시작하지 못했습니다.",
                lambda site=site: start_job(engine, site),
                {"source_site": site},
            )
            site_ids[site] = _stage_call(
                "sitemap_fetch",
                "external",
                "외부 사이트맵을 가져오지 못했습니다.",
                lambda site=site: fetch_sitemap_ids(client, site),
                {"source_site": site},
            )
            if mode == "weekly":
                result["jobs"][site]["new_ids"] = len(set(site_ids[site]) - state.get(site, set()))
        candidates, new_counts = candidate_ids(site_ids, state, mode)
        for site in sites:
            result["jobs"][site]["new_ids"] = new_counts[site]
        crawl_details(
            client,
            raw,
            maps,
            candidates,
            state,
            result["job_ids"],
            max_detail,
            state_path,
            fetched,
            structured=True,
        )
        for site in sites:
            result["jobs"][site]["fetched"] = fetched[site]
        before = {
            site: _stage_call(
                "registration_count",
                "internal",
                "등록된 공간 수를 조회하지 못했습니다.",
                lambda site=site: raw.count_documents(
                    {"source_site": site, "status": "registered"}
                ),
                {"source_site": site},
            )
            for site in sites
        }
        registration = _empty_registration_result()
        result.update(registration)
        register_pending(
            raw,
            api,
            key,
            api_url,
            max_register,
            mode == "weekly",
            sites,
            outcome=registration,
        )
        for site in sites:
            after = _stage_call(
                "registration_count",
                "internal",
                "등록된 공간 수를 조회하지 못했습니다.",
                lambda site=site: raw.count_documents(
                    {"source_site": site, "status": "registered"}
                ),
                {"source_site": site},
            )
            result["jobs"][site]["registered"] = after - before[site]
        for site, job_id in result["job_ids"].items():
            _stage_call(
                "job_finish",
                "internal",
                "크롤링 작업 결과를 저장하지 못했습니다.",
                lambda site=site, job_id=job_id: finish_job(
                    engine, job_id, result["jobs"][site], "done"
                ),
                {"source_site": site},
            )
        return result
    except Exception as error:
        if isinstance(error, CrawlerStageError):
            failure = dict(error.failure)
        else:
            failure = {
                "stage": "run",
                "kind": "internal",
                "error_type": type(error).__name__,
                "summary": "크롤러 실행 중 내부 오류가 발생했습니다.",
            }
        result["ok"] = False
        result["failure"] = failure
        cleanup_failures = []
        for site in sites:
            result["jobs"][site]["fetched"] = fetched.get(site, 0)
            if site in before:
                try:
                    count = raw.count_documents({"source_site": site, "status": "registered"})
                    result["jobs"][site]["registered"] = max(0, count - before[site])
                except Exception as count_error:
                    cleanup_failures.append(
                        {
                            "stage": "registration_count",
                            "kind": "internal",
                            "source_site": site,
                            "error_type": type(count_error).__name__,
                            "summary": "부분 등록 건수를 조회하지 못했습니다.",
                        }
                    )
        for site, job_id in result["job_ids"].items():
            try:
                finish_job(engine, job_id, result["jobs"][site], "failed")
            except Exception as cleanup_error:
                cleanup_failures.append(
                    {
                        "stage": "job_finish",
                        "kind": "internal",
                        "source_site": site,
                        "error_type": type(cleanup_error).__name__,
                        "summary": "실패한 크롤링 작업 상태를 저장하지 못했습니다.",
                    }
                )
        if cleanup_failures:
            result["secondary_failures"] = cleanup_failures
            if failure["kind"] != "internal":
                result["original_failure"] = failure
                result["failure"] = cleanup_failures[0]
        raise CrawlerRunError(result) from error


def run_configured(
    *,
    sites: tuple[str, ...] = SITES,
    mode: str = "weekly",
    max_detail: int = MAX_DETAIL_PER_RUN,
    max_register: int | None = None,
    api_url: str = API_URL,
    state_path: Path = SITEMAP_STATE,
) -> dict:
    """통합 실행기에서 import해 호출하는 공개 F-61 실행 진입점."""
    if max_register is None:
        max_register = 5 if mode == "weekly" else 20
    _validate_run_options(sites, mode, max_detail, max_register)
    try:
        engine, mongo, raw, key = _runtime()
    except Exception as error:
        result = _empty_run_result(sites)
        result["ok"] = False
        result["failure"] = {
            "stage": "runtime_init",
            "kind": "internal",
            "error_type": type(error).__name__,
            "summary": "크롤러 설정 또는 DB 연결을 초기화하지 못했습니다.",
        }
        raise CrawlerRunError(result) from error

    result = None
    run_error = None
    try:
        with PoliteClient() as client, httpx.Client() as api:
            result = run(
                sites=sites,
                mode=mode,
                max_detail=max_detail,
                max_register=max_register,
                client=client,
                raw=raw,
                engine=engine,
                api=api,
                key=key,
                api_url=api_url,
                state_path=state_path,
            )
    except CrawlerRunError as error:
        run_error = error
    except Exception as error:
        result = _empty_run_result(sites)
        result["ok"] = False
        result["failure"] = {
            "stage": "client_init",
            "kind": "internal",
            "error_type": type(error).__name__,
            "summary": "크롤러 HTTP 클라이언트를 초기화하지 못했습니다.",
        }
        run_error = CrawlerRunError(result)

    cleanup_failures = []
    for close in (mongo.close, engine.dispose):
        try:
            close()
        except Exception as error:
            cleanup_failures.append(
                {
                    "stage": "runtime_cleanup",
                    "kind": "internal",
                    "error_type": type(error).__name__,
                    "summary": "크롤러 DB 연결을 정리하지 못했습니다.",
                }
            )
    if cleanup_failures:
        if run_error is not None:
            result = run_error.result
            result.setdefault("original_failure", result.get("failure"))
        elif result is None:
            result = _empty_run_result(sites)
        result["ok"] = False
        result["failure"] = cleanup_failures[0]
        if cleanup_failures[1:]:
            result["secondary_failures"] = [
                *result.get("secondary_failures", []),
                *cleanup_failures[1:],
            ]
        run_error = CrawlerRunError(result)
    if run_error is not None:
        raise run_error
    return result


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
        try:
            result = run_configured(
                sites=sites,
                mode=args.mode,
                max_detail=args.max_detail,
                max_register=max_register,
            )
        except CrawlerRunError as error:
            print(json.dumps(error.result, ensure_ascii=False))
            raise SystemExit(1) from error
        print(json.dumps(result, ensure_ascii=False))
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
