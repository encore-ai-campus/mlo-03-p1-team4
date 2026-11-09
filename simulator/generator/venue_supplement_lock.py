"""#99·#100 공간 작업이 공유하는 프로세스 잠금."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK_ENV = "SPACECUBE_VENUE_LOCK_FD"
PARENT_ENV = "SPACECUBE_VENUE_LOCK_PARENT"


class LockUnavailable(RuntimeError):
    """다른 보충 또는 통합 실행기가 잠금을 보유 중이다."""


class VenuePipelineLock:
    def __init__(self, path=None):
        self.path = Path(path or ROOT / "logs" / ".venue-pipeline.lock").resolve()
        self.stream = None
        self.inherited = False

    def __enter__(self):
        inherited_fd = os.environ.get(LOCK_ENV)
        if inherited_fd is not None:
            self._verify_inherited(inherited_fd)
            self.inherited = True
            return self

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+b")
        if os.fstat(self.stream.fileno()).st_size == 0:
            self.stream.write(b"\0")
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as error:
            self.stream.close()
            self.stream = None
            raise LockUnavailable("공간 보충 또는 통합 실행이 이미 진행 중입니다.") from error
        return self

    def _verify_inherited(self, raw_fd):
        try:
            descriptor = int(raw_fd)
            parent_pid = int(os.environ[PARENT_ENV])
            if os.getppid() != parent_pid:
                raise ValueError
            file_stat = os.fstat(descriptor)
            path_stat = self.path.stat()
            if (file_stat.st_dev, file_stat.st_ino) != (path_stat.st_dev, path_stat.st_ino):
                raise ValueError
        except (KeyError, OSError, TypeError, ValueError):
            raise LockUnavailable("상위 실행기의 공간 작업 잠금을 확인할 수 없습니다.") from None

    def child_options(self):
        """잠금 FD를 자식 프로세스에 넘겨 같은 잠금을 유지한다."""
        if self.stream is None or self.inherited:
            raise LockUnavailable("현재 프로세스가 공간 작업 잠금을 소유하지 않습니다.")
        environment = os.environ.copy()
        descriptor = self.stream.fileno()
        environment[LOCK_ENV] = str(descriptor)
        environment[PARENT_ENV] = str(os.getpid())
        if os.name == "nt":
            os.set_inheritable(descriptor, True)
            return {"env": environment, "close_fds": False}
        return {"env": environment, "pass_fds": (descriptor,)}

    def __exit__(self, exc_type, exc, traceback):
        if self.stream is None or self.inherited:
            return
        try:
            self.stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        finally:
            if os.name == "nt":
                os.set_inheritable(self.stream.fileno(), False)
            self.stream.close()
            self.stream = None
