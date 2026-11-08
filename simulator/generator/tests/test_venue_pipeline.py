"""#99/#100 공간 보충과 통합 실행 경계를 검증한다."""

import json
from contextlib import nullcontext
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from simulator.generator import run_pipeline, venue_supplement
from simulator.generator.plan import CATEGORIES, GeneratorError


def counts(value=0):
    return dict.fromkeys(CATEGORIES, value)


def references_from_profiles(valid_profiles):
    return [
        {
            "venue_id": index,
            "source_site": "spacecloud",
            "source_id": f"crawl-{index}",
            "category_code": category,
            "sido": profile["sido"],
            "sigungu": profile["sigungu"],
            "capacity_max": profile["capacity_max"],
            "price_per_hour": profile["price_per_hour"],
            "min_hours": profile["min_hours"],
            "open_hour": profile["open_hour"],
            "close_hour": profile["close_hour"],
            "facilities": list(profile["facilities"]),
        }
        for index, (category, profile) in enumerate(valid_profiles.items(), start=1)
    ]


def test_new_registration_counts_are_exact_and_strict():
    assert venue_supplement.validate_counts({"newly_registered_by_category": counts(2)}) == counts(
        2
    )
    with pytest.raises(GeneratorError):
        venue_supplement.validate_counts({"studyroom": 1})
    invalid = counts()
    invalid["cafe"] = True
    with pytest.raises(GeneratorError):
        venue_supplement.validate_counts(invalid)


def test_plan_fills_only_the_gap_from_this_crawls_201_counts():
    document, profile_hash, valid_profiles = venue_supplement.load_profiles()
    refs = references_from_profiles(valid_profiles)
    registered = counts()
    registered.update(studyroom=2, studio=6)

    plan = venue_supplement.build_plan(
        registered, refs, document, "pipeline-abc", profile_hash=profile_hash
    )

    assert plan["planned_by_category"] == {
        "studyroom": 4,
        "studio": 0,
        "cafe": 6,
        "lectureroom": 6,
        "partyroom": 6,
    }
    assert len({item["payload"]["source_id"] for item in plan["items"]}) == 22
    assert all(item["payload"]["source_site"] == "synthetic" for item in plan["items"])
    assert all(item["payload"]["images"][0].startswith("art:") for item in plan["items"])


def test_plan_is_reproducible_and_category_fallback_failure_is_local():
    document, _, _ = venue_supplement.load_profiles()
    plan = venue_supplement.build_plan(counts(), [], document, "stable-run")
    assert plan == venue_supplement.build_plan(counts(), [], document, "stable-run")
    assert plan["planned_by_category"] == counts(6)

    broken = json.loads(json.dumps(document))
    broken["categories"]["partyroom"]["sigungu"] = "없는구"
    partial = venue_supplement.build_plan(counts(), [], broken, "partial-run")
    assert partial["category_failures"] == {
        "partyroom": "유효한 크롤링 기준 공간과 기본 프로필이 없습니다."
    }
    assert partial["planned_by_category"]["partyroom"] == 0
    assert all(partial["planned_by_category"][category] == 6 for category in CATEGORIES[:-1])


def test_pipeline_accepts_confirmed_external_failure_but_stops_uncertain_or_internal():
    result = {
        "ok": False,
        "newly_registered_by_category": counts(1),
        "uncertain_registrations": [],
        "failure": {"kind": "external", "stage": "sitemap_fetch"},
    }
    assert run_pipeline._validate_crawler_result(result) == (counts(1), None)

    internal = {**result, "failure": {"kind": "internal"}}
    assert run_pipeline._validate_crawler_result(internal)[0] is None
    uncertain = {**result, "uncertain_registrations": [{"source_id": "x"}]}
    assert run_pipeline._validate_crawler_result(uncertain)[0] is None


def test_supplement_resume_retries_the_saved_request_after_uncertain_response(
    monkeypatch, tmp_path
):
    document, profile_hash, _ = venue_supplement.load_profiles()
    monkeypatch.setattr(venue_supplement, "_target_identity", lambda: "db-hash")
    monkeypatch.setattr(venue_supplement, "_code_identity", lambda: "code-hash")
    monkeypatch.setattr(
        venue_supplement,
        "get_settings",
        lambda: SimpleNamespace(
            internal_api_key=SecretStr("test-key"),
            synthetic_api_key=SecretStr("synthetic-test-key"),
        ),
    )
    monkeypatch.setattr(venue_supplement, "_check_catalog", lambda plan: None)
    monkeypatch.setattr(venue_supplement, "_get_snapshot", lambda body: None)

    directory, plan = venue_supplement.create_run(
        output_root=tmp_path,
        run_id="resume-run",
        counts=counts(5),
        references=[],
        profile_document=document,
        profile_hash=profile_hash,
    )
    saved_plan = (directory / "plan.json").read_text(encoding="utf-8")

    class FirstAttemptFails:
        def __init__(self, **kwargs):
            self.calls = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, *, headers, json):
            assert headers["X-Synthetic"] == "1"
            assert "X-Synthetic-Key" in headers
            self.calls += 1
            request = httpx.Request("POST", url)
            raise httpx.ConnectError("offline", request=request)

    monkeypatch.setattr(venue_supplement.httpx, "Client", FirstAttemptFails)
    first = venue_supplement.apply_run(directory, lock_held=True)
    assert first["status"] == "uncertain"
    assert first["supplement_registered_by_category"]["studyroom"] == 0

    class RetrySucceeds:
        def __init__(self, **kwargs):
            self.calls = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, *, headers, json):
            assert headers["X-Synthetic"] == "1"
            self.calls += 1
            return httpx.Response(
                201,
                json={"venue_id": self.calls, "ignored_facilities": []},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(venue_supplement.httpx, "Client", RetrySucceeds)
    resumed = venue_supplement.apply_run(directory, lock_held=True)
    assert resumed["status"] == "completed"
    assert resumed["supplement_registered_by_category"]["studyroom"] == 1
    assert (directory / "plan.json").read_text(encoding="utf-8") == saved_plan
    state = json.loads((directory / "state.json").read_text(encoding="utf-8"))
    assert state["items"][plan["items"][0]["item_id"]]["attempts"] == 2


def test_supplement_does_not_count_an_existing_source_200(monkeypatch, tmp_path):
    document, profile_hash, _ = venue_supplement.load_profiles()
    monkeypatch.setattr(venue_supplement, "_target_identity", lambda: "db-hash")
    monkeypatch.setattr(venue_supplement, "_code_identity", lambda: "code-hash")
    monkeypatch.setattr(
        venue_supplement,
        "get_settings",
        lambda: SimpleNamespace(
            internal_api_key=SecretStr("test-key"),
            synthetic_api_key=SecretStr("synthetic-test-key"),
        ),
    )
    monkeypatch.setattr(venue_supplement, "_check_catalog", lambda plan: None)
    calls = []

    class DuplicateClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, *, headers, json):
            calls.append(json["source_id"])
            return httpx.Response(
                200,
                json={"venue_id": 123, "ignored_facilities": []},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(venue_supplement.httpx, "Client", DuplicateClient)
    directory, _ = venue_supplement.create_run(
        output_root=tmp_path,
        run_id="duplicate-run",
        counts=counts(5),
        references=[],
        profile_document=document,
        profile_hash=profile_hash,
    )

    first = venue_supplement.apply_run(directory, lock_held=True)
    second = venue_supplement.apply_run(directory, lock_held=True)
    assert first["status"] == "failed"
    assert second["status"] == "failed"
    assert first["supplement_registered_by_category"]["studyroom"] == 0
    assert len(calls) == 1


def test_pipeline_resume_never_repeats_the_crawl(monkeypatch, tmp_path):
    run_id = "saved-pipeline"
    supplement_id = "saved-supplement"
    pipeline_dir = tmp_path / f"venue-pipeline-{run_id}"
    supplement_dir = tmp_path / f"venue-supplement-{supplement_id}"
    pipeline_dir.mkdir()
    supplement_dir.mkdir()
    document, profile_hash, _ = venue_supplement.load_profiles()
    manifest = {
        "run_id": run_id,
        "supplement_run_id": supplement_id,
        "profile_sha256": profile_hash,
        "code_sha256": "code-hash",
        "target_identity": "db-hash",
    }
    (pipeline_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (pipeline_dir / "state.json").write_text(
        json.dumps({"stage": "crawler_result_saved"}), encoding="utf-8"
    )
    (pipeline_dir / "crawler_result.json").write_text(
        json.dumps(
            {
                "ok": True,
                "newly_registered_by_category": counts(),
                "uncertain_registrations": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(venue_supplement, "_code_identity", lambda: "code-hash")
    monkeypatch.setattr(venue_supplement, "_target_identity", lambda: "db-hash")
    monkeypatch.setattr(venue_supplement, "load_profiles", lambda: (document, profile_hash, {}))
    monkeypatch.setattr(venue_supplement, "read_references", lambda: [])
    monkeypatch.setattr(
        venue_supplement,
        "apply_run",
        lambda directory, lock_held: {
            "status": "completed",
            "remaining_to_target_by_category": counts(),
            "supplement_registered_by_category": counts(6),
            "category_failures": {},
        },
    )

    monkeypatch.setattr(run_pipeline, "venue_pipeline_lock", nullcontext)
    monkeypatch.setattr(
        run_pipeline.crawl_venues,
        "run_configured",
        lambda **kwargs: pytest.fail("crawl repeated"),
    )
    report = run_pipeline.resume_pipeline(output_root=tmp_path, run_id=run_id)
    assert report["status"] == "completed"
