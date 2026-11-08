"""#99: 유형별 활성 공간 바닥선을 내부 API로 보충한다."""

import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402 -- backend 경로를 먼저 추가한다.
from app.core.db import close_databases, new_write_session  # noqa: E402
from app.schemas.internal import InternalVenueUpsert  # noqa: E402

from . import venue_supplement_repo
from .plan import GeneratorError, digest
from .storage import atomic_json
from .topup import CATEGORIES, NAMES, prepare, valid_candidate
from .venue_supplement_lock import LockUnavailable, VenuePipelineLock

DEFAULT_PROFILES = Path(__file__).with_name("venue_profiles.json")
DEFAULT_OUTPUT_ROOT = ROOT / "logs"
DEFAULT_API_URL = "http://127.0.0.1:8000/internal/venues"
RETRIES = 2


class SupplementError(GeneratorError):
    """실행·복구할 수 없는 공간 보충 오류."""


def _read_profiles(path):
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
        common = source["common"]
        profiles = source["profiles"]
        version = str(source["version"])
        if set(profiles) != set(CATEGORIES):
            raise ValueError("유형 구성이 다릅니다.")
        normalized = {}
        for category in CATEGORIES:
            row = {**common, **profiles[category]}
            row["facilities"] = sorted(
                set(common.get("facilities", [])) | set(profiles[category].get("facilities", []))
            )
            normalized[category] = row
        return normalized, version, hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise SupplementError(f"기본 프로필을 읽을 수 없습니다 ({type(error).__name__}).") from None


def _catalog_for_profiles(profiles, catalog):
    for category, profile in profiles.items():
        title = NAMES[category][0]
        body = {
            "source_site": "synthetic",
            "source_id": "profile-check",
            "name": f"{profile['sigungu']} {title} 시연용 공간",
            "category_code": category,
            **profile,
            "description": f"{profile['sigungu']}의 시연용 {title} 공간입니다.",
            "notice": "실제 업체의 예약 상품이 아닌 시연용 공간입니다.",
            "images": [NAMES[category][2]],
        }
        validated = InternalVenueUpsert.model_validate(body).model_dump()
        if validated["min_hours"] > validated["close_hour"] - validated["open_hour"]:
            raise SupplementError(f"{category}: 최소 이용시간이 영업시간보다 깁니다.")
        if category not in catalog["categories"]:
            raise SupplementError(f"{category}: 대상 DB에 유형 기초 데이터가 없습니다.")
        if (profile["sido"], profile["sigungu"]) not in catalog["regions"]:
            raise SupplementError(f"{category}: 대상 DB에 기본 프로필 지역이 없습니다.")
        unknown = set(profile["facilities"]) - catalog["facilities"]
        if unknown:
            raise SupplementError(f"{category}: 기본 프로필 시설이 대상 DB에 없습니다.")
    return profiles


def _target_identity(settings):
    if settings.db_write_url is None:
        raise SupplementError("DB_WRITE_URL 설정이 필요합니다.")
    url = settings.db_write_url.get_secret_value()
    from sqlalchemy.engine import make_url

    parsed = make_url(url)
    return digest({"host": parsed.host, "port": parsed.port, "database": parsed.database})


def _api_identity(value):
    from urllib.parse import urlsplit

    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise SupplementError("--api-url은 사용자 정보·질의값 없는 HTTP 주소여야 합니다.")
    return digest(
        {
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "port": parsed.port,
            "path": parsed.path,
        }
    )


def _code_identity():
    paths = (
        Path(__file__),
        Path(__file__).with_name("topup.py"),
        Path(__file__).with_name("venue_supplement_repo.py"),
        Path(__file__).with_name("venue_supplement_lock.py"),
        Path(__file__).with_name("plan.py"),
        Path(__file__).with_name("storage.py"),
        ROOT / "backend" / "app" / "schemas" / "internal.py",
        DEFAULT_PROFILES,
    )
    hasher = hashlib.sha256()
    for path in paths:
        hasher.update(path.relative_to(ROOT).as_posix().encode())
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _load_primary():
    with new_write_session() as db:
        snapshot = venue_supplement_repo.load_snapshot(db)
        catalog = venue_supplement_repo.load_catalog(db)
    if not catalog["categories"] or not catalog["regions"] or not catalog["facilities"]:
        raise SupplementError("유형·지역·시설 기초 데이터가 준비되지 않았습니다.")
    return snapshot, catalog


def _matches(existing, body):
    keys = (
        "source_id",
        "name",
        "category_code",
        "sido",
        "sigungu",
        "capacity_max",
        "price_per_hour",
        "min_hours",
        "open_hour",
        "close_hour",
        "description",
        "notice",
    )
    return all(existing.get(key) == body.get(key) for key in keys) and (
        sorted(existing.get("facilities", [])) == sorted(body["facilities"])
        and existing.get("images", []) == body["images"]
    )


def _find_source(source_id):
    with new_write_session() as db:
        return venue_supplement_repo.get_synthetic_source(db, source_id)


def _save_state(directory, state):
    atomic_json(directory / "state.json", state)


def _register(body, api, key, api_url):
    last_kind = "request_failed"
    for attempt in range(RETRIES + 1):
        try:
            response = api.post(
                api_url,
                headers={"X-Internal-Key": key},
                json=body,
                timeout=15,
            )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
            last_kind = "response_uncertain"
            existing = _find_source(body["source_id"])
            if existing is not None:
                if existing["is_active"] and _matches(existing, body):
                    return existing, None, attempt + 1
                return existing, "stored_result_mismatch", attempt + 1
            if attempt < RETRIES:
                continue
            return None, last_kind, attempt + 1

        if response.status_code not in {200, 201}:
            return None, f"http_{response.status_code}", attempt + 1
        try:
            result = response.json()
            venue_id = result.get("venue_id")
            ignored = result.get("ignored_facilities", [])
        except (ValueError, AttributeError):
            return None, "invalid_response", attempt + 1
        if not isinstance(venue_id, int) or venue_id <= 0 or not isinstance(ignored, list):
            return None, "invalid_response", attempt + 1
        if ignored:
            return (
                {"venue_id": venue_id, "ignored_facilities": ignored},
                "ignored_facilities",
                attempt + 1,
            )
        existing = _find_source(body["source_id"])
        if existing is None:
            return None, "stored_result_missing", attempt + 1
        if existing["venue_id"] != venue_id or not existing["is_active"] or not _matches(existing, body):
            return existing, "stored_result_mismatch", attempt + 1
        return existing, None, attempt + 1
    return None, last_kind, RETRIES + 1


def _profile_plan(snapshot, catalog, profiles, *, target, seed, profile_version):
    active_counts = _summarize_counts(snapshot)
    for category, profile in profiles.items():
        if active_counts[category] >= target:
            continue
        has_candidate = any(
            row.get("category_code") == category
            and valid_candidate(row, catalog)
            for row in snapshot["venues"]
        )
        if not has_candidate:
            _catalog_for_profiles({category: profile}, catalog)
    return prepare(
        snapshot,
        target=target,
        seed=seed,
        profiles=profiles,
        catalog=catalog,
        profile_version=profile_version,
    )


def _summarize_counts(snapshot):
    counts = {category: 0 for category in CATEGORIES}
    for venue in snapshot["venues"]:
        if venue.get("is_active") and venue.get("category_code") in counts:
            counts[venue["category_code"]] += 1
    return counts


def _report(run_id, seed, target, snapshot, plan, state, *, failures=None):
    active_counts = _summarize_counts(snapshot)
    supplement_counts = {
        category: sum(
            1
            for item in state["items"].values()
            if item.get("status") == "registered" and item.get("category_code") == category
        )
        for category in CATEGORIES
    }
    return {
        "run_id": run_id,
        "seed": seed,
        "target_per_category": target,
        "initial_active_counts": plan["active_counts"],
        "supplemented_by_category": supplement_counts,
        "active_counts": active_counts,
        "remaining_by_category": {
            category: max(0, target - active_counts[category]) for category in CATEGORIES
        },
        "source_ids": [
            source_id
            for source_id, item in state["items"].items()
            if item.get("status") == "registered"
        ],
        "failures": failures if failures is not None else plan["failures"],
        "complete": (
            all(active_counts[category] >= target for category in CATEGORIES)
            and not (failures if failures is not None else plan["failures"])
        ),
    }


def parser():
    command = argparse.ArgumentParser(description="#99 유형별 부족 공간 보충기")
    mode = command.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="등록 요청을 내부 API에 전송")
    mode.add_argument("--dry-run", action="store_true", help="DB 기준 계획만 확인")
    command.add_argument("--seed", type=int)
    command.add_argument("--target", type=int)
    command.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    command.add_argument("--api-url", default=DEFAULT_API_URL)
    command.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    command.add_argument("--save-plan", action="store_true")
    command.add_argument("--resume", metavar="RUN_ID")
    return command


def execute(args):
    settings = get_settings()
    profiles, profile_version, profile_sha = _read_profiles(args.profiles)
    target = args.target if args.target is not None else 6
    if target < 0:
        raise SupplementError("--target는 0 이상이어야 합니다.")
    if args.resume and not args.apply:
        raise SupplementError("--resume은 --apply와 함께 사용해야 합니다.")
    if args.save_plan and args.apply:
        raise SupplementError("--save-plan은 dry-run에서만 사용합니다.")
    if args.resume and (args.seed is not None or args.target is not None):
        raise SupplementError("재개할 때 seed와 목표는 기존 실행 기록에서 불러옵니다.")

    if args.resume:
        try:
            run_id = str(uuid.UUID(args.resume))
        except ValueError:
            raise SupplementError("재개 ID 형식이 올바르지 않습니다.") from None
        directory = args.output_root / f"venue-supplement-{run_id}"
        manifest_path = directory / "manifest.json"
        plan_path = directory / "plan.json"
        state_path = directory / "state.json"
        if not manifest_path.is_file() or not plan_path.is_file() or not state_path.is_file():
            raise SupplementError("재개에 필요한 manifest, plan, state 파일이 없습니다.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest["profile_sha256"] != profile_sha
            or manifest["code_sha256"] != _code_identity()
            or manifest["target_sha256"] != _target_identity(settings)
            or manifest["api_target_sha256"] != _api_identity(args.api_url)
        ):
            raise SupplementError("프로필·코드·대상 DB가 기존 계획과 다릅니다.")
        seed = manifest["seed"]
        target = manifest["target_per_category"]
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if manifest.get("run_id") != run_id or state.get("run_id") != run_id:
            raise SupplementError("state.json의 실행 ID가 manifest와 다릅니다.")
    else:
        seed = args.seed
        if seed is None:
            seed = int.from_bytes(os.urandom(4), "big")
        if seed < 0:
            raise SupplementError("seed는 0 이상이어야 합니다.")
        run_id = str(uuid.uuid4())
        directory = args.output_root / f"venue-supplement-{run_id}"
        snapshot, catalog = _load_primary()
        plan = _profile_plan(
            snapshot,
            catalog,
            profiles,
            target=target,
            seed=seed,
            profile_version=profile_version,
        )
        manifest = {
            "run_id": run_id,
            "seed": seed,
            "target_per_category": target,
            "profile_version": profile_version,
            "profile_sha256": profile_sha,
            "code_sha256": _code_identity(),
            "target_sha256": _target_identity(settings),
            "api_target_sha256": _api_identity(args.api_url),
        }
        state = {
            "run_id": run_id,
            "items": {
                request["source_id"]: {
                    "category_code": request["category_code"],
                    "status": "pending",
                    "attempts": 0,
                }
                for request in plan["requests"]
            },
        }
        if not args.apply and not args.save_plan:
            planned_by_category = {
                category: sum(
                    request["category_code"] == category for request in plan["requests"]
                )
                for category in CATEGORIES
            }
            return {
                "mode": "dry-run",
                "run_id": run_id,
                "seed": seed,
                "target_per_category": target,
                **plan,
                "planned_by_category": planned_by_category,
                "complete": not plan["failures"]
                and all(
                    plan["active_counts"][category] + planned_by_category[category] >= target
                    for category in CATEGORIES
                ),
            }
        directory.mkdir(parents=True, exist_ok=False)
        atomic_json(directory / "manifest.json", manifest)
        atomic_json(directory / "plan.json", plan)
        _save_state(directory, state)
        if not args.apply:
            planned_by_category = {
                category: sum(
                    request["category_code"] == category for request in plan["requests"]
                )
                for category in CATEGORIES
            }
            return {
                "mode": "dry-run",
                "run_id": run_id,
                "seed": seed,
                "target_per_category": target,
                "plan_path": str(directory / "plan.json"),
                **plan,
                "complete": not plan["failures"]
                and all(
                    plan["active_counts"][category] + planned_by_category[category] >= target
                    for category in CATEGORIES
                ),
            }

    snapshot, _catalog = _load_primary()
    failures = dict(plan["failures"])
    fatal_error = None
    api_key = (
        settings.internal_api_key.get_secret_value() if settings.internal_api_key else ""
    )
    if plan["requests"]:
        if not api_key:
            raise SupplementError("INTERNAL_API_KEY 설정이 필요합니다.")
        with httpx.Client(follow_redirects=False) as api:
            for body in plan["requests"]:
                item = state["items"][body["source_id"]]
                snapshot, _catalog = _load_primary()
                if item["status"] == "registered":
                    existing = _find_source(body["source_id"])
                    if existing is None or not existing["is_active"] or not _matches(existing, body):
                        failures[body["category_code"]] = "saved_result_mismatch"
                        fatal_error = "saved_result_mismatch"
                        break
                    continue

                existing = _find_source(body["source_id"])
                active_count = _summarize_counts(snapshot)[body["category_code"]]
                if existing is not None:
                    if existing["is_active"]:
                        if _matches(existing, body):
                            item.update(status="registered", venue_id=existing["venue_id"])
                            _save_state(directory, state)
                            continue
                        failures[body["category_code"]] = "source_id_conflict"
                        fatal_error = "source_id_conflict"
                        _save_state(directory, state)
                        break
                    if active_count >= target:
                        item.update(status="skipped", skip_reason="현재 활성 수가 목표에 도달")
                        _save_state(directory, state)
                        continue
                    if not existing["is_active"]:
                        item.update(status="failed", failure="기존 비활성 출처 ID 충돌")
                        failures[body["category_code"]] = "비활성 공간은 재활성화하지 않았습니다."
                        _save_state(directory, state)
                        continue

                if active_count >= target:
                    item.update(status="skipped", skip_reason="현재 활성 수가 목표에 도달")
                    _save_state(directory, state)
                    continue

                item.update(status="in_flight", attempts=item["attempts"] + 1)
                _save_state(directory, state)
                existing, failure, attempts = _register(
                    body,
                    api,
                    api_key,
                    args.api_url,
                )
                item["attempts"] += attempts - 1
                if failure == "ignored_facilities":
                    item.update(
                        status="failed",
                        failure=failure,
                        venue_id=existing["venue_id"],
                        ignored_facilities=existing["ignored_facilities"],
                    )
                    failures[body["category_code"]] = "내부 API가 일부 시설을 제외했습니다."
                    _save_state(directory, state)
                    fatal_error = "ignored_facilities"
                    break
                if failure:
                    item.update(status="uncertain" if failure == "response_uncertain" else "failed")
                    item["failure"] = failure
                    failures[body["category_code"]] = failure
                    _save_state(directory, state)
                    fatal_error = failure
                    break
                item.update(status="registered", venue_id=existing["venue_id"])
                _save_state(directory, state)
                snapshot, _catalog = _load_primary()

    snapshot, _catalog = _load_primary()
    report = _report(run_id, seed, target, snapshot, plan, state, failures=failures)
    report["fatal_error"] = fatal_error
    report["mode"] = "apply"
    atomic_json(directory / "report.json", report)
    return report


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.apply or args.save_plan:
            with VenuePipelineLock():
                result = execute(args)
        else:
            result = execute(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if result.get("complete", False) else 1
    except LockUnavailable as error:
        print(f"공간 보충 중단: {error}", file=sys.stderr)
        return 1
    except SupplementError as error:
        print(f"공간 보충 중단: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(
            f"공간 보충 중단 ({type(error).__name__}). 대상 설정과 실행 기록을 확인하세요.",
            file=sys.stderr,
        )
        return 1
    finally:
        close_databases()


if __name__ == "__main__":
    raise SystemExit(main())
