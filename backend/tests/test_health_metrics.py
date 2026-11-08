"""F-70 저장소 상태 지표와 기존 헬스 응답 계약."""

import pytest
from prometheus_client import REGISTRY

from app.core.errors import AppError
from app.services import health_service


def test_degraded_health_records_each_dependency(monkeypatch):
    monkeypatch.setattr(health_service, "check_database", lambda mode: mode == "write")
    monkeypatch.setattr(health_service, "check_mongo", lambda: False)
    try:
        assert health_service.get_health() == {
            "status": "degraded",
            "replica": "down",
            "mongo": "down",
        }
        assert REGISTRY.get_sample_value("health_dependency_up", {"dependency": "primary"}) == 1
        assert REGISTRY.get_sample_value("health_dependency_up", {"dependency": "replica"}) == 0
        assert REGISTRY.get_sample_value("health_dependency_up", {"dependency": "mongo"}) == 0
    finally:
        health_service.stop_health_checks()


def test_primary_failure_still_returns_503_and_records_status(monkeypatch):
    monkeypatch.setattr(health_service, "check_database", lambda _mode: False)
    monkeypatch.setattr(health_service, "check_mongo", lambda: True)
    try:
        with pytest.raises(AppError) as error:
            health_service.get_health()
        assert error.value.status == 503
        assert REGISTRY.get_sample_value("health_dependency_up", {"dependency": "primary"}) == 0
    finally:
        health_service.stop_health_checks()
