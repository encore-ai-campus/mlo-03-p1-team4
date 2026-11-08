"""#100 주간 크롤링·공간 보충을 한 잠금과 복구 기록으로 실행한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import httpx  # noqa: E402 -- standalone CLI adds backend to sys.path first

from app.core.clock import get_now  # noqa: E402 -- standalone CLI imports app from backend
from app.core.config import get_settings  # noqa: E402 -- standalone CLI imports app from backend
from app.core.db import close_databases  # noqa: E402 -- standalone CLI imports app from backend
from crawler import crawl_venues  # noqa: E402 -- standalone CLI imports app from backend
from simulator.generator import venue_supplement  # noqa: E402 -- bootstrap above
from simulator.generator.plan import CATEGORIES, GeneratorError  # noqa: E402 -- bootstrap above
from simulator.generator.storage import atomic_json  # noqa: E402 -- bootstrap above
from simulator.generator.venue_pipeline_lock import venue_pipeline_lock  # noqa: E402 -- bootstrap above

DEFAULT_OUTPUT_ROOT = ROOT / "logs"
MAX_REGISTER = 5


def _directory(output_root: Path, run_id: str) -> Path:
    if not run_id or any(
        char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for char in run_id
    ):
        raise GeneratorError("실행 ID에 사용할 수 없는 문자가 있습니다.")
    return output_root / f"venue-pipeline-{run_id}"


def _safe_summary(result: dict) -> dict:
    failure = result.get("failure")
    if not isinstance(failure, dict):
        return {"stage": "run", "kind": "internal", "summary": "크롤러 결과를 확인할 수 없습니다."}
    return {
        key: failure.get(key)
        for key in ("stage", "kind", "error_type", "summary")
        if failure.get(key) is not None
    }


def _validate_crawler_result(result: dict) -> tuple[dict[str, int] | None, str | None]:
    """내부 오류·불확실 결과는 보충을 막고 확인된 외부 실패는 허용한다."""
    if not isinstance(result, dict):
        return None, "크롤러 결과 형식이 올바르지 않습니다."
    if result.get("uncertain_registrations"):
        return None, "공간 등록 응답이 불확실해 보충을 중단합니다."
    if result.get("secondary_failures"):
        return None, "크롤러 내부 정리 실패가 있어 보충을 중단합니다."
    failure = result.get("failure")
    if failure and (not isinstance(failure, dict) or failure.get("kind") != "external"):
        return None, "DB·내부 API·설정 오류가 있어 보충을 중단합니다."
    if failure and result.get("ok") is True:
        return None, "크롤러 실패 상태가 모순되어 보충을 중단합니다."
    if not isinstance(result.get("uncertain_registrations"), list):
        return None, "불확실 등록 결과가 누락되어 보충을 중단합니다."
    if result.get("ok") is not True and not failure:
        return None, "크롤러 결과가 확정되지 않아 보충을 중단합니다."
    try:
        counts = venue_supplement.validate_counts(result)
    except GeneratorError:
        return None, "유형별 신규 등록 건수를 확정할 수 없어 보충을 중단합니다."
    return counts, None


def _preflight() -> None:
    """DB·Mongo·기준선·seed를 먼저 확인해 설정 실패 뒤 외부 요청을 막는다."""
    engine = None
    mongo = None
    try:
        engine, mongo, _, _ = crawl_venues._runtime()
        state = crawl_venues.read_state()
        if any(site not in state for site in crawl_venues.SITES):
            raise GeneratorError("주간 실행 전에 두 사이트의 sitemap baseline이 필요합니다.")
        crawl_venues.SeedMaps.load()
        venue_supplement.check_profile_catalog()
        if get_settings().synthetic_api_key is None:
            raise GeneratorError("SYNTHETIC_API_KEY 설정이 필요합니다.")
        response = httpx.get("http://127.0.0.1:8000/health", timeout=5)
        response.raise_for_status()
        if response.json().get("status") != "ok":
            raise GeneratorError("내부 API health가 정상 상태가 아닙니다.")
    except GeneratorError:
        raise
    except Exception:
        raise GeneratorError("크롤링 실행 환경을 확인하지 못했습니다.") from None
    finally:
        if mongo is not None:
            mongo.close()
        if engine is not None:
            engine.dispose()


def _pipeline_manifest(run_id: str, supplement_run_id: str) -> dict:
    _, profile_hash, _ = venue_supplement.load_profiles()
    return {
        "version": 1,
        "run_id": run_id,
        "supplement_run_id": supplement_run_id,
        "created_at": get_now().isoformat(),
        "sites": list(crawl_venues.SITES),
        "mode": "weekly",
        "max_detail": crawl_venues.MAX_DETAIL_PER_RUN,
        "max_register": MAX_REGISTER,
        "profile_sha256": profile_hash,
        "code_sha256": venue_supplement._code_identity(),
        "target_identity": venue_supplement._target_identity(),
    }


def _save_pipeline_state(directory: Path, state: dict) -> None:
    atomic_json(directory / "state.json", state)


def _category_summary(crawler_counts: dict, supplement_report: dict | None) -> dict:
    supplemented = (
        supplement_report.get("supplement_registered_by_category", {})
        if supplement_report
        else dict.fromkeys(CATEGORIES, 0)
    )
    return {
        category: {
            "crawler_http_201": crawler_counts[category],
            "supplement_registered": supplemented.get(category, 0),
            "new_registered_total": crawler_counts[category] + supplemented.get(category, 0),
            "target": 6,
            "remaining": max(0, 6 - crawler_counts[category] - supplemented.get(category, 0)),
        }
        for category in CATEGORIES
    }


def _write_report(
    directory: Path,
    *,
    run_id: str,
    supplement_run_id: str,
    status: str,
    crawler_result: dict | None,
    supplement_report: dict | None = None,
    failure: str | None = None,
) -> dict:
    try:
        counts = (
            venue_supplement.validate_counts(crawler_result)
            if crawler_result is not None
            else dict.fromkeys(CATEGORIES, 0)
        )
    except GeneratorError:
        counts = dict.fromkeys(CATEGORIES, 0)
    report = {
        "run_id": run_id,
        "supplement_run_id": supplement_run_id,
        "status": status,
        "crawler_failure": _safe_summary(crawler_result)
        if crawler_result and crawler_result.get("failure")
        else None,
        "category_summary": _category_summary(counts, supplement_report),
        "supplement_category_failures": (
            supplement_report.get("category_failures", {}) if supplement_report else {}
        ),
        "failure": failure,
    }
    atomic_json(directory / "report.json", report)
    return report


def _begin_supplement(
    *,
    directory: Path,
    manifest: dict,
    crawler_result: dict,
    output_root: Path,
) -> dict:
    counts, stop_reason = _validate_crawler_result(crawler_result)
    if stop_reason:
        state = json.loads((directory / "state.json").read_text(encoding="utf-8"))
        state.update(stage="stopped_before_supplement", crawler_result_saved=True)
        _save_pipeline_state(directory, state)
        return _write_report(
            directory,
            run_id=manifest["run_id"],
            supplement_run_id=manifest["supplement_run_id"],
            status="stopped_before_supplement",
            crawler_result=crawler_result,
            failure=stop_reason,
        )

    profile_document, profile_hash, _ = venue_supplement.load_profiles()
    if profile_hash != manifest["profile_sha256"]:
        raise GeneratorError("보충 프로필이 실행 시작 시점과 달라 계획을 만들 수 없습니다.")
    supplement_directory = venue_supplement._run_directory(
        output_root, manifest["supplement_run_id"]
    )
    if not supplement_directory.exists():
        venue_supplement.create_run(
            output_root=output_root,
            run_id=manifest["supplement_run_id"],
            counts=counts,
            references=venue_supplement.read_references(),
            profile_document=profile_document,
            profile_hash=profile_hash,
            parent_pipeline_id=manifest["run_id"],
        )
    state = json.loads((directory / "state.json").read_text(encoding="utf-8"))
    state.update(stage="supplement_planned", crawler_result_saved=True)
    _save_pipeline_state(directory, state)
    supplement_report = venue_supplement.apply_run(supplement_directory, lock_held=True)
    if supplement_report.get("status") == "completed":
        gaps = any(supplement_report.get("remaining_to_target_by_category", {}).values())
        external_failure = bool(crawler_result.get("failure"))
        status = (
            "completed_with_category_gaps"
            if gaps or supplement_report.get("category_failures")
            else "completed_with_external_crawl_failure"
            if external_failure
            else "completed"
        )
    else:
        status = f"supplement_{supplement_report.get('status', 'failed')}"
    state.update(stage=status, crawler_result_saved=True)
    _save_pipeline_state(directory, state)
    report = _write_report(
        directory,
        run_id=manifest["run_id"],
        supplement_run_id=manifest["supplement_run_id"],
        status=status,
        crawler_result=crawler_result,
        supplement_report=supplement_report,
        failure=supplement_report.get("failure"),
    )
    return report


def dry_run(crawler_result: dict, *, run_id: str | None = None) -> dict:
    counts = venue_supplement.validate_counts(crawler_result)
    profile_document, profile_hash, _ = venue_supplement.load_profiles()
    references = venue_supplement.read_references()
    plan = venue_supplement.build_plan(
        counts,
        references,
        profile_document,
        run_id or str(uuid4()),
        profile_hash=profile_hash,
    )
    return {
        "mode": "dry-run",
        "crawler_newly_registered_by_category": counts,
        "planned_by_category": plan["planned_by_category"],
        "remaining_to_target_by_category": {
            category: max(0, 6 - counts[category] - plan["planned_by_category"][category])
            for category in CATEGORIES
        },
        "category_failures": plan["category_failures"],
        "plan_sha256": plan["plan_sha256"],
        "plan": plan,
    }


def apply_pipeline(*, output_root: Path = DEFAULT_OUTPUT_ROOT, run_id: str | None = None) -> dict:
    run_id = run_id or str(uuid4())
    supplement_run_id = str(uuid4())
    directory = _directory(output_root, run_id)
    if directory.exists():
        raise GeneratorError("같은 통합 실행 기록이 이미 있습니다.")
    with venue_pipeline_lock():
        _preflight()
        manifest = _pipeline_manifest(run_id, supplement_run_id)
        directory.mkdir(parents=True)
        atomic_json(directory / "manifest.json", manifest)
        state = {"stage": "ready", "crawler_result_saved": False}
        _save_pipeline_state(directory, state)
        state.update(stage="crawling")
        _save_pipeline_state(directory, state)
        try:
            result = crawl_venues.run_configured(
                sites=crawl_venues.SITES,
                mode="weekly",
                max_detail=crawl_venues.MAX_DETAIL_PER_RUN,
                max_register=MAX_REGISTER,
            )
        except crawl_venues.CrawlerRunError as error:
            result = error.result
        except Exception:
            result = {
                "ok": False,
                "newly_registered_by_category": dict.fromkeys(CATEGORIES, 0),
                "registered_by_category": dict.fromkeys(CATEGORIES, 0),
                "uncertain_registrations": [],
                "failure": {
                    "stage": "pipeline_crawler",
                    "kind": "internal",
                    "summary": "크롤러 실행 결과를 확정하지 못했습니다.",
                },
            }
        atomic_json(directory / "crawler_result.json", result)
        state.update(
            stage="crawler_result_saved",
            crawler_result_saved=True,
        )
        _save_pipeline_state(directory, state)
        return _begin_supplement(
            directory=directory,
            manifest=manifest,
            crawler_result=result,
            output_root=output_root,
        )


def resume_pipeline(*, output_root: Path = DEFAULT_OUTPUT_ROOT, run_id: str) -> dict:
    directory = _directory(output_root, run_id)
    try:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        json.loads((directory / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise GeneratorError("재개할 통합 실행 기록이 없거나 불완전합니다.") from None
    if manifest.get("run_id") != run_id:
        raise GeneratorError("manifest 실행 ID가 요청과 다릅니다.")
    if (
        manifest.get("code_sha256") != venue_supplement._code_identity()
        or manifest.get("target_identity") != venue_supplement._target_identity()
    ):
        raise GeneratorError("DB 대상 또는 실행 코드가 바뀌어 이 통합 실행을 재개할 수 없습니다.")
    if not (directory / "crawler_result.json").exists():
        raise GeneratorError(
            "저장된 크롤러 결과가 없습니다. 안전을 위해 크롤링을 다시 실행하지 않습니다."
        )
    try:
        crawler_result = json.loads((directory / "crawler_result.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise GeneratorError("저장된 크롤러 결과가 손상되어 재개할 수 없습니다.") from None

    with venue_pipeline_lock():
        # crawler_result.json이 이미 있으면 크롤러는 호출하지 않는다.
        return _begin_supplement(
            directory=directory,
            manifest=manifest,
            crawler_result=crawler_result,
            output_root=output_root,
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="#100 주간 크롤링 + 공간 보충 실행기")
    parser.add_argument("--mode", choices=("dry-run", "apply", "resume"), required=True)
    parser.add_argument("--crawler-result", type=Path, help="미리보기용 크롤러 결과 JSON")
    parser.add_argument("--run-id", help="--resume할 venue-pipeline 실행 ID")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--confirm-shareit-terms",
        action="store_true",
        help="이번 실행 전 쉐어잇 이용약관을 확인했음을 표시합니다.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.mode == "dry-run":
            if not args.crawler_result or args.run_id or args.confirm_shareit_terms:
                parser.error("--dry-run에는 --crawler-result만 사용하세요.")
            try:
                result = json.loads(args.crawler_result.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raise GeneratorError("미리보기용 크롤러 결과 JSON을 읽지 못했습니다.") from None
            report = dry_run(result)
        elif args.mode == "apply":
            if args.crawler_result or args.run_id:
                parser.error("--apply에는 --crawler-result/--run-id를 사용하지 않습니다.")
            if not args.confirm_shareit_terms:
                raise GeneratorError(
                    "쉐어잇 이용약관을 확인한 뒤 --confirm-shareit-terms를 지정하세요."
                )
            report = apply_pipeline(output_root=args.output_root)
        else:
            if not args.run_id or args.crawler_result or args.confirm_shareit_terms:
                parser.error("--resume에는 --run-id만 사용하세요.")
            report = resume_pipeline(output_root=args.output_root, run_id=args.run_id)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if report.get("status", "planned").startswith("completed") else 1
    except GeneratorError as error:
        print(f"실행 중단: {error}", file=sys.stderr)
        return 2
    finally:
        close_databases()


if __name__ == "__main__":
    raise SystemExit(main())
