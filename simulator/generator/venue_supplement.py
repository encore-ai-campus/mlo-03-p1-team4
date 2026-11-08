"""#99 크롤링 결과 기준으로 synthetic 공간을 계획·등록·재개한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import httpx  # noqa: E402 -- standalone CLI adds backend to sys.path first
from pydantic import ValidationError  # noqa: E402 -- standalone CLI adds backend to sys.path first

from app.core.clock import get_now  # noqa: E402 -- standalone CLI imports app from backend
from app.core.config import get_settings  # noqa: E402 -- standalone CLI imports app from backend
from app.core.db import (  # noqa: E402 -- standalone CLI imports app from backend
    close_databases,
    get_engine,
    new_write_session,
)
from app.repositories import catalog_repo, venue_repo  # noqa: E402 -- standalone CLI imports app from backend
from app.schemas.internal import InternalVenueRead, InternalVenueUpsert  # noqa: E402 -- standalone CLI imports app from backend
from crawler.preprocess import ART_IMAGES, CATEGORY_NAMES, SeedMaps  # noqa: E402 -- standalone CLI imports app from backend
from simulator.generator.plan import CATEGORIES, GeneratorError, digest  # noqa: E402 -- bootstrap above
from simulator.generator.storage import atomic_json  # noqa: E402 -- bootstrap above
from simulator.generator.venue_pipeline_lock import venue_pipeline_lock  # noqa: E402 -- bootstrap above

PROFILE_PATH = Path(__file__).with_name("venue_profiles.json")
DEFAULT_OUTPUT_ROOT = ROOT / "logs"
API_URL = "http://127.0.0.1:8000/internal/venues"
CRAWL_SOURCES = {"spacecloud", "shareit"}
SUPPLEMENT_SOURCE = "synthetic"


def validate_counts(value: object) -> dict[str, int]:
    """크롤러가 반환한 HTTP 201 유형별 건수만 허용한다."""
    if isinstance(value, dict) and "newly_registered_by_category" in value:
        value = value["newly_registered_by_category"]
    if not isinstance(value, dict) or set(value) != set(CATEGORIES):
        raise GeneratorError("유형별 신규 등록 건수에 다섯 유형이 모두 있어야 합니다.")
    counts = {}
    for category in CATEGORIES:
        count = value[category]
        if type(count) is not int or count < 0:
            raise GeneratorError("신규 등록 건수는 0 이상의 정수여야 합니다.")
        counts[category] = count
    return counts


def read_crawler_counts(path: Path) -> dict[str, int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise GeneratorError("크롤러 결과 JSON을 읽지 못했습니다.") from None
    if not isinstance(data, dict):
        raise GeneratorError("크롤러 결과 JSON 형식이 올바르지 않습니다.")
    return validate_counts(data)


def _profile_fields(category: str, raw: object, common: object, maps: SeedMaps) -> dict | None:
    if not isinstance(raw, dict) or not isinstance(common, dict):
        return None
    try:
        facilities = list(dict.fromkeys([*common["facilities"], *raw["facilities"]]))
        images = list(raw["images"])
        if (
            raw["name"] != CATEGORY_NAMES[category]
            or (raw["sido"], raw["sigungu"]) not in maps.regions
            or any(name not in maps.facilities for name in facilities)
            or not images
            or any(image not in ART_IMAGES[category] for image in images)
        ):
            return None
        fields = {
            "name": raw["name"],
            "sido": raw["sido"],
            "sigungu": raw["sigungu"],
            "capacity_max": raw["capacity_max"],
            "price_per_hour": raw["price_per_hour"],
            "min_hours": raw["min_hours"],
            "open_hour": common["open_hour"],
            "close_hour": common["close_hour"],
            "feature": raw["feature"],
            "facilities": facilities,
            "images": images,
        }
        # 프로필도 같은 API 스키마와 DB 제약으로 확인한다.
        sample = _payload(category, fields, "profile-check", 1, images[0])
        InternalVenueUpsert.model_validate(sample)
        return fields
    except (KeyError, TypeError, ValueError, ValidationError):
        return None


def load_profiles(path: Path = PROFILE_PATH) -> tuple[dict, str, dict[str, dict]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise GeneratorError("공간 보충 프로필을 읽지 못했습니다.") from None
    if (
        not isinstance(document, dict)
        or type(document.get("version")) is not int
        or document.get("version") != 1
        or type(document.get("target_per_category")) is not int
        or document["target_per_category"] != 6
        or not isinstance(document.get("categories"), dict)
    ):
        raise GeneratorError("공간 보충 프로필의 버전 또는 유형 목표가 올바르지 않습니다.")
    try:
        maps = SeedMaps.load()
    except Exception:
        raise GeneratorError("로컬 유형·지역·시설 seed를 읽지 못했습니다.") from None
    common = document.get("common")
    valid = {
        category: fields
        for category in CATEGORIES
        if (fields := _profile_fields(category, document["categories"].get(category), common, maps))
        is not None
    }
    return document, digest(document), valid


def _valid_reference(item: object, category: str, maps: SeedMaps) -> bool:
    if not isinstance(item, dict) or item.get("category_code") != category:
        return False
    if item.get("source_site") not in CRAWL_SOURCES or type(item.get("venue_id")) is not int:
        return False
    if not item.get("source_id") or (item.get("sido"), item.get("sigungu")) not in maps.regions:
        return False
    integer_fields = (
        "capacity_max",
        "price_per_hour",
        "min_hours",
        "open_hour",
        "close_hour",
    )
    if any(type(item.get(field)) is not int for field in integer_fields):
        return False
    if not (
        1 <= item["capacity_max"] <= 32767
        and 0 < item["price_per_hour"] <= 2147483647
        and 9 <= item["open_hour"] <= 22
        and 10 <= item["close_hour"] <= 23
        and item["close_hour"] > item["open_hour"]
        and 1 <= item["min_hours"] <= min(4, item["close_hour"] - item["open_hour"])
    ):
        return False
    facilities = item.get("facilities")
    return (
        isinstance(facilities, list)
        and bool(facilities)
        and all(isinstance(name, str) and name in maps.facilities for name in facilities)
    )


def _payload(category: str, fields: dict, run_id: str, ordinal: int, image: str) -> dict:
    source_id = (
        "sup-"
        + hashlib.sha256(
            f"spacecube-venue-supplement:{run_id}:{category}:{ordinal}".encode()
        ).hexdigest()[:32]
    )
    name = f"{fields['sigungu']} {fields['feature']} {fields['name']} {ordinal:02d}"
    payload = {
        "source_site": SUPPLEMENT_SOURCE,
        "source_id": source_id,
        "name": name,
        "category_code": category,
        "sido": fields["sido"],
        "sigungu": fields["sigungu"],
        "capacity_max": fields["capacity_max"],
        "price_per_hour": fields["price_per_hour"],
        "min_hours": fields["min_hours"],
        "open_hour": fields["open_hour"],
        "close_hour": fields["close_hour"],
        "description": f"공간큐브에서 예약할 수 있는 {fields['name']} 공간입니다.",
        "notice": "시설과 이용 시간은 예약 전에 확인해 주세요.",
        "facilities": sorted(set(fields["facilities"])),
        "images": [image],
    }
    # 보호: 생성기와 API 계약이 달라지면 계획을 저장하지 않는다.
    try:
        InternalVenueUpsert.model_validate(payload)
    except ValidationError:
        raise GeneratorError("생성한 공간 정보가 내부 API 계약을 만족하지 않습니다.") from None
    return payload


def build_plan(
    newly_registered_by_category: dict,
    references: list[dict],
    profiles: dict,
    run_id: str,
    *,
    profile_hash: str | None = None,
) -> dict:
    """HTTP 201 건수와 이번 실행 ID로 재현 가능한 보충 계획을 만든다."""
    counts = validate_counts(newly_registered_by_category)
    if not isinstance(references, list):
        raise GeneratorError("공간 보충 기준 공간 목록이 올바르지 않습니다.")
    if not run_id or len(run_id) > 64:
        raise GeneratorError("보충 실행 ID가 올바르지 않습니다.")
    try:
        maps = SeedMaps.load()
    except Exception:
        raise GeneratorError("로컬 유형·지역·시설 seed를 읽지 못했습니다.") from None

    common = profiles.get("common", {}) if isinstance(profiles, dict) else {}
    by_category = profiles.get("categories", {}) if isinstance(profiles, dict) else {}
    valid_profiles = {
        category: fields
        for category in CATEGORIES
        if (fields := _profile_fields(category, by_category.get(category), common, maps))
        is not None
    }
    items = []
    planned = dict.fromkeys(CATEGORIES, 0)
    selected_references = {}
    category_failures = {}
    target = 6

    for category in CATEGORIES:
        needed = max(0, target - counts[category])
        pool = [
            reference for reference in references if _valid_reference(reference, category, maps)
        ]
        selected_references[category] = len(pool)
        if needed and not pool and category not in valid_profiles:
            category_failures[category] = "유효한 크롤링 기준 공간과 기본 프로필이 없습니다."
            continue
        if not needed:
            continue
        for ordinal in range(1, needed + 1):
            profile = valid_profiles.get(category)
            if pool:
                selector = int(
                    digest({"run_id": run_id, "category": category, "ordinal": ordinal})[:16],
                    16,
                )
                reference = pool[selector % len(pool)]
                fields = {
                    "name": CATEGORY_NAMES[category],
                    "feature": profile["feature"] if profile else CATEGORY_NAMES[category],
                    "sido": reference["sido"],
                    "sigungu": reference["sigungu"],
                    "capacity_max": reference["capacity_max"],
                    "price_per_hour": reference["price_per_hour"],
                    "min_hours": reference["min_hours"],
                    "open_hour": reference["open_hour"],
                    "close_hour": reference["close_hour"],
                    "facilities": list(reference["facilities"]),
                }
                reference_id = reference["venue_id"]
                image_pool = profile["images"] if profile else ART_IMAGES[category]
            else:
                fields = profile
                reference_id = None
                image_pool = profile["images"]
            image = image_pool[(ordinal - 1) % len(image_pool)]
            try:
                payload = _payload(category, fields, run_id, ordinal, image)
            except GeneratorError:
                category_failures[category] = "유형별 공간 계획을 만들지 못했습니다."
                break
            items.append(
                {
                    "item_id": f"{category}:{ordinal}",
                    "category_code": category,
                    "ordinal": ordinal,
                    "reference_venue_id": reference_id,
                    "payload": payload,
                }
            )
            planned[category] += 1

    result = {
        "version": 1,
        "run_id": run_id,
        "profile_sha256": profile_hash or digest(profiles),
        "target_per_category": target,
        "newly_registered_by_category": counts,
        "planned_by_category": planned,
        "reference_count_by_category": selected_references,
        "category_failures": category_failures,
        "items": items,
    }
    result["plan_sha256"] = digest(result)
    return result


def read_references() -> list[dict]:
    try:
        with new_write_session() as db:
            return venue_repo.list_supplement_references(db)
    except Exception:
        raise GeneratorError("primary DB에서 크롤링 기준 공간을 읽지 못했습니다.") from None


def _target_identity() -> str:
    try:
        url = get_engine("write").url
        return digest({"host": url.host, "port": url.port, "database": url.database})
    except Exception:
        raise GeneratorError("primary DB 대상 정보를 확인하지 못했습니다.") from None


def _code_identity() -> str:
    files = [
        *Path(__file__).parent.glob("*.py"),
        PROFILE_PATH,
        ROOT / "crawler" / "crawl_venues.py",
        ROOT / "crawler" / "preprocess.py",
        ROOT / "backend" / "app" / "repositories" / "venue_repo.py",
        ROOT / "backend" / "app" / "schemas" / "internal.py",
    ]
    hasher = hashlib.sha256()
    for path in sorted(set(files)):
        if path.exists():
            hasher.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _run_directory(output_root: Path, run_id: str) -> Path:
    if not run_id or any(
        char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for char in run_id
    ):
        raise GeneratorError("실행 ID에 사용할 수 없는 문자가 있습니다.")
    return output_root / f"venue-supplement-{run_id}"


def create_run(
    *,
    output_root: Path,
    run_id: str,
    counts: dict,
    references: list[dict],
    profile_document: dict,
    profile_hash: str,
    parent_pipeline_id: str | None = None,
) -> tuple[Path, dict]:
    directory = _run_directory(output_root, run_id)
    if directory.exists():
        raise GeneratorError("같은 보충 실행 기록이 이미 있습니다.")
    plan = build_plan(counts, references, profile_document, run_id, profile_hash=profile_hash)
    target_identity = _target_identity()
    code_sha256 = _code_identity()
    directory.mkdir(parents=True)
    manifest = {
        "version": 1,
        "run_id": run_id,
        "created_at": get_now().isoformat(),
        "target_identity": target_identity,
        "code_sha256": code_sha256,
        "profile_sha256": profile_hash,
        "reference_sha256": digest(
            [
                {
                    key: reference.get(key)
                    for key in (
                        "venue_id",
                        "source_site",
                        "category_code",
                        "sido",
                        "sigungu",
                        "capacity_max",
                        "price_per_hour",
                        "min_hours",
                        "open_hour",
                        "close_hour",
                        "facilities",
                    )
                }
                for reference in references
                if isinstance(reference, dict)
            ]
        ),
        "parent_pipeline_id": parent_pipeline_id,
        "plan_sha256": plan["plan_sha256"],
    }
    state = {
        "status": "planned",
        "items": {
            item["item_id"]: {
                "status": "planned",
                "attempts": 0,
                "category_code": item["category_code"],
            }
            for item in plan["items"]
        },
    }
    atomic_json(directory / "manifest.json", manifest)
    atomic_json(directory / "plan.json", plan)
    atomic_json(directory / "state.json", state)
    return directory, plan


def _payload_matches(snapshot: dict | None, payload: dict) -> bool:
    if snapshot is None or not snapshot.get("is_active"):
        return False
    fields = (
        "source_site",
        "source_id",
        "name",
        "description",
        "notice",
        "category_code",
        "sido",
        "sigungu",
        "capacity_max",
        "price_per_hour",
        "min_hours",
        "open_hour",
        "close_hour",
    )
    if any(snapshot.get(field) != payload.get(field) for field in fields):
        return False
    return (
        sorted(snapshot.get("facilities", [])) == sorted(payload["facilities"])
        and list(snapshot.get("images", [])) == payload["images"]
    )


def _check_catalog(plan: dict) -> None:
    try:
        with new_write_session() as db:
            for item in plan["items"]:
                body = item["payload"]
                if catalog_repo.get_category_id(db, body["category_code"]) is None:
                    raise GeneratorError("유형 seed가 내부 API 기준과 다릅니다.")
                if catalog_repo.get_region_id(db, body["sido"], body["sigungu"]) is None:
                    raise GeneratorError("지역 seed가 내부 API 기준과 다릅니다.")
                for name in body["facilities"]:
                    if catalog_repo.get_facility_id(db, name) is None:
                        raise GeneratorError("시설 seed가 내부 API 기준과 다릅니다.")
    except GeneratorError:
        raise
    except Exception:
        raise GeneratorError("primary DB의 유형·지역·시설 seed를 확인하지 못했습니다.") from None


def check_profile_catalog() -> None:
    """외부 크롤링 전에 기본 프로필이 primary 기준 정보와 맞는지 확인한다."""
    _, _, valid_profiles = load_profiles()
    if not valid_profiles:
        raise GeneratorError("검증 가능한 기본 공간 프로필이 없습니다.")
    items = [
        {
            "payload": _payload(
                category,
                valid_profiles[category],
                "catalog-preflight",
                1,
                valid_profiles[category]["images"][0],
            )
        }
        for category in CATEGORIES
    ]
    _check_catalog({"items": items})


def _get_snapshot(payload: dict) -> dict | None:
    try:
        with new_write_session() as db:
            return venue_repo.get_source_snapshot(db, payload["source_site"], payload["source_id"])
    except Exception:
        raise GeneratorError("primary DB에서 공간 등록 결과를 대조하지 못했습니다.") from None


def _report(plan: dict, state: dict, *, status: str, failure: dict | None = None) -> dict:
    registered = dict.fromkeys(CATEGORIES, 0)
    outcomes = {}
    for item in plan["items"]:
        item_state = state["items"].get(item["item_id"], {})
        item_status = item_state.get("status", "planned")
        outcomes[item["item_id"]] = item_status
        if item_status in {"created", "reconciled"}:
            registered[item["category_code"]] += 1
    crawler_counts = plan["newly_registered_by_category"]
    remaining = {
        category: max(0, 6 - crawler_counts[category] - registered[category])
        for category in CATEGORIES
    }
    return {
        "run_id": plan["run_id"],
        "status": status,
        "target_per_category": 6,
        "newly_registered_by_category": crawler_counts,
        "planned_by_category": plan["planned_by_category"],
        "supplement_registered_by_category": registered,
        "remaining_to_target_by_category": remaining,
        "category_failures": plan["category_failures"],
        "item_status": outcomes,
        "failure": failure,
    }


def _save_report(directory: Path, plan: dict, state: dict, status: str, failure=None) -> None:
    state["status"] = status
    atomic_json(directory / "state.json", state)
    atomic_json(directory / "report.json", _report(plan, state, status=status, failure=failure))


def _fail_run(directory: Path, plan: dict, state: dict, reason: str) -> dict:
    failure = {"reason": reason}
    _save_report(directory, plan, state, "failed", failure)
    return _report(plan, state, status="failed", failure=failure)


def _apply_locked(directory: Path, api_url: str) -> dict:
    try:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        plan = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
        state = json.loads((directory / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise GeneratorError("보충 실행 기록이 불완전해 재개할 수 없습니다.") from None
    if (
        manifest.get("run_id") != plan.get("run_id")
        or manifest.get("plan_sha256") != plan.get("plan_sha256")
        or digest({key: value for key, value in plan.items() if key != "plan_sha256"})
        != plan.get("plan_sha256")
    ):
        raise GeneratorError("저장된 보충 계획이 manifest와 다릅니다.")
    if manifest.get("profile_sha256") != plan.get("profile_sha256"):
        raise GeneratorError("저장된 보충 프로필 지문이 manifest와 다릅니다.")
    try:
        target_identity = _target_identity()
    except GeneratorError:
        return _fail_run(directory, plan, state, "primary_db_unavailable")
    if manifest.get("target_identity") != target_identity:
        return _fail_run(directory, plan, state, "db_target_changed")
    if manifest.get("code_sha256") != _code_identity():
        return _fail_run(directory, plan, state, "code_changed")
    settings = get_settings()
    if settings.internal_api_key is None:
        return _fail_run(directory, plan, state, "internal_api_key_missing")
    if settings.synthetic_api_key is None:
        return _fail_run(directory, plan, state, "synthetic_api_key_missing")
    try:
        url = httpx.URL(api_url)
    except httpx.InvalidURL:
        return _fail_run(directory, plan, state, "invalid_internal_api_url")
    if (
        url.scheme not in {"http", "https"}
        or not url.host
        or url.username
        or url.password
        or url.query
    ):
        return _fail_run(directory, plan, state, "invalid_internal_api_url")
    try:
        _check_catalog(plan)
    except GeneratorError:
        return _fail_run(directory, plan, state, "catalog_preflight_failed")
    headers = {
        "X-Internal-Key": settings.internal_api_key.get_secret_value(),
        "X-Synthetic": "1",
        "X-Synthetic-Key": settings.synthetic_api_key.get_secret_value(),
    }
    failure = None
    try:
        with httpx.Client(timeout=30) as client:
            for item in plan["items"]:
                item_id = item["item_id"]
                body = item["payload"]
                item_state = state["items"].setdefault(
                    item_id,
                    {"status": "planned", "attempts": 0, "category_code": item["category_code"]},
                )
                previous_status = item_state.get("status")
                if previous_status in {"created", "reconciled"}:
                    continue
                if previous_status == "failed":
                    failure = item_state.get("failure") or {
                        "item_id": item_id,
                        "category_code": item["category_code"],
                        "reason": "previous_attempt_failed",
                    }
                    return _report(plan, state, status="failed", failure=failure)
                recovery_retry = previous_status in {"posting", "uncertain"}
                if recovery_retry:
                    snapshot = _get_snapshot(body)
                    if snapshot is not None:
                        if not _payload_matches(snapshot, body):
                            failure = {
                                "item_id": item_id,
                                "category_code": item["category_code"],
                                "reason": "source_conflict",
                            }
                            item_state["status"] = "failed"
                            _save_report(directory, plan, state, "failed", failure)
                            return _report(plan, state, status="failed", failure=failure)
                        item_state.update(status="reconciled", venue_id=snapshot["venue_id"])
                        atomic_json(directory / "state.json", state)
                        atomic_json(
                            directory / "report.json",
                            _report(plan, state, status="running"),
                        )
                        continue

                item_state["attempts"] = item_state.get("attempts", 0) + 1
                item_state["status"] = "posting"
                atomic_json(directory / "state.json", state)
                try:
                    response = client.post(api_url, headers=headers, json=body)
                except httpx.RequestError:
                    item_state["status"] = "uncertain"
                    failure = {
                        "item_id": item_id,
                        "category_code": item["category_code"],
                        "reason": "no_response",
                    }
                    _save_report(directory, plan, state, "uncertain", failure)
                    return _report(plan, state, status="uncertain", failure=failure)

                if response.status_code == 201:
                    try:
                        result = InternalVenueRead.model_validate(response.json())
                    except (ValueError, ValidationError):
                        item_state["status"] = "uncertain"
                        failure = {
                            "item_id": item_id,
                            "category_code": item["category_code"],
                            "reason": "invalid_created_response",
                        }
                        _save_report(directory, plan, state, "uncertain", failure)
                        return _report(plan, state, status="uncertain", failure=failure)
                    if result.ignored_facilities:
                        item_state["status"] = "uncertain"
                        failure = {
                            "item_id": item_id,
                            "category_code": item["category_code"],
                            "reason": "ignored_facility",
                        }
                        _save_report(directory, plan, state, "uncertain", failure)
                        return _report(plan, state, status="uncertain", failure=failure)
                    item_state.update(status="created", venue_id=result.venue_id)
                elif response.status_code == 200 and recovery_retry:
                    snapshot = _get_snapshot(body)
                    if _payload_matches(snapshot, body):
                        item_state.update(status="reconciled", venue_id=snapshot["venue_id"])
                    else:
                        item_state["status"] = "failed"
                        failure = {
                            "item_id": item_id,
                            "category_code": item["category_code"],
                            "reason": "duplicate_response_mismatch",
                        }
                        _save_report(directory, plan, state, "failed", failure)
                        return _report(plan, state, status="failed", failure=failure)
                else:
                    reason = (
                        "server_error_uncertain" if response.status_code >= 500 else "api_rejected"
                    )
                    item_state["status"] = "uncertain" if response.status_code >= 500 else "failed"
                    failure = {
                        "item_id": item_id,
                        "category_code": item["category_code"],
                        "reason": reason,
                        "status_code": response.status_code,
                    }
                    item_state["failure"] = failure
                    status = "uncertain" if response.status_code >= 500 else "failed"
                    _save_report(directory, plan, state, status, failure)
                    return _report(plan, state, status=status, failure=failure)

                atomic_json(directory / "state.json", state)
                atomic_json(directory / "report.json", _report(plan, state, status="running"))
    except GeneratorError:
        raise
    except Exception:
        return _fail_run(directory, plan, state, "execution_error")

    report = _report(plan, state, status="completed")
    _save_report(directory, plan, state, "completed")
    return report


def apply_run(directory: Path, *, api_url: str = API_URL, lock_held: bool = False) -> dict:
    if lock_held:
        return _apply_locked(directory, api_url)
    with venue_pipeline_lock():
        return _apply_locked(directory, api_url)


def dry_run(counts: dict, references: list[dict], profile_document: dict, run_id: str) -> dict:
    profile_hash = digest(profile_document)
    return build_plan(counts, references, profile_document, run_id, profile_hash=profile_hash)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="#99 크롤링 공간 부족분 보충기")
    parser.add_argument("--mode", choices=("dry-run", "apply", "resume"), required=True)
    parser.add_argument("--crawler-result", type=Path, help="유형별 HTTP 201 건수가 담긴 JSON")
    parser.add_argument("--run-id", help="--resume할 venue-supplement 실행 ID")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--api-url", default=API_URL)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.mode == "resume":
            if not args.run_id or args.crawler_result:
                parser.error("--resume에는 --run-id만 사용하세요.")
            directory = _run_directory(args.output_root, args.run_id)
            report = apply_run(directory, api_url=args.api_url)
        else:
            if not args.crawler_result or args.run_id:
                parser.error("--dry-run/--apply에는 --crawler-result만 사용하세요.")
            counts = read_crawler_counts(args.crawler_result)
            profile_document, profile_hash, _ = load_profiles()
            run_id = str(uuid4())
            if args.mode == "dry-run":
                report = dry_run(counts, read_references(), profile_document, run_id)
            else:
                with venue_pipeline_lock():
                    directory, _ = create_run(
                        output_root=args.output_root,
                        run_id=run_id,
                        counts=counts,
                        references=read_references(),
                        profile_document=profile_document,
                        profile_hash=profile_hash,
                    )
                    report = apply_run(directory, api_url=args.api_url, lock_held=True)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if report.get("status", "planned") in {"planned", "completed"} else 1
    except GeneratorError as error:
        print(f"실행 중단: {error}", file=sys.stderr)
        return 2
    finally:
        close_databases()


if __name__ == "__main__":
    raise SystemExit(main())
