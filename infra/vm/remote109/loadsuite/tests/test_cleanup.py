"""보고서/공용 작업판 쓰기 실패가 잠금 유출로 이어지지 않는지 검증한다."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).parents[1]
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("load_runner", HERE / "runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
sys.path.pop(0)


def finished_script(tmp_path, monkeypatch):
    suite = runner.Suite("http://192.168.219.218", tmp_path / "report")
    suite.claimed = True
    suite.key, suite.password, suite.tokens = "secret", "secret", {1: "token"}
    scripts = []
    monkeypatch.setattr(runner, "remote", lambda script: scripts.append(script))

    def fail_report(_error):
        raise OSError("disk_full")

    monkeypatch.setattr(suite, "write_summary", fail_report)
    suite.finish("test_abort")
    assert suite.key == suite.password == "" and suite.tokens == {}
    assert len(scripts) == 1
    return scripts[0], suite.run_id


def test_report_failure_still_attempts_remote_lock_release(tmp_path, monkeypatch):
    finished_script(tmp_path, monkeypatch)


def test_remote_board_write_failure_still_releases_own_lock(tmp_path, monkeypatch):
    script, run_id = finished_script(tmp_path, monkeypatch)
    op = tmp_path / ".server-operation.lock"
    op.mkdir()
    (op / "runner").write_text(run_id)
    (op / "owner").write_text(runner.TASK)
    board = tmp_path / "SERVER_WORK_BOARD.md"
    board.write_text("| CODEX-LOAD-20261107 | Codex | active | run | info |")
    original = Path.write_text

    def fail_board(path, *args, **kwargs):
        if path == board:
            raise OSError("board_disk_full")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_board)
    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(flock=lambda *_: None, LOCK_EX=2))
    script = script.replace(
        "Path('/home/playdata/spacecube109')", "Path(" + repr(str(tmp_path)) + ")"
    )
    with pytest.raises(OSError, match="board_disk_full"):
        exec(compile(script, "remote_cleanup_test", "exec"), {})  # noqa: S102 고정 실행기 정리 코드만 임시 디렉터리로 바꿔 격리 검증
    assert not op.exists()
