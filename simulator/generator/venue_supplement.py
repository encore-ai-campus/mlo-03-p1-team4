"""#99: 실행별 유형 신규 등록 목표를 내부 API로 보충한다."""

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

from . import venue_supplement_repo  # noqa: E402 -- backend 경로를 먼저 추가한다.
from .plan import GeneratorError, digest  # noqa: E402
from .storage import atomic_json  # noqa: E402
from .topup import (  # noqa: E402
    CATEGORIES,
    prepare,
    validate_newly_registered_by_category,
)
from .venue_supplement_lock import LockUnavailable, VenuePipelineLock  # noqa: E402

DEFAULT_PROFILES = Path(__file__).with_name("venue_profiles.json")
DEFAULT_OUTPUT_ROOT = ROOT / "logs"
DEFAULT_API_URL = "http://127.0.0.1:8000/internal/venues"
RETRIES = 2
POLICY_VERSION = "execution-new-count-v2"


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
        catalog = venue_supplement_repo.load_catalog(db)
        missing = []
        missing_categories = set(CATEGORIES) - catalog["categories"]
        if missing_categories:
            missing.append(f"공간 유형 누락: {', '.join(sorted(missing_categories))}")
        if not catalog["regions"]:
            missing.append("지역 기초 데이터 없음")
        if not catalog["facilities"]:
            missing.append("시설 기초 데이터 없음")
        if missing:
            raise SupplementError(f"필수 기초 데이터가 준비되지 않았습니다 ({'; '.join(missing)}).")
        snapshot = venue_supplement_repo.load_snapshot(db)
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


def _reject_seed_reuse(output_root, seed):
    """저장된 새 실행과 seed가 겹치지 않게 한다."""
    for manifest_path in output_root.glob("venue-supplement-*/manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise SupplementError(
                "기존 실행 기록을 읽지 못해 seed 중복을 확인할 수 없습니다."
            ) from None
        if manifest.get("seed") == seed:
            raise SupplementError("새 실행에는 아직 사용하지 않은 seed를 지정해야 합니다.")


def _register(body, api, key, api_url, *, max_attempts=RETRIES + 1):
    last_kind = "request_failed"
    uncertain_attempt = False
    for attempt in range(max_attempts):
        try:
            response = api.post(
                api_url,
                headers={"X-Internal-Key": key},
                json=body,
                timeout=15,
            )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
            last_kind = "response_uncertain"
            uncertain_attempt = True
            existing = _find_source(body["source_id"])
            if existing is not None:
                if existing["is_active"] and _matches(existing, body):
                    return existing, None, attempt + 1, True
                return existing, "stored_result_mismatch", attempt + 1, False
            if attempt + 1 < max_attempts:
                continue
            return None, last_kind, attempt + 1, False

        if response.status_code not in {200, 201}:
            return None, f"http_{response.status_code}", attempt + 1, False
        try:
            result = response.json()
            venue_id = result.get("venue_id")
            ignored = result.get("ignored_facilities", [])
        except (ValueError, AttributeError):
            return None, "invalid_response", attempt + 1, False
        if not isinstance(venue_id, int) or venue_id <= 0 or not isinstance(ignored, list):
            return None, "invalid_response", attempt + 1, False
        if ignored:
            return (
                {"venue_id": venue_id, "ignored_facilities": ignored},
                "ignored_facilities",
                attempt + 1,
                False,
            )
        existing = _find_source(body["source_id"])
        if existing is None:
            return None, "stored_result_missing", attempt + 1, False
        if (
            existing["venue_id"] != venue_id
            or not existing["is_active"]
            or not _matches(existing, body)
        ):
            return existing, "stored_result_mismatch", attempt + 1, False
        created = response.status_code == 201 or uncertain_attempt
        if not created:
            return existing, "not_new_registration", attempt + 1, False
        return existing, None, attempt + 1, True
    return None, last_kind, max_attempts, False


def _profile_plan(
    snapshot,
    catalog,
    profiles,
    *,
    newly_registered_by_category,
    target,
    seed,
    profile_version,
):
    return prepare(
        snapshot,
        newly_registered_by_category=newly_registered_by_category,
        target=target,
        seed=seed,
        profiles=profiles,
        catalog=catalog,
        profile_version=profile_version,
    )


def _summarize_counts(snapshot):
    counts = dict.fromkeys(CATEGORIES, 0)
    for venue in snapshot["venues"]:
        if venue.get("is_active") and venue.get("category_code") in counts:
            counts[venue["category_code"]] += 1
    return counts


def _manual_summary(report):
    """수동 실행의 계획과 실제 성공을 구분해 시연용 요약을 만든다."""
    labels = {
        "studyroom": "스터디룸",
        "studio": "스튜디오",
        "cafe": "카페",
        "lectureroom": "강의실",
        "partyroom": "파티룸",
    }
    planned = report["completion_basis"] == "projected"
    title = "수동모드 보충 계획 (dry-run)" if planned else "수동모드 보충 결과"
    count_label = "보충 계획" if planned else "수동 보충 성공"
    counts = report["planned_by_category"] if planned else report["supplemented_by_category"]
    target = report["target_per_category"]
    lines = [title, f"실행 ID: {report['run_id']}", "크롤러 신규 등록: 미확인"]
    lines.extend(
        f"{labels[category]}: {count_label} {counts[category]}곳 / 목표 {target}곳"
        for category in CATEGORIES
    )
    lines.append(
        f"합계: {count_label} {sum(counts.values())}곳 / 목표 {target * len(CATEGORIES)}곳"
    )
    if planned:
        lines.append(f"실제 보충 성공: {sum(report['supplemented_by_category'].values())}곳")
    status_label = "계획 검증" if planned else "실행 결과"
    status = "완료" if report["complete"] else "미완료"
    lines.append(f"{status_label}: {status}")
    return "\n".join(lines)


def _report(run_id, seed, target, snapshot, plan, state, *, failures=None, planned=False):
    active_counts = _summarize_counts(snapshot)
    registered_counts = {
        category: sum(
            1
            for item in state["items"].values()
            if item.get("status") == "registered"
            and item.get("newly_created", False)
            and item.get("category_code") == category
        )
        for category in CATEGORIES
    }
    planned_counts = {
        category: sum(request["category_code"] == category for request in plan["requests"])
        for category in CATEGORIES
    }
    crawler_counts = plan["newly_registered_by_category"]
    total_new_by_category = {
        category: (crawler_counts[category] if crawler_counts is not None else 0)
        + registered_counts[category]
        for category in CATEGORIES
    }
    remaining_by_category = {
        category: max(0, target - total_new_by_category[category]) for category in CATEGORIES
    }
    projected_total_by_category = {
        category: (crawler_counts[category] if crawler_counts is not None else 0)
        + planned_counts[category]
        for category in CATEGORIES
    }
    projected_remaining_by_category = {
        category: max(0, target - projected_total_by_category[category]) for category in CATEGORIES
    }
    completion_remaining = projected_remaining_by_category if planned else remaining_by_category
    result_failures = failures if failures is not None else plan["failures"]
    report = {
        "run_id": run_id,
        "seed": seed,
        "policy_version": POLICY_VERSION,
        "supplement_mode": plan["supplement_mode"],
        "target_per_category": target,
        "newly_registered_by_category": crawler_counts,
        "crawler_counts_provided": crawler_counts is not None,
        "initial_active_counts": plan["active_counts"],
        "supplemented_by_category": registered_counts,
        "planned_by_category": planned_counts,
        "total_newly_registered_by_category": total_new_by_category,
        "projected_total_by_category": projected_total_by_category,
        "active_counts": active_counts,
        "final_active_counts": active_counts,
        "remaining_by_category": remaining_by_category,
        "projected_remaining_by_category": projected_remaining_by_category,
        "completion_basis": "projected" if planned else "actual",
        "source_ids": [
            source_id
            for source_id, item in state["items"].items()
            if item.get("status") == "registered"
        ],
        "failures": result_failures,
        "complete": (
            all(remaining == 0 for remaining in completion_remaining.values())
            and not result_failures
        ),
    }
    if report["supplement_mode"] == "manual":
        report["summary_text"] = _manual_summary(report)
    return report


def parser():
    command = argparse.ArgumentParser(description="#99 유형별 부족 공간 보충기")
    mode = command.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="등록 요청을 내부 API에 전송")
    mode.add_argument("--dry-run", action="store_true", help="등록 계획만 확인")
    command.add_argument(
        "--manual",
        action="store_true",
        help="크롤러 결과 없이 유형별 6개씩 보충",
    )
    command.add_argument("--seed", type=int)
    command.add_argument("--target", type=int)
    command.add_argument(
        "--newly-registered-by-category",
        metavar="JSON",
        help="다섯 유형의 크롤러 HTTP 201 신규 등록 건수 JSON",
    )
    command.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    command.add_argument("--api-url", default=DEFAULT_API_URL)
    command.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    command.add_argument("--save-plan", action="store_true")
    command.add_argument("--resume", metavar="RUN_ID")
    return command


def _parse_newly_registered(raw):
    if raw is None:
        return None
    try:
        return validate_newly_registered_by_category(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        raise SupplementError(
            "--newly-registered-by-category에는 다섯 유형의 0 이상 정수 JSON이 필요합니다."
        ) from None


def execute(args):
    settings = get_settings()
    profiles, profile_version, profile_sha = _read_profiles(args.profiles)
    target = args.target if args.target is not None else 6
    if target < 0:
        raise SupplementError("--target는 0 이상이어야 합니다.")
    if args.manual and args.target is not None:
        raise SupplementError("수동 모드 목표는 유형별 6개로 고정됩니다.")
    if args.resume and not args.apply:
        raise SupplementError("--resume은 --apply와 함께 사용해야 합니다.")
    if args.save_plan and args.apply:
        raise SupplementError("--save-plan은 dry-run에서만 사용합니다.")
    if args.resume and (args.seed is not None or args.target is not None):
        raise SupplementError("재개할 때 seed와 목표는 기존 실행 기록에서 불러옵니다.")
    input_counts = _parse_newly_registered(args.newly_registered_by_category)
    if args.manual and input_counts is not None:
        raise SupplementError("수동 모드에는 크롤러 신규 등록 수를 입력할 수 없습니다.")

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
        if manifest.get("policy_version") != POLICY_VERSION:
            raise SupplementError(
                "이 실행 기록은 이전 보충 정책으로 만들어져 재개할 수 없습니다. 기존 기록은 보존됩니다."
            )
        supplement_mode = manifest.get("supplement_mode")
        if supplement_mode not in {"crawler", "manual"}:
            raise SupplementError("실행 기록의 보충 모드를 확인할 수 없습니다.")
        if args.manual and supplement_mode != "manual":
            raise SupplementError("기존 실행의 보충 모드와 재개 옵션이 다릅니다.")
        saved_counts = manifest.get("newly_registered_by_category")
        if supplement_mode == "manual":
            if saved_counts is not None or input_counts is not None:
                raise SupplementError("수동 실행 기록에는 크롤러 신규 등록 수가 없어야 합니다.")
            input_counts = None
            planning_counts = dict.fromkeys(CATEGORIES, 0)
        else:
            saved_counts = validate_newly_registered_by_category(saved_counts)
            if input_counts is not None and input_counts != saved_counts:
                raise SupplementError("재개 입력의 유형별 크롤러 실적이 기존 실행과 다릅니다.")
            input_counts = saved_counts
            planning_counts = saved_counts
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
        if (
            manifest.get("record_version") != 3
            or plan.get("record_version") != 3
            or plan.get("policy_version") != POLICY_VERSION
            or state.get("record_version") != 3
            or plan.get("supplement_mode") != supplement_mode
            or plan.get("newly_registered_by_category") != saved_counts
            or plan.get("planning_newly_registered_by_category") != planning_counts
            or plan.get("target_per_category") != target
            or (supplement_mode == "manual" and target != 6)
        ):
            raise SupplementError("재개 기록의 형식 또는 정책 버전이 올바르지 않습니다.")
        expected_items = {
            request["source_id"]: request["category_code"] for request in plan["requests"]
        }
        saved_items = state.get("items")
        if not isinstance(saved_items, dict) or set(saved_items) != set(expected_items):
            raise SupplementError("state.json의 처리 항목이 저장된 계획과 다릅니다.")
        if any(
            not isinstance(saved_items[source_id], dict)
            or saved_items[source_id].get("category_code") != category
            for source_id, category in expected_items.items()
        ):
            raise SupplementError("state.json의 유형별 처리 항목이 저장된 계획과 다릅니다.")
    else:
        supplement_mode = "manual" if args.manual else "crawler"
        if supplement_mode == "manual":
            planning_counts = dict.fromkeys(CATEGORIES, 0)
        elif input_counts is None:
            raise SupplementError("새 실행에는 유형별 크롤러 신규 등록 수 전체 매핑이 필요합니다.")
        else:
            planning_counts = input_counts
        seed = args.seed
        if seed is None:
            seed = int.from_bytes(os.urandom(4), "big")
        if seed < 0:
            raise SupplementError("seed는 0 이상이어야 합니다.")
        if args.apply or args.save_plan:
            _reject_seed_reuse(args.output_root, seed)
        run_id = str(uuid.UUID(args.run_id)) if getattr(args, "run_id", None) else str(uuid.uuid4())
        directory = args.output_root / f"venue-supplement-{run_id}"
        snapshot, catalog = _load_primary()
        plan = _profile_plan(
            snapshot,
            catalog,
            profiles,
            newly_registered_by_category=planning_counts,
            target=target,
            seed=seed,
            profile_version=profile_version,
        )
        plan["planning_newly_registered_by_category"] = plan["newly_registered_by_category"]
        plan["newly_registered_by_category"] = input_counts
        plan["supplement_mode"] = supplement_mode
        plan["record_version"] = 3
        plan["policy_version"] = POLICY_VERSION
        manifest = {
            "record_version": 3,
            "policy_version": POLICY_VERSION,
            "supplement_mode": supplement_mode,
            "run_id": run_id,
            "seed": seed,
            "target_per_category": target,
            "newly_registered_by_category": input_counts,
            "profile_version": profile_version,
            "profile_sha256": profile_sha,
            "code_sha256": _code_identity(),
            "target_sha256": _target_identity(settings),
            "api_target_sha256": _api_identity(args.api_url),
        }
        if getattr(args, "parent_pipeline_id", None):
            manifest["parent_pipeline_id"] = args.parent_pipeline_id
        state = {
            "record_version": 3,
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
            report = _report(run_id, seed, target, snapshot, plan, state, planned=True)
            return {
                **plan,
                **report,
                "mode": "dry-run",
            }
        directory.mkdir(parents=True, exist_ok=False)
        atomic_json(directory / "manifest.json", manifest)
        atomic_json(directory / "plan.json", plan)
        _save_state(directory, state)
        if not args.apply:
            report = _report(run_id, seed, target, snapshot, plan, state, planned=True)
            report["mode"] = "dry-run"
            atomic_json(directory / "report.json", report)
            return {
                **plan,
                **report,
                "plan_path": str(directory / "plan.json"),
            }

    snapshot, _catalog = _load_primary()
    failures = dict(plan["failures"])
    fatal_error = None
    api_key = settings.internal_api_key.get_secret_value() if settings.internal_api_key else ""
    if plan["requests"]:
        if not api_key:
            raise SupplementError("INTERNAL_API_KEY 설정이 필요합니다.")
        with httpx.Client(follow_redirects=False) as api:
            for body in plan["requests"]:
                item = state["items"][body["source_id"]]
                if item["status"] == "registered":
                    existing = _find_source(body["source_id"])
                    if (
                        existing is None
                        or not existing["is_active"]
                        or not _matches(existing, body)
                    ):
                        failures[body["category_code"]] = "saved_result_mismatch"
                        fatal_error = "saved_result_mismatch"
                        break
                    continue

                category = body["category_code"]
                registered_this_run = sum(
                    entry.get("status") == "registered"
                    and entry.get("newly_created", False)
                    and entry.get("category_code") == category
                    for entry in state["items"].values()
                )
                remaining = max(
                    0,
                    target
                    - plan["planning_newly_registered_by_category"][category]
                    - registered_this_run,
                )
                if remaining == 0:
                    item.update(status="skipped", skip_reason="이번 실행 목표를 이미 충족")
                    _save_state(directory, state)
                    continue

                existing = _find_source(body["source_id"])
                if existing is not None:
                    if (
                        existing["is_active"]
                        and _matches(existing, body)
                        and item.get("status") in {"in_flight", "uncertain"}
                        and item.get("attempts", 0) > 0
                    ):
                        item.update(
                            status="registered",
                            venue_id=existing["venue_id"],
                            newly_created=True,
                            reconciled=True,
                        )
                        _save_state(directory, state)
                        continue
                    item.update(status="failed", failure="source_id_conflict")
                    failures[category] = (
                        "같은 출처 ID의 기존 공간이 계획과 일치하지 않거나 이번 실행 전에 등록돼 있습니다."
                    )
                    _save_state(directory, state)
                    fatal_error = "source_id_conflict"
                    break

                max_attempts = max(0, RETRIES + 1 - item["attempts"])
                if max_attempts == 0:
                    item.update(status="uncertain", failure="retry_limit_exhausted")
                    failures[category] = "같은 실행의 등록 재시도 횟수를 모두 사용했습니다."
                    _save_state(directory, state)
                    fatal_error = "retry_limit_exhausted"
                    break
                item.update(status="in_flight", attempts=item["attempts"] + 1)
                _save_state(directory, state)
                existing, failure, attempts, newly_created = _register(
                    body,
                    api,
                    api_key,
                    args.api_url,
                    max_attempts=max_attempts,
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
                item["newly_created"] = newly_created
                _save_state(directory, state)

    snapshot, _catalog = _load_primary()
    report = _report(run_id, seed, target, snapshot, plan, state, failures=failures)
    report["fatal_error"] = fatal_error
    report["mode"] = "apply"
    atomic_json(directory / "report.json", report)
    return report


def plan_run(
    *,
    counts,
    seed,
    run_id,
    output_root,
    profiles=DEFAULT_PROFILES,
    api_url=DEFAULT_API_URL,
    parent_pipeline_id=None,
    save_plan=True,
):
    """상위 실행기가 공통 잠금 안에서 기존 #99 계획 경로를 호출한다."""
    options = [
        "--dry-run",
        "--seed",
        str(seed),
        "--profiles",
        str(profiles),
        "--api-url",
        api_url,
        "--output-root",
        str(output_root),
        "--newly-registered-by-category",
        json.dumps(counts),
    ]
    if save_plan:
        options.append("--save-plan")
    args = parser().parse_args(options)
    args.run_id = run_id
    args.parent_pipeline_id = parent_pipeline_id
    return execute(args)


def apply_saved_run(*, run_id, output_root, profiles=DEFAULT_PROFILES, api_url=DEFAULT_API_URL):
    """상위 실행기의 공통 잠금 안에서 저장된 #99 계획만 적용한다."""
    return execute(
        parser().parse_args(
            [
                "--apply",
                "--resume",
                run_id,
                "--output-root",
                str(output_root),
                "--profiles",
                str(profiles),
                "--api-url",
                api_url,
            ]
        )
    )


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.apply or args.save_plan:
            with VenuePipelineLock():
                result = execute(args)
        else:
            result = execute(args)
        if "summary_text" in result:
            print(result["summary_text"], file=sys.stderr)
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
