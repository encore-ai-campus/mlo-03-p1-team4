"""F-61: #108 크롤러 결과를 #103 공간 보충기의 저장 계획에 연결한다."""

import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import httpx  # noqa: E402 -- 독립 CLI에서 backend 경로를 먼저 추가한다.

from app.core.clock import get_now  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import close_databases  # noqa: E402
from crawler import crawl_venues  # noqa: E402
from simulator.generator import venue_supplement  # noqa: E402
from simulator.generator.plan import GeneratorError, digest  # noqa: E402
from simulator.generator.storage import atomic_json  # noqa: E402
from simulator.generator.topup import CATEGORIES, validate_newly_registered_by_category  # noqa: E402
from simulator.generator.venue_supplement_lock import (  # noqa: E402
    LockUnavailable,
    VenuePipelineLock,
)

DEFAULT_OUTPUT_ROOT = ROOT / "logs"


def _directory(output_root, run_id):
    try:
        normalized = str(uuid.UUID(run_id))
    except (ValueError, TypeError, AttributeError):
        raise GeneratorError("통합 실행 ID는 UUID여야 합니다.") from None
    return Path(output_root) / f"venue-pipeline-{normalized}"


def _read(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (OSError, ValueError):
        raise GeneratorError(f"실행 기록을 읽지 못했습니다: {path.name}") from None


def _counts(result):
    try:
        return validate_newly_registered_by_category(result["newly_registered_by_category"])
    except (KeyError, TypeError, ValueError):
        raise GeneratorError("다섯 유형의 신규 등록 수는 0 이상의 정수여야 합니다.") from None


def _validate_crawler_result(result):
    counts = _counts(result)
    if not isinstance(result.get("uncertain_registrations"), list):
        raise GeneratorError("크롤러의 미확정 등록 정보가 누락됐습니다.")
    if result["uncertain_registrations"]:
        raise GeneratorError("미확정 등록이 있어 보충을 중단합니다.")
    if result.get("secondary_failures"):
        raise GeneratorError("크롤러 내부 정리 실패로 보충을 중단합니다.")
    failure = result.get("failure")
    if failure:
        if not isinstance(failure, dict) or failure.get("kind") != "external":
            raise GeneratorError("DB·내부 API·설정 장애로 보충을 중단합니다.")
        if result.get("ok") is not False:
            raise GeneratorError("크롤러 성공·실패 상태가 모순됩니다.")
    elif result.get("ok") is not True:
        raise GeneratorError("크롤러 실행 결과가 확정되지 않았습니다.")
    return counts


def _code_identity():
    hasher = hashlib.sha256(venue_supplement._code_identity().encode())
    for path in (Path(__file__), ROOT / "crawler/crawl_venues.py", ROOT / "crawler/preprocess.py"):
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _active_counts():
    snapshot, _ = venue_supplement._load_primary()
    return venue_supplement._summarize_counts(snapshot)


def _preflight(crawl_mode, profiles, api_url):
    """기초 데이터·내부 저장 경로를 외부 수집 전에 확인한다."""
    venue_supplement._read_profiles(profiles)
    _active_counts()
    if crawl_mode == "weekly":
        state = crawl_venues.read_state()
        if any(site not in state for site in crawl_venues.SITES):
            raise GeneratorError("weekly 실행 전 두 사이트의 baseline이 필요합니다.")
    engine = mongo = None
    try:
        engine, mongo, _, _ = crawl_venues._runtime()
        health_url = api_url.rsplit("/internal/venues", 1)[0] + "/health"
        response = httpx.get(health_url, timeout=5, follow_redirects=False)
        response.raise_for_status()
        health = response.json()
        if health.get("status") not in {"ok", "degraded"} or health.get("mongo") == "down":
            raise ValueError
    except Exception:
        raise GeneratorError("DB・MongoDB・내부 API 실행 환경을 확인하지 못했습니다.") from None
    finally:
        if mongo is not None:
            mongo.close()
        if engine is not None:
            engine.dispose()


def _manifest(*, run_id, seed, mode, crawl_mode, profiles, api_url):
    _, version, profile_hash = venue_supplement._read_profiles(profiles)
    return {
        "version": 1,
        "run_id": run_id,
        "supplement_run_id": str(uuid.uuid4()),
        "seed": seed,
        "mode": mode,
        "created_at": get_now().isoformat(),
        "crawl_mode": crawl_mode,
        "sites": list(crawl_venues.SITES),
        "max_detail": crawl_venues.MAX_DETAIL_PER_RUN,
        "max_register": 5 if crawl_mode == "weekly" else 20,
        "profile_version": version,
        "profile_sha256": profile_hash,
        "code_sha256": _code_identity(),
        "target_sha256": venue_supplement._target_identity(get_settings()),
        "api_target_sha256": venue_supplement._api_identity(api_url),
    }


def _report(directory, manifest, result, state, supplement=None, *, failure=None):
    try:
        counts = _counts(result) if result else None
    except GeneratorError:
        counts = None
    successful = (supplement or {}).get("supplemented_by_category", dict.fromkeys(CATEGORIES, 0))
    totals = (
        {category: counts[category] + successful[category] for category in CATEGORIES}
        if counts
        else None
    )
    preview = manifest["mode"] == "dry-run"
    report = {
        "run_id": manifest["run_id"],
        "supplement_run_id": manifest["supplement_run_id"],
        "seed": manifest["seed"],
        "mode": manifest["mode"],
        "status": state["stage"],
        "complete": state["stage"] in {"completed", "completed_with_external_crawl_failure"},
        "newly_registered_by_category": counts,
        "supplemented_by_category": successful,
        "total_newly_registered_by_category": totals,
        "remaining_by_category": {category: max(0, 6 - totals[category]) for category in CATEGORIES}
        if totals
        else None,
        "initial_active_counts": state.get("initial_active_counts"),
        "final_active_counts": (supplement or {}).get("final_active_counts"),
        "crawler_failure": (result or {}).get("failure"),
        "uncertain_registrations": (result or {}).get("uncertain_registrations"),
        "failure": failure,
        "supplement": supplement,
        "completion_basis": "projected" if preview else "actual",
    }
    if directory is not None:
        atomic_json(directory / "report.json", report)
    return report


def _save_state(directory, state, stage):
    state["stage"] = stage
    atomic_json(directory / "state.json", state)


def _begin_supplement(directory, manifest, result, state, *, output_root, profiles, api_url):
    try:
        counts = _validate_crawler_result(result)
    except GeneratorError as error:
        _save_state(directory, state, "stopped_before_supplement")
        return _report(directory, manifest, result, state, failure=str(error))
    supplement_id = manifest["supplement_run_id"]
    supplement_directory = output_root / f"venue-supplement-{supplement_id}"
    try:
        if not supplement_directory.exists():
            _save_state(directory, state, "planning_supplement")
            venue_supplement.plan_run(
                counts=counts,
                seed=manifest["seed"],
                run_id=supplement_id,
                output_root=output_root,
                profiles=profiles,
                api_url=api_url,
                parent_pipeline_id=manifest["run_id"],
            )
        saved = _read(supplement_directory / "manifest.json")
        if (
            saved.get("parent_pipeline_id") != manifest["run_id"]
            or saved.get("run_id") != supplement_id
            or saved.get("seed") != manifest["seed"]
            or saved.get("newly_registered_by_category") != counts
            or saved.get("supplement_mode") != "crawler"
        ):
            raise GeneratorError("연결된 보충 실행의 입력·seed·실행 ID가 다릅니다.")
        # 연결 ID는 크롤링 전에, 계획 완료는 첫 등록 전에 각각 저장한다.
        _save_state(directory, state, "supplement_planned")
        supplement = venue_supplement.apply_saved_run(
            run_id=supplement_id,
            output_root=output_root,
            profiles=profiles,
            api_url=api_url,
        )
        stage = "completed" if supplement["complete"] else "supplement_incomplete"
        if stage == "completed" and result.get("failure"):
            stage = "completed_with_external_crawl_failure"
        _save_state(directory, state, stage)
        return _report(directory, manifest, result, state, supplement)
    except Exception as error:
        _save_state(directory, state, "supplement_interrupted")
        return _report(
            directory,
            manifest,
            result,
            state,
            failure=f"보충 단계 중단 ({type(error).__name__}); 같은 실행 ID로 재개하세요.",
        )


def dry_run(
    result,
    *,
    output_root=DEFAULT_OUTPUT_ROOT,
    seed=None,
    save_plan=False,
    profiles=venue_supplement.DEFAULT_PROFILES,
    api_url=venue_supplement.DEFAULT_API_URL,
):
    counts = _counts(result)
    seed = seed if seed is not None else int.from_bytes(os.urandom(8), "big")
    if seed < 0:
        raise GeneratorError("seed는 0 이상이어야 합니다.")
    run_id = str(uuid.uuid4())
    manifest = _manifest(
        run_id=run_id,
        seed=seed,
        mode="dry-run",
        crawl_mode="weekly",
        profiles=profiles,
        api_url=api_url,
    )
    directory = _directory(output_root, run_id) if save_plan else None
    preview = venue_supplement.plan_run(
        counts=counts,
        seed=seed,
        run_id=manifest["supplement_run_id"],
        output_root=output_root,
        profiles=profiles,
        api_url=api_url,
        parent_pipeline_id=run_id,
        save_plan=save_plan,
    )
    state = {
        "stage": "planned",
        "supplement_run_id": manifest["supplement_run_id"],
        "initial_active_counts": preview["initial_active_counts"],
    }
    if save_plan:
        directory.mkdir(parents=True)
        atomic_json(directory / "manifest.json", manifest)
        atomic_json(directory / "crawler_result.json", result)
        atomic_json(directory / "state.json", state)
    report = _report(directory, manifest, result, state, preview)
    report["plan_valid"] = preview["complete"]
    if directory is not None:
        atomic_json(directory / "report.json", report)
    return report


def apply_pipeline(
    *,
    output_root=DEFAULT_OUTPUT_ROOT,
    seed=None,
    crawl_mode="weekly",
    profiles=venue_supplement.DEFAULT_PROFILES,
    api_url=venue_supplement.DEFAULT_API_URL,
):
    output_root = Path(output_root)
    seed = seed if seed is not None else int.from_bytes(os.urandom(8), "big")
    if seed < 0:
        raise GeneratorError("seed는 0 이상이어야 합니다.")
    venue_supplement._reject_seed_reuse(output_root, seed)
    for path in output_root.glob("venue-pipeline-*/manifest.json"):
        if _read(path).get("seed") == seed:
            raise GeneratorError("새 통합 실행에는 아직 사용하지 않은 seed가 필요합니다.")
    _preflight(crawl_mode, profiles, api_url)
    run_id = str(uuid.uuid4())
    directory = _directory(output_root, run_id)
    manifest = _manifest(
        run_id=run_id,
        seed=seed,
        mode="apply",
        crawl_mode=crawl_mode,
        profiles=profiles,
        api_url=api_url,
    )
    state = {
        "stage": "crawling",
        "supplement_run_id": manifest["supplement_run_id"],
        "initial_active_counts": _active_counts(),
    }
    directory.mkdir(parents=True)
    atomic_json(directory / "manifest.json", manifest)
    atomic_json(directory / "state.json", state)
    _report(directory, manifest, None, state)
    try:
        result = crawl_venues.run_configured(
            sites=crawl_venues.SITES,
            mode=crawl_mode,
            max_detail=manifest["max_detail"],
            max_register=manifest["max_register"],
            api_url=api_url,
        )
    except crawl_venues.CrawlerRunError as error:
        result = error.result
    except Exception as error:
        _save_state(directory, state, "crawler_interrupted")
        return _report(
            directory,
            manifest,
            None,
            state,
            failure=f"크롤러 실적을 확정하지 못했습니다 ({type(error).__name__}). 재수집하지 마세요.",
        )
    atomic_json(directory / "crawler_result.json", result)
    state["crawler_result_sha256"] = digest(result)
    _save_state(directory, state, "crawler_result_saved")
    return _begin_supplement(
        directory,
        manifest,
        result,
        state,
        output_root=output_root,
        profiles=profiles,
        api_url=api_url,
    )


def resume_pipeline(
    *,
    run_id,
    output_root=DEFAULT_OUTPUT_ROOT,
    profiles=venue_supplement.DEFAULT_PROFILES,
    api_url=venue_supplement.DEFAULT_API_URL,
):
    output_root = Path(output_root)
    directory = _directory(output_root, run_id)
    manifest = _read(directory / "manifest.json")
    state = _read(directory / "state.json")
    if manifest.get("mode") != "apply":
        raise GeneratorError("미리보기 입력을 실제 크롤러 실적으로 사용해 재개할 수 없습니다.")
    _, _, profile_hash = venue_supplement._read_profiles(profiles)
    if (
        manifest.get("run_id") != str(uuid.UUID(run_id))
        or manifest.get("supplement_run_id") != state.get("supplement_run_id")
        or manifest.get("code_sha256") != _code_identity()
        or manifest.get("target_sha256") != venue_supplement._target_identity(get_settings())
        or manifest.get("api_target_sha256") != venue_supplement._api_identity(api_url)
        or manifest.get("profile_sha256") != profile_hash
    ):
        raise GeneratorError("실행 ID·코드·프로필·DB·API 대상이 기존 실행과 다릅니다.")
    result = _read(directory / "crawler_result.json")
    if digest(result) != state.get("crawler_result_sha256"):
        raise GeneratorError("저장된 크롤러 결과가 기존 실행 기록과 다릅니다.")
    return _begin_supplement(
        directory,
        manifest,
        result,
        state,
        output_root=output_root,
        profiles=profiles,
        api_url=api_url,
    )


def parser():
    command = argparse.ArgumentParser(description="F-61 크롤러·공간 보충 통합 실행기")
    command.add_argument("--mode", choices=("dry-run", "apply", "resume"), required=True)
    command.add_argument("--crawler-result", type=Path)
    command.add_argument("--run-id")
    command.add_argument("--seed", type=int)
    command.add_argument(
        "--crawler-mode",
        "--crawl-mode",
        dest="crawl_mode",
        choices=("weekly", "bootstrap"),
        default="weekly",
    )
    command.add_argument("--save-plan", action="store_true")
    command.add_argument(
        "--confirm-shareit-terms",
        action="store_true",
        help="이번 실행 직전 쉐어잇 약관을 확인했음을 표시",
    )
    command.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    command.add_argument("--profiles", type=Path, default=venue_supplement.DEFAULT_PROFILES)
    command.add_argument("--api-url", default=venue_supplement.DEFAULT_API_URL)
    return command


def main(argv=None):
    command = parser()
    args = command.parse_args(argv)
    if args.mode == "dry-run":
        if not args.crawler_result or args.run_id:
            command.error("dry-run은 --crawler-result가 필요하고 --run-id를 사용할 수 없습니다.")
    elif args.crawler_result or args.save_plan:
        command.error("실제 실행·재개는 미리보기 입력이나 --save-plan을 사용하지 않습니다.")
    if args.mode == "resume" and (not args.run_id or args.seed is not None):
        command.error("resume은 --run-id가 필요하며 저장된 seed를 사용합니다.")
    if args.mode == "apply" and args.run_id:
        command.error("새 apply 실행의 ID는 자동으로 생성합니다.")
    if args.mode == "apply" and not args.confirm_shareit_terms:
        command.error("실행 직전 약관을 확인한 뒤 --confirm-shareit-terms를 지정하세요.")
    options = {"output_root": args.output_root, "profiles": args.profiles, "api_url": args.api_url}
    try:
        # 단독 #99 CLI와 같은 잠금. 내부 #99 함수는 다시 잠그지 않는다.
        if args.mode == "dry-run" and not args.save_plan:
            report = dry_run(_read(args.crawler_result), seed=args.seed, **options)
        else:
            with VenuePipelineLock():
                if args.mode == "apply":
                    report = apply_pipeline(seed=args.seed, crawl_mode=args.crawl_mode, **options)
                elif args.mode == "resume":
                    report = resume_pipeline(run_id=args.run_id, **options)
                else:
                    report = dry_run(
                        _read(args.crawler_result), seed=args.seed, save_plan=True, **options
                    )
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if report.get("complete") or report.get("plan_valid") else 1
    except (GeneratorError, LockUnavailable) as error:
        print(f"통합 실행 중단: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(
            f"통합 실행 중단 ({type(error).__name__}); 실행 기록과 설정을 확인하세요.",
            file=sys.stderr,
        )
        return 2
    finally:
        close_databases()


if __name__ == "__main__":
    raise SystemExit(main())
