import pytest

from app.core import logging as app_logging


def test_thread_lock_timeout_has_a_specific_reason(monkeypatch, tmp_path):
    class BusyLock:
        def acquire(self, timeout):
            assert timeout == 0.1
            return False

        def release(self):
            raise AssertionError("획득하지 못한 잠금은 해제하지 않아야 함")

    monkeypatch.setattr(app_logging, "_file_lock", BusyLock())
    app_logging.event_file_lock_wait_seconds.labels(scope="thread")
    samples_before = next(
        sample.value
        for family in app_logging.event_file_lock_wait_seconds.collect()
        for sample in family.samples
        if sample.name == "event_file_lock_wait_seconds_count"
    )

    with (
        pytest.raises(app_logging.EventFileLockTimeout) as error,
        app_logging._process_lock(tmp_path / "events.log"),
    ):
        pass

    assert error.value.scope == "thread"
    assert error.value.stage == "thread_lock"
    assert error.value.reason == "lock_timeout"
    samples_after = next(
        sample.value
        for family in app_logging.event_file_lock_wait_seconds.collect()
        for sample in family.samples
        if sample.name == "event_file_lock_wait_seconds_count"
    )
    assert samples_after == samples_before + 1


def test_serialization_failure_is_classified_before_file_access(tmp_path):
    before = next(
        sample.value
        for family in app_logging.event_file_write_duration_seconds.collect()
        for sample in family.samples
        if sample.name == "event_file_write_duration_seconds_count"
    )

    with pytest.raises(app_logging.EventFileWriteError) as error:
        app_logging.append_json(tmp_path / "events.log", {"not_json": object()})

    assert error.value.stage == "serialize"
    assert error.value.reason == "serialization_error"
    assert not (tmp_path / "events.log").exists()
    after = next(
        sample.value
        for family in app_logging.event_file_write_duration_seconds.collect()
        for sample in family.samples
        if sample.name == "event_file_write_duration_seconds_count"
    )
    assert after == before + 1
