"""실제 배포 묶음이 독립 헬스·큐·219망을 보존하고 반복 생성해도 같은지 검증."""

import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path


def test_runtime_bundle_preserves_health_and_queue(tmp_path):
    original = Path(__file__).parents[2]
    repo = tmp_path / "repo"
    target = repo / "infra/vm/remote109"
    target.mkdir(parents=True)
    shutil.copytree(original.parent / "lab", target.parent / "lab")
    shutil.copyfile(original / "build_config.py", target / "build_config.py")
    home = tmp_path / "home"
    (home / "spacecube109").mkdir(parents=True)
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    command = [sys.executable, str(target / "build_config.py")]
    subprocess.run(command, env=env, check=True, capture_output=True)  # noqa: S603 고정 빌더를 격리된 공개 fixture에서 실행
    bundle = home / "spacecube109/config.tar.gz"
    first = hashlib.sha256(bundle.read_bytes()).hexdigest()
    with tarfile.open(bundle) as archive:
        nginx = archive.extractfile("nginx.conf").read().decode()
        haproxy = archive.extractfile("haproxy-final.cfg").read().decode()
        unit = archive.extractfile("spacecube-health.service").read().decode()
        assert nginx.count("127.0.0.1:8001/health") == 2
        assert "timeout queue 5s" in haproxy
        assert haproxy.count("maxconn 50") == 2
        assert "192.168.219.214:80" in haproxy
        assert "192.168.0." not in haproxy
        assert "WantedBy=spacecube.service" in unit
        assert "127.0.0.1 --port 8001" in unit
        assert archive.extractfile("health_app.py").read()
    subprocess.run(command, env=env, check=True, capture_output=True)  # noqa: S603 동일 격리 fixture의 반복 생성 검증
    assert first == hashlib.sha256(bundle.read_bytes()).hexdigest()
