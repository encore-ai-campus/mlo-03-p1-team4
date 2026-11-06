"""기존 공개 설정을 109의 실제 gw 주소로 렌더링한다. 비밀값은 포함하지 않는다."""

import gzip
import io
import tarfile
from pathlib import Path

source = Path(__file__).resolve().parent.parent / "lab"
target = Path.home() / "spacecube109/config.tar.gz"
allowed = {
    "haproxy.cfg",
    "haproxy-final.cfg",
    "nginx.conf",
    "prometheus.yml",
    "loki.yml",
    "install-role.sh",
    "refresh-observability.sh",
    "backend-requirements.txt",
    "verify-grafana.py",
}
with (
    target.open("wb") as output,
    gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=0) as zipped,
    tarfile.open(fileobj=zipped, mode="w") as archive,
):
    for path in sorted(source.iterdir()):
        if not path.is_file() or not (
            path.name in allowed or (path.name.startswith("dashboard-") and path.suffix == ".json")
        ):
            continue
        content = (
            path.read_text(encoding="utf-8").replace("192.168.0.211", "192.168.0.218").encode()
        )
        info = tarfile.TarInfo(path.name)
        info.size = len(content)
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(content))
print("109 공개 설정 묶음 생성: gw 192.168.0.218")
