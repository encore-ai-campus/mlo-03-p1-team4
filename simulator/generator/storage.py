"""새 DB 표 없이 실행 입력과 작업별 결과를 원자적으로 보관한다."""

import json
import os
from pathlib import Path

from .plan import GeneratorError, digest


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    # Linux의 전원 중단에서도 rename 결과를 보존한다. Windows는 파일 fsync를 사용한다.
    if os.name != "nt":
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


class Journal:
    def __init__(self, directory, manifest, *, resume=False):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / "manifest.json"
        if path.exists():
            if not resume:
                raise GeneratorError("기존 실행입니다. 같은 입력으로 --resume을 사용하세요.")
            saved = json.loads(path.read_text(encoding="utf-8"))
            if digest(saved) != digest(manifest):
                raise GeneratorError("설정·대상 DB·공간 스냅샷·생성기 버전이 기존 실행과 다릅니다.")
        else:
            if resume:
                raise GeneratorError("재개할 manifest.json이 없습니다.")
            atomic_json(path, manifest)
        self.path = self.directory / "state.json"
        self.operations = (
            json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        )

    def save(self, key, value):
        self.operations[key] = value
        atomic_json(self.path, self.operations)

    def perform(self, key, recover, execute):
        """커밋 후 파일 기록 전에 끊겨도 DB를 먼저 대조한다."""
        saved = self.operations.get(key)
        recovered = recover()
        if saved is not None:
            if recovered != saved:
                raise GeneratorError(f"저장된 작업 결과와 DB가 다릅니다: {key}")
            return saved
        result = recovered if recovered is not None else execute()
        self.save(key, result)
        return result
