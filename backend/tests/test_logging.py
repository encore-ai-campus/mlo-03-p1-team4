"""F-64: 파일 잠금 경합과 JSON 줄 기록 회귀."""

import json
from multiprocessing import get_context
from pathlib import Path
from threading import Event, Thread
from time import sleep

from app.core import logging as app_logging


def hold_process_lock(path: Path, lock_acquired) -> None:
    with app_logging._process_lock(path):
        lock_acquired.set()
        sleep(0.15)


def test_append_json_waits_for_short_same_process_lock_contention(tmp_path):
    path = tmp_path / "events.log"
    lock_acquired = Event()

    def hold_file_lock():
        with app_logging._file_lock:
            lock_acquired.set()
            sleep(0.15)

    holder = Thread(target=hold_file_lock)
    holder.start()
    assert lock_acquired.wait(timeout=1)

    app_logging.append_json(path, {"event_id": "lock-wait-test"})
    holder.join(timeout=1)

    assert not holder.is_alive()
    assert json.loads(path.read_text(encoding="utf-8")) == {"event_id": "lock-wait-test"}


def test_append_json_waits_for_short_cross_process_lock_contention(tmp_path):
    path = tmp_path / "events.log"
    process_context = get_context("spawn")
    lock_acquired = process_context.Event()
    holder = process_context.Process(target=hold_process_lock, args=(path, lock_acquired))
    holder.start()
    assert lock_acquired.wait(timeout=5)

    app_logging.append_json(path, {"event_id": "process-lock-wait-test"})
    holder.join(timeout=5)

    assert holder.exitcode == 0
    assert json.loads(path.read_text(encoding="utf-8")) == {"event_id": "process-lock-wait-test"}
