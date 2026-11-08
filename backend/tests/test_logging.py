import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Timer

import pytest

from app.core import logging as app_logging


def test_app_file_lock_does_not_block_event_file(tmp_path):
    entered, release = Event(), Event()

    def hold_app():
        with app_logging._process_lock(tmp_path / "app.log"):
            entered.set()
            assert release.wait(5)

    with ThreadPoolExecutor(max_workers=1) as executor:
        holder = executor.submit(hold_app)
        try:
            assert entered.wait(5)
            app_logging.append_json(tmp_path / "events.log", {"event_id": "independent"})
            assert json.loads((tmp_path / "events.log").read_text()) == {"event_id": "independent"}
        finally:
            release.set()
            holder.result(timeout=5)


def test_event_write_survives_short_same_file_contention(tmp_path):
    entered, release = Event(), Event()

    def hold_event():
        with app_logging._process_lock(tmp_path / "events.log"):
            entered.set()
            assert release.wait(5)

    with ThreadPoolExecutor(max_workers=1) as executor:
        holder = executor.submit(hold_event)
        timer = Timer(0.2, release.set)
        try:
            assert entered.wait(5)
            timer.start()
            app_logging.append_json(tmp_path / "events.log", {"event_id": "waited"})
            assert json.loads((tmp_path / "events.log").read_text()) == {"event_id": "waited"}
        finally:
            release.set()
            timer.cancel()
            holder.result(timeout=5)


def test_same_file_alias_still_times_out_while_owned(tmp_path):
    entered, release = Event(), Event()
    (tmp_path / "sub").mkdir()

    def hold_event():
        with app_logging._process_lock(tmp_path / "events.log"):
            entered.set()
            assert release.wait(5)

    with ThreadPoolExecutor(max_workers=1) as executor:
        holder = executor.submit(hold_event)
        try:
            assert entered.wait(5)
            with pytest.raises(app_logging.EventFileLockTimeout) as error:
                app_logging.append_json(tmp_path / "sub" / ".." / "events.log", {})
            assert error.value.stage == "thread_lock"
        finally:
            release.set()
            holder.result(timeout=5)


def test_concurrent_same_file_writes_preserve_json_lines(tmp_path):
    path = tmp_path / "events.log"
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda number: app_logging.append_json(path, {"id": number}), range(64)))
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 64
    assert {row["id"] for row in rows} == set(range(64))


def test_thread_lock_timeout_has_a_specific_reason(monkeypatch, tmp_path):
    class BusyLock:
        def acquire(self, timeout):
            assert timeout == 0.5
            return False

        def release(self):
            raise AssertionError("획득하지 못한 잠금은 해제하지 않아야 함")

    monkeypatch.setattr(app_logging, "_thread_lock_for", lambda _path: BusyLock())
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
