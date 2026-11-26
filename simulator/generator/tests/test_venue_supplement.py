import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from simulator.generator import venue_supplement
from simulator.generator.topup import CATEGORIES, prepare


@pytest.fixture
def profile_context():
    profiles, version, _ = venue_supplement._read_profiles(venue_supplement.DEFAULT_PROFILES)
    catalog = {
        "categories": set(CATEGORIES),
        "regions": {(profile["sido"], profile["sigungu"]) for profile in profiles.values()},
        "facilities": {
            facility for profile in profiles.values() for facility in profile["facilities"]
        },
    }
    return profiles, version, catalog


def _prepare(snapshot, profile_context, counts):
    profiles, version, catalog = profile_context
    return prepare(
        snapshot,
        newly_registered_by_category=counts,
        profiles=profiles,
        catalog=catalog,
        profile_version=version,
    )


def _counts_by_category(plan):
    return {
        category: sum(request["category_code"] == category for request in plan["requests"])
        for category in CATEGORIES
    }


def test_manual_plan_requests_six_new_venues_per_category(profile_context):
    plan = _prepare({"venues": []}, profile_context, dict.fromkeys(CATEGORIES, 0))

    assert _counts_by_category(plan) == dict.fromkeys(CATEGORIES, 6)
    assert len(plan["requests"]) == 30


@pytest.fixture
def primary_source(monkeypatch, profile_context):
    _profiles, _version, catalog = profile_context
    snapshot_reader = Mock(return_value={"venues": []})
    monkeypatch.setattr(venue_supplement, "new_write_session", lambda: nullcontext(object()))
    monkeypatch.setattr(venue_supplement.venue_supplement_repo, "load_catalog", lambda _db: catalog)
    monkeypatch.setattr(venue_supplement.venue_supplement_repo, "load_snapshot", snapshot_reader)
    monkeypatch.setattr(
        venue_supplement, "get_settings", lambda: SimpleNamespace(internal_api_key=None)
    )
    monkeypatch.setattr(venue_supplement, "_target_identity", lambda _settings: "test-db")
    return catalog, snapshot_reader


@pytest.mark.parametrize("resume", [False, True], ids=["new", "resume"])
@pytest.mark.parametrize(
    ("missing_field", "message"),
    [
        ("categories", "공간 유형 누락: studyroom"),
        ("regions", "지역 기초 데이터 없음"),
        ("facilities", "시설 기초 데이터 없음"),
    ],
)
def test_missing_primary_catalog_stops_before_plan_or_api_writes(
    monkeypatch, primary_source, tmp_path, resume, missing_field, message
):
    catalog, snapshot_reader = primary_source
    if resume:
        saved = venue_supplement.execute(
            venue_supplement.parser().parse_args(
                ["--manual", "--dry-run", "--save-plan", "--output-root", str(tmp_path)]
            )
        )
        options = ["--apply", "--resume", saved["run_id"]]
    else:
        options = ["--manual", "--apply"]
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*.json")}
    if missing_field == "categories":
        catalog[missing_field].remove("studyroom")
    else:
        catalog[missing_field].clear()
    snapshot_reader.reset_mock()
    api_factory = Mock(side_effect=AssertionError("등록 API를 사용하면 안 됨"))
    source_reader = Mock(side_effect=AssertionError("등록 결과 조회 전 중단해야 함"))
    monkeypatch.setattr(venue_supplement.httpx, "Client", api_factory)
    monkeypatch.setattr(venue_supplement, "_find_source", source_reader)
    args = venue_supplement.parser().parse_args([*options, "--output-root", str(tmp_path)])

    with pytest.raises(venue_supplement.SupplementError, match=message):
        venue_supplement.execute(args)

    snapshot_reader.assert_not_called()
    api_factory.assert_not_called()
    source_reader.assert_not_called()
    after = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*.json")}
    assert after == before


def test_ready_primary_without_venues_plans_thirty_from_profiles(primary_source):
    _catalog, snapshot_reader = primary_source
    report = venue_supplement.execute(
        venue_supplement.parser().parse_args(["--manual", "--dry-run"])
    )

    assert report["complete"] is True
    assert _counts_by_category(report) == dict.fromkeys(CATEGORIES, 6)
    assert report["initial_active_counts"] == dict.fromkeys(CATEGORIES, 0)
    snapshot_reader.assert_called_once()


@pytest.mark.parametrize("invalid_attribute", ["region", "facility"])
def test_invalid_profile_only_fails_its_category(profile_context, invalid_attribute):
    profiles, _version, _catalog = profile_context
    if invalid_attribute == "region":
        profiles["studyroom"]["sigungu"] = "등록되지 않은 지역"
    else:
        profiles["studyroom"]["facilities"] = ["등록되지 않은 시설"]

    plan = _prepare({"venues": []}, profile_context, dict.fromkeys(CATEGORIES, 0))

    assert set(plan["failures"]) == {"studyroom"}
    assert _counts_by_category(plan) == {
        category: 0 if category == "studyroom" else 6 for category in CATEGORIES
    }
    assert len(plan["requests"]) == 24


def test_crawler_plan_uses_only_this_run_201_counts(profile_context):
    crawler_counts = dict(zip(CATEGORIES, (5, 4, 2, 0, 1), strict=True))
    plan = _prepare({"venues": []}, profile_context, crawler_counts)

    assert _counts_by_category(plan) == dict(zip(CATEGORIES, (1, 2, 4, 6, 5), strict=True))
    assert len(plan["requests"]) == 18


def test_manual_report_does_not_claim_crawler_zeroes(profile_context):
    plan = _prepare({"venues": []}, profile_context, dict.fromkeys(CATEGORIES, 0))
    plan["planning_newly_registered_by_category"] = plan["newly_registered_by_category"]
    plan["newly_registered_by_category"] = None
    plan["supplement_mode"] = "manual"
    state = {
        "items": {
            request["source_id"]: {
                "category_code": request["category_code"],
                "status": "pending",
            }
            for request in plan["requests"]
        }
    }

    report = venue_supplement._report("test-run", 1, 6, {"venues": []}, plan, state, planned=True)

    assert report["supplement_mode"] == "manual"
    assert report["newly_registered_by_category"] is None
    assert report["crawler_counts_provided"] is False
    assert report["planned_by_category"] == dict.fromkeys(CATEGORIES, 6)
    assert report["supplemented_by_category"] == dict.fromkeys(CATEGORIES, 0)
    assert report["projected_remaining_by_category"] == dict.fromkeys(CATEGORIES, 0)
    assert report["complete"] is True
    assert "크롤러 신규 등록: 미확인" in report["summary_text"]
    assert "합계: 보충 계획 30곳 / 목표 30곳" in report["summary_text"]
    assert "실제 보충 성공: 0곳" in report["summary_text"]


def test_manual_partial_result_summary_counts_only_confirmed_new_registrations(profile_context):
    plan = _prepare({"venues": []}, profile_context, dict.fromkeys(CATEGORIES, 0))
    plan["newly_registered_by_category"] = None
    plan["supplement_mode"] = "manual"
    outcomes = [
        ("registered", True),
        ("registered", True),
        ("registered", False),
        ("failed", False),
        ("uncertain", False),
        ("pending", False),
    ]
    state = {"items": {}}
    for category in CATEGORIES:
        requests = [body for body in plan["requests"] if body["category_code"] == category]
        for body, (status, newly_created) in zip(requests, outcomes, strict=True):
            state["items"][body["source_id"]] = {
                "category_code": category,
                "status": status,
                "newly_created": newly_created,
            }

    report = venue_supplement._report("partial-run", 1, 6, {"venues": []}, plan, state)

    assert report["complete"] is False
    assert "스터디룸: 수동 보충 성공 2곳 / 목표 6곳" in report["summary_text"]
    assert "합계: 수동 보충 성공 10곳 / 목표 30곳" in report["summary_text"]
    assert "크롤러 신규 등록: 미확인" in report["summary_text"]
    assert "실행 결과: 미완료" in report["summary_text"]


def test_manual_dry_run_uses_manual_mode_without_database_writes(
    monkeypatch, profile_context, capsys
):
    profiles, version, catalog = profile_context
    snapshot = {"venues": []}
    monkeypatch.setattr(venue_supplement, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        venue_supplement,
        "_read_profiles",
        lambda _path: (profiles, version, "profile-hash"),
    )
    monkeypatch.setattr(venue_supplement, "_load_primary", lambda: (snapshot, catalog))
    monkeypatch.setattr(venue_supplement, "_target_identity", lambda _settings: "db-hash")
    monkeypatch.setattr(venue_supplement, "_api_identity", lambda _url: "api-hash")
    monkeypatch.setattr(venue_supplement, "_code_identity", lambda: "code-hash")
    args = venue_supplement.parser().parse_args(["--manual", "--dry-run"])

    report = venue_supplement.execute(args)

    assert report["supplement_mode"] == "manual"
    assert report["newly_registered_by_category"] is None
    assert len(report["requests"]) == 30
    assert report["complete"] is True
    monkeypatch.setattr(venue_supplement, "close_databases", lambda: None)

    assert venue_supplement.main(["--manual", "--dry-run"]) == 0
    output = capsys.readouterr()
    printed_report = json.loads(output.out)
    assert output.err.strip() == printed_report["summary_text"]
    assert "수동모드 보충 계획 (dry-run)" in output.err
    assert "실제 보충 성공: 0곳" in output.err


def test_manual_run_does_not_change_following_crawler_run(monkeypatch, profile_context):
    profiles, version, catalog = profile_context
    snapshot = {"venues": []}
    monkeypatch.setattr(venue_supplement, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(
        venue_supplement,
        "_read_profiles",
        lambda _path: (profiles, version, "profile-hash"),
    )
    monkeypatch.setattr(venue_supplement, "_load_primary", lambda: (snapshot, catalog))
    monkeypatch.setattr(venue_supplement, "_target_identity", lambda _settings: "db-hash")
    monkeypatch.setattr(venue_supplement, "_api_identity", lambda _url: "api-hash")
    monkeypatch.setattr(venue_supplement, "_code_identity", lambda: "code-hash")

    manual = venue_supplement.execute(
        venue_supplement.parser().parse_args(["--manual", "--dry-run"])
    )
    crawler = venue_supplement.execute(
        venue_supplement.parser().parse_args(
            [
                "--dry-run",
                "--newly-registered-by-category",
                '{"studyroom":5,"studio":4,"cafe":2,"lectureroom":0,"partyroom":1}',
            ]
        )
    )

    assert manual["supplement_mode"] == "manual"
    assert _counts_by_category(manual) == dict.fromkeys(CATEGORIES, 6)
    assert crawler["supplement_mode"] == "crawler"
    assert "summary_text" not in crawler
    assert crawler["newly_registered_by_category"] == dict(
        zip(CATEGORIES, (5, 4, 2, 0, 1), strict=True)
    )
    assert _counts_by_category(crawler) == dict(zip(CATEGORIES, (1, 2, 4, 6, 5), strict=True))


def test_manual_apply_resume_reuses_saved_mode_and_does_not_register_twice(
    monkeypatch, profile_context, tmp_path
):
    profiles, version, catalog = profile_context
    snapshot = {"venues": []}
    stored_rows = {}
    register_calls = 0
    settings = SimpleNamespace(
        internal_api_key=SimpleNamespace(get_secret_value=lambda: "test-key")
    )

    class NoopClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def register(body, _api, _key, _url, *, max_attempts):
        nonlocal register_calls
        register_calls += 1
        row = {**body, "venue_id": register_calls, "is_active": True}
        stored_rows[body["source_id"]] = row
        return row, None, 1, True

    monkeypatch.setattr(venue_supplement, "get_settings", lambda: settings)
    monkeypatch.setattr(
        venue_supplement,
        "_read_profiles",
        lambda _path: (profiles, version, "profile-hash"),
    )
    monkeypatch.setattr(venue_supplement, "_load_primary", lambda: (snapshot, catalog))
    monkeypatch.setattr(venue_supplement, "_target_identity", lambda _settings: "db-hash")
    monkeypatch.setattr(venue_supplement, "_api_identity", lambda _url: "api-hash")
    monkeypatch.setattr(venue_supplement, "_code_identity", lambda: "code-hash")
    monkeypatch.setattr(venue_supplement, "_find_source", stored_rows.get)
    monkeypatch.setattr(venue_supplement, "_register", register)
    monkeypatch.setattr(venue_supplement.httpx, "Client", lambda **_kwargs: NoopClient())

    saved_plan = venue_supplement.execute(
        venue_supplement.parser().parse_args(
            [
                "--manual",
                "--dry-run",
                "--save-plan",
                "--seed",
                "20261108",
                "--output-root",
                str(tmp_path),
            ]
        )
    )
    resume_args = [
        "--apply",
        "--resume",
        saved_plan["run_id"],
        "--output-root",
        str(tmp_path),
    ]

    first_resume = venue_supplement.execute(venue_supplement.parser().parse_args(resume_args))
    second_resume = venue_supplement.execute(venue_supplement.parser().parse_args(resume_args))

    assert first_resume["supplement_mode"] == "manual"
    assert first_resume["newly_registered_by_category"] is None
    assert first_resume["supplemented_by_category"] == dict.fromkeys(CATEGORIES, 6)
    assert second_resume["complete"] is True
    assert register_calls == 30
    assert "합계: 수동 보충 성공 30곳 / 목표 30곳" in first_resume["summary_text"]
    assert second_resume["summary_text"] == first_resume["summary_text"]
    report_path = tmp_path / f"venue-supplement-{saved_plan['run_id']}" / "report.json"
    saved_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved_report["summary_text"] == second_resume["summary_text"]


@pytest.mark.parametrize(
    "options",
    [
        ["--manual", "--dry-run", "--target", "6"],
        [
            "--manual",
            "--dry-run",
            "--newly-registered-by-category",
            '{"studyroom":0,"studio":0,"cafe":0,"lectureroom":0,"partyroom":0}',
        ],
    ],
)
def test_manual_rejects_target_override_and_crawler_counts(options):
    args = venue_supplement.parser().parse_args(options)

    with pytest.raises(venue_supplement.SupplementError):
        venue_supplement.execute(args)


def test_crawler_mode_still_requires_all_category_counts():
    args = venue_supplement.parser().parse_args(["--dry-run"])

    with pytest.raises(venue_supplement.SupplementError):
        venue_supplement.execute(args)


@pytest.fixture
def registration_body(profile_context):
    return _prepare({"venues": []}, profile_context, dict.fromkeys(CATEGORIES, 0))["requests"][0]


@pytest.mark.parametrize("status_code", [200, 201])
def test_registration_counts_only_http_201_as_new(monkeypatch, registration_body, status_code):
    row = {**registration_body, "venue_id": 1, "is_active": True}
    monkeypatch.setattr(venue_supplement, "_find_source", lambda _source_id: row)
    sent = []

    def respond(request):
        sent.append(json.loads(request.content))
        return httpx.Response(status_code, json={"venue_id": 1, "ignored_facilities": []})

    with httpx.Client(transport=httpx.MockTransport(respond)) as api:
        existing, failure, attempts, created = venue_supplement._register(
            registration_body, api, "test-key", "http://testserver/internal/venues"
        )

    assert existing == row
    assert created is (status_code == 201)
    assert failure == (None if status_code == 201 else "not_new_registration")
    assert attempts == 1
    assert sent == [registration_body]


def test_lost_response_reconciles_committed_registration_without_resending(
    monkeypatch, registration_body
):
    stored = {}
    sent = []
    row = {**registration_body, "venue_id": 1, "is_active": True}
    monkeypatch.setattr(venue_supplement, "_find_source", stored.get)

    def lose_response(request):
        sent.append(json.loads(request.content))
        stored[registration_body["source_id"]] = row
        raise httpx.ReadTimeout("등록 응답 유실", request=request)

    with httpx.Client(transport=httpx.MockTransport(lose_response)) as api:
        existing, failure, attempts, created = venue_supplement._register(
            registration_body, api, "test-key", "http://testserver/internal/venues"
        )

    assert existing == row
    assert failure is None
    assert created is True
    assert attempts == len(sent) == 1


def test_timeout_retry_limit_does_not_claim_registration(monkeypatch, registration_body):
    sent = []
    monkeypatch.setattr(venue_supplement, "_find_source", lambda _source_id: None)

    def timeout(request):
        sent.append(json.loads(request.content))
        raise httpx.ConnectTimeout("연결 시간 초과", request=request)

    with httpx.Client(transport=httpx.MockTransport(timeout)) as api:
        existing, failure, attempts, created = venue_supplement._register(
            registration_body, api, "test-key", "http://testserver/internal/venues"
        )

    assert existing is None
    assert failure == "response_uncertain"
    assert created is False
    assert attempts == 3
    assert sent == [registration_body] * 3


@pytest.mark.parametrize("status_code", [401, 500])
def test_api_error_is_not_retried_or_counted(registration_body, status_code):
    sent = []

    def respond(request):
        sent.append(request)
        return httpx.Response(status_code, json={"code": "UNAUTHORIZED"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as api:
        existing, failure, attempts, created = venue_supplement._register(
            registration_body, api, "test-key", "http://testserver/internal/venues"
        )

    assert existing is None
    assert failure == f"http_{status_code}"
    assert created is False
    assert attempts == len(sent) == 1


def test_ignored_facilities_are_not_counted_as_success(registration_body):
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            201, json={"venue_id": 1, "ignored_facilities": ["없는 시설"]}
        )
    )
    with httpx.Client(transport=transport) as api:
        existing, failure, attempts, created = venue_supplement._register(
            registration_body, api, "test-key", "http://testserver/internal/venues"
        )

    assert existing["ignored_facilities"] == ["없는 시설"]
    assert failure == "ignored_facilities"
    assert created is False
    assert attempts == 1


def test_partial_run_resumes_uncertain_item_without_duplicate_posts(
    monkeypatch, profile_context, tmp_path
):
    profiles, version, catalog = profile_context
    stored = {}
    posted = []
    lost_body = None
    original_client = httpx.Client
    settings = SimpleNamespace(
        internal_api_key=SimpleNamespace(get_secret_value=lambda: "test-key")
    )
    monkeypatch.setattr(venue_supplement, "get_settings", lambda: settings)
    monkeypatch.setattr(
        venue_supplement, "_read_profiles", lambda _path: (profiles, version, "profile-hash")
    )
    monkeypatch.setattr(
        venue_supplement, "_load_primary", lambda: ({"venues": list(stored.values())}, catalog)
    )
    monkeypatch.setattr(venue_supplement, "_target_identity", lambda _settings: "db-hash")
    monkeypatch.setattr(venue_supplement, "_api_identity", lambda _url: "api-hash")
    monkeypatch.setattr(venue_supplement, "_code_identity", lambda: "code-hash")
    monkeypatch.setattr(venue_supplement, "_find_source", stored.get)

    def respond(request):
        nonlocal lost_body
        body = json.loads(request.content)
        posted.append(body["source_id"])
        if len(stored) == 2:
            lost_body = body
            raise httpx.ReadTimeout("등록 결과 미확정", request=request)
        stored[body["source_id"]] = {**body, "venue_id": len(stored) + 1, "is_active": True}
        return httpx.Response(
            201, json={"venue_id": stored[body["source_id"]]["venue_id"], "ignored_facilities": []}
        )

    monkeypatch.setattr(
        venue_supplement.httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    saved = venue_supplement.execute(
        venue_supplement.parser().parse_args(
            ["--manual", "--dry-run", "--save-plan", "--output-root", str(tmp_path)]
        )
    )
    args = venue_supplement.parser().parse_args(
        ["--apply", "--resume", saved["run_id"], "--output-root", str(tmp_path)]
    )

    partial = venue_supplement.execute(args)
    assert partial["complete"] is False
    assert partial["fatal_error"] == "response_uncertain"
    assert sum(partial["supplemented_by_category"].values()) == 2
    assert len(posted) == 5
    # 응답이 유실된 등록을 나중에 primary에서 확인할 수 있는 상황을 재현한다.
    stored[lost_body["source_id"]] = {**lost_body, "venue_id": 3, "is_active": True}

    resumed = venue_supplement.execute(args)
    posts_after_resume = len(posted)
    repeated = venue_supplement.execute(args)

    assert resumed["complete"] is True
    assert resumed["failures"] == {}
    assert resumed["supplemented_by_category"] == dict.fromkeys(CATEGORIES, 6)
    assert len(stored) == len(resumed["source_ids"]) == 30
    assert posts_after_resume == len(posted) == 32
    assert repeated["complete"] is True
