"""F-61: #108 크롤러와 #103 계획·등록·재개의 실제 연결을 검증한다."""

import json
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from pydantic import SecretStr

from simulator.generator import run_pipeline as pipeline
from simulator.generator import venue_supplement as supplement
from simulator.generator.storage import atomic_json
from simulator.generator.topup import CATEGORIES
from simulator.generator.venue_supplement_lock import VenuePipelineLock


def counts(value=0):
    return dict.fromkeys(CATEGORIES, value)


def crawler_result(**changes):
    return {
        "ok": True,
        "jobs": {},
        "job_ids": {},
        "registered_by_category": counts(),
        "newly_registered_by_category": counts(),
        "uncertain_registrations": [],
        "failure": None,
        **changes,
    }


@pytest.fixture
def runtime(monkeypatch):
    profiles, _, _ = supplement._read_profiles(supplement.DEFAULT_PROFILES)
    catalog = {
        "categories": set(CATEGORIES),
        "regions": {(p["sido"], p["sigungu"]) for p in profiles.values()},
        "facilities": {name for p in profiles.values() for name in p["facilities"]},
    }
    existing = {}
    calls = []
    monkeypatch.setattr(supplement, "_target_identity", lambda settings: "test-primary")
    monkeypatch.setattr(
        supplement, "get_settings", lambda: SimpleNamespace(internal_api_key=SecretStr("test-key"))
    )
    monkeypatch.setattr(pipeline, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        supplement, "_load_primary", lambda: ({"venues": list(existing.values())}, catalog)
    )
    monkeypatch.setattr(supplement, "_find_source", lambda source_id: existing.get(source_id))
    monkeypatch.setattr(pipeline, "_preflight", lambda *args: None)
    crawl = Mock(return_value=crawler_result())
    monkeypatch.setattr(pipeline.crawl_venues, "run_configured", crawl)

    def post(url, request):
        body = json.loads(request.content)
        assert request.headers["X-Internal-Key"] == "test-key"
        calls.append(body)
        source_id = body["source_id"]
        status = 200 if source_id in existing else 201
        existing[source_id] = {**body, "venue_id": len(existing) + 1, "is_active": True}
        return httpx.Response(
            status, json={"venue_id": existing[source_id]["venue_id"], "ignored_facilities": []}
        )

    transport = httpx.MockTransport(lambda request: post(str(request.url), request))
    original_client = httpx.Client
    monkeypatch.setattr(
        supplement.httpx, "Client", lambda **kw: original_client(transport=transport, **kw)
    )
    return SimpleNamespace(existing=existing, calls=calls, crawl=crawl, catalog=catalog)


@pytest.mark.parametrize("new_count,planned", [(0, 6), (2, 4), (6, 0), (8, 0)])
def test_dry_run_reuses_103_without_crawling_or_writing(runtime, tmp_path, new_count, planned):
    report = pipeline.dry_run(
        crawler_result(newly_registered_by_category=counts(new_count)), output_root=tmp_path
    )
    assert report["supplement"]["planned_by_category"] == counts(planned)
    assert report["supplemented_by_category"] == counts()
    assert report["completion_basis"] == "projected"
    assert report["plan_valid"] is True
    assert list(tmp_path.iterdir()) == []
    assert runtime.calls == []
    runtime.crawl.assert_not_called()


@pytest.mark.parametrize(
    "invalid",
    [{"cafe": 0}, {**counts(), "cafe": -1}, {**counts(), "cafe": True}, {**counts(), "cafe": "2"}],
)
def test_invalid_counts_stop_without_files(runtime, tmp_path, invalid):
    with pytest.raises(pipeline.GeneratorError):
        pipeline.dry_run({"newly_registered_by_category": invalid}, output_root=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_apply_saves_linked_plan_before_registration_and_reports_actual_counts(
    runtime, tmp_path, monkeypatch
):
    runtime.crawl.return_value = crawler_result(
        newly_registered_by_category=dict(zip(CATEGORIES, (5, 4, 2, 0, 1), strict=True))
    )
    original = supplement.apply_saved_run

    def inspect_then_apply(**kwargs):
        directory = next(tmp_path.glob("venue-pipeline-*"))
        manifest = pipeline._read(directory / "manifest.json")
        state = pipeline._read(directory / "state.json")
        assert state["stage"] == "supplement_planned"
        assert state["supplement_run_id"] == kwargs["run_id"] == manifest["supplement_run_id"]
        assert (tmp_path / f"venue-supplement-{kwargs['run_id']}" / "plan.json").is_file()
        assert runtime.calls == []
        return original(**kwargs)

    monkeypatch.setattr(supplement, "apply_saved_run", inspect_then_apply)
    report = pipeline.apply_pipeline(output_root=tmp_path, seed=100)
    assert report["complete"] is True
    assert report["supplemented_by_category"] == dict(zip(CATEGORIES, (1, 2, 4, 6, 5), strict=True))
    assert report["total_newly_registered_by_category"] == counts(6)
    assert report["remaining_by_category"] == counts()
    assert report["initial_active_counts"] == counts()
    assert report["final_active_counts"] == report["supplemented_by_category"]
    assert len(runtime.calls) == 18
    assert report["run_id"] != report["supplement_run_id"]


def test_resume_after_plan_saved_before_apply_uses_same_plan_without_recrawling(
    runtime, tmp_path, monkeypatch
):
    original = supplement.apply_saved_run
    monkeypatch.setattr(supplement, "apply_saved_run", Mock(side_effect=RuntimeError("중단")))
    first = pipeline.apply_pipeline(output_root=tmp_path, seed=101)
    assert first["status"] == "supplement_interrupted"
    plan_path = tmp_path / f"venue-supplement-{first['supplement_run_id']}" / "plan.json"
    before = plan_path.read_bytes()
    monkeypatch.setattr(supplement, "apply_saved_run", original)
    resumed = pipeline.resume_pipeline(output_root=tmp_path, run_id=first["run_id"])
    assert resumed["complete"] is True
    assert plan_path.read_bytes() == before
    assert len(runtime.calls) == 30
    assert runtime.crawl.call_count == 1
    again = pipeline.resume_pipeline(output_root=tmp_path, run_id=first["run_id"])
    assert again["complete"] is True
    assert len(runtime.calls) == 30


def test_resume_after_plan_saved_before_state_update_does_not_create_new_plan(
    runtime, tmp_path, monkeypatch
):
    original_save = pipeline._save_state

    def fail_once(directory, state, stage):
        if stage == "supplement_planned":
            raise RuntimeError("계획 저장 직후 중단")
        return original_save(directory, state, stage)

    monkeypatch.setattr(pipeline, "_save_state", fail_once)
    first = pipeline.apply_pipeline(output_root=tmp_path, seed=102)
    monkeypatch.setattr(pipeline, "_save_state", original_save)
    resumed = pipeline.resume_pipeline(output_root=tmp_path, run_id=first["run_id"])
    assert resumed["complete"] is True
    assert len(list(tmp_path.glob("venue-supplement-*"))) == 1
    assert runtime.crawl.call_count == 1


@pytest.mark.parametrize(
    "kind,uncertain,allowed",
    [("external", [], True), ("internal", [], False), ("external", [{"source_id": "1"}], False)],
)
def test_partial_crawl_failure_only_allows_confirmed_external_results(
    runtime, tmp_path, kind, uncertain, allowed
):
    result = crawler_result(
        ok=False, failure={"kind": kind, "stage": "test"}, uncertain_registrations=uncertain
    )
    runtime.crawl.side_effect = pipeline.crawl_venues.CrawlerRunError(result)
    report = pipeline.apply_pipeline(output_root=tmp_path, seed=103)
    assert report["complete"] is allowed
    assert len(runtime.calls) == (30 if allowed else 0)
    assert (
        pipeline._read(tmp_path / f"venue-pipeline-{report['run_id']}" / "crawler_result.json")
        == result
    )


def test_preview_records_cannot_be_applied_as_real_crawl_results(runtime, tmp_path):
    preview = pipeline.dry_run(crawler_result(), output_root=tmp_path, save_plan=True, seed=104)
    with pytest.raises(pipeline.GeneratorError, match="미리보기"):
        pipeline.resume_pipeline(output_root=tmp_path, run_id=preview["run_id"])
    assert runtime.calls == []


def test_invalid_profile_is_isolated_by_103_instead_of_key_error(runtime, tmp_path):
    document = json.loads(supplement.DEFAULT_PROFILES.read_text(encoding="utf-8"))
    document["profiles"]["partyroom"]["sigungu"] = "없는구"
    path = tmp_path / "profiles.json"
    atomic_json(path, document)
    report = pipeline.dry_run(crawler_result(), output_root=tmp_path, profiles=path)
    assert report["plan_valid"] is False
    assert report["supplement"]["planned_by_category"]["partyroom"] == 0
    assert set(report["supplement"]["failures"]) == {"partyroom"}


def test_missing_crawler_result_stops_resume_without_recrawling(runtime, tmp_path):
    runtime.crawl.side_effect = RuntimeError("기록 전 중단")
    first = pipeline.apply_pipeline(output_root=tmp_path, seed=105)
    with pytest.raises(pipeline.GeneratorError, match=r"crawler_result\.json"):
        pipeline.resume_pipeline(output_root=tmp_path, run_id=first["run_id"])
    assert runtime.crawl.call_count == 1
    assert runtime.calls == []


def test_changed_crawler_result_is_rejected(runtime, tmp_path):
    first = pipeline.apply_pipeline(output_root=tmp_path, seed=106)
    path = tmp_path / f"venue-pipeline-{first['run_id']}" / "crawler_result.json"
    result = pipeline._read(path)
    result["newly_registered_by_category"]["cafe"] = 99
    atomic_json(path, result)
    with pytest.raises(pipeline.GeneratorError, match="크롤러 결과"):
        pipeline.resume_pipeline(output_root=tmp_path, run_id=first["run_id"])


def test_cli_dry_run_returns_zero_and_does_not_claim_actual_completion(runtime, tmp_path, capsys):
    path = tmp_path / "counts.json"
    atomic_json(path, crawler_result())
    assert pipeline.main(["--mode", "dry-run", "--crawler-result", str(path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["complete"] is False
    assert output["plan_valid"] is True


def test_cli_apply_acquires_103_lock_before_crawl(runtime, tmp_path, monkeypatch):
    lock_path = tmp_path / "common.lock"
    monkeypatch.setattr(pipeline, "VenuePipelineLock", lambda: VenuePipelineLock(lock_path))
    with VenuePipelineLock(lock_path):
        assert pipeline.main(["--mode", "apply", "--confirm-shareit-terms"]) == 2
    runtime.crawl.assert_not_called()


def test_common_lock_excludes_a_second_process(tmp_path):
    path = tmp_path / "common.lock"
    code = "from simulator.generator.venue_supplement_lock import VenuePipelineLock, LockUnavailable\nimport sys\ntry:\n with VenuePipelineLock(sys.argv[1]): pass\nexcept LockUnavailable:\n sys.exit(7)\n"
    with VenuePipelineLock(path):
        result = subprocess.run(  # noqa: S603 -- 현재 Python과 고정 검증 코드만 실행한다.
            [sys.executable, "-c", code, str(path)], capture_output=True, text=True
        )
    assert result.returncode == 7, result.stderr


def test_new_run_rejects_reused_seed_before_crawl(runtime, tmp_path):
    first = pipeline.apply_pipeline(output_root=tmp_path, seed=107)
    with pytest.raises(supplement.SupplementError, match="seed"):
        pipeline.apply_pipeline(output_root=tmp_path, seed=107)
    assert first["complete"] is True
    assert runtime.crawl.call_count == 1


def test_partial_supplement_resume_keeps_successes_and_does_not_recrawl(
    runtime, tmp_path, monkeypatch
):
    original = supplement._register

    def interrupt_after_two(*args, **kwargs):
        if len(runtime.calls) == 2:
            return None, "response_uncertain", 1, False
        return original(*args, **kwargs)

    monkeypatch.setattr(supplement, "_register", interrupt_after_two)
    first = pipeline.apply_pipeline(output_root=tmp_path, seed=108)
    assert first["complete"] is False
    assert sum(first["supplemented_by_category"].values()) == 2
    monkeypatch.setattr(supplement, "_register", original)
    resumed = pipeline.resume_pipeline(output_root=tmp_path, run_id=first["run_id"])
    assert resumed["complete"] is True
    assert len(runtime.calls) == 30
    assert len({item["source_id"] for item in runtime.calls}) == 30
    assert runtime.crawl.call_count == 1
