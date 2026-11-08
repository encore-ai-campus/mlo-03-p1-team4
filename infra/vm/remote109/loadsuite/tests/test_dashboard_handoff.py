"""DASH-003의 중복/반복 적용과 보존 요구를 검증한다."""

import copy
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "dash_handoff", Path(__file__).parents[3] / "lab" / "dashboard_handoff.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_overview_handoff_is_idempotent_and_preserves_graphs():
    original = {
        "uid": "spacecube-overview",
        "title": "overview",
        "panels": [
            {
                "id": 5,
                "title": "CPU",
                "type": "timeseries",
                "targets": [],
                "gridPos": {"x": 0, "y": 3, "w": 12, "h": 7},
            },
            {
                "id": 500,
                "title": "HTTP pie",
                "type": "piechart",
                "targets": [],
                "gridPos": {"x": 0, "y": 10, "w": 12, "h": 7},
            },
        ],
    }
    old = copy.deepcopy(original)
    result = module.patch_dashboard(original)
    assert original == old
    assert module.patch_dashboard(result) == result
    assert len(result["panels"]) == len({p["id"] for p in result["panels"]})
    assert {5, 500}.issubset({p["id"] for p in result["panels"]})
    top = [p for p in result["panels"] if p["gridPos"]["y"] < 6]
    assert len(top) == 8
    assert all(p["fieldConfig"]["defaults"]["noValue"] != "0" for p in top)


def test_all_pages_have_same_eleven_navigation_links():
    result = module.patch_dashboard({"uid": "spacecube-db-connections", "panels": []})
    assert result["title"] == "Spacecube / DB 연결·대기"
    assert len(result["links"]) == 11
    assert len({v["url"] for v in result["links"]}) == 11
    assert all(v["keepTime"] and not v["targetBlank"] for v in result["links"])
