"""실제 브라우저 시험의 출력·보고서에서 합성 키를 제외한다."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
key = os.environ["SPACE_SYNTHETIC_KEY"]
frontend = Path(os.environ["SPACE_FRONTEND_DIR"])
node = shutil.which("node")
if not node:
    raise SystemExit("Node 실행 파일이 없습니다.")
result = subprocess.run(  # noqa: S603 지정한 frontend의 Playwright CLI만 실행
    [
        node,
        str(frontend / "node_modules/@playwright/test/cli.js"),
        "test",
        "--config",
        str(Path(__file__).with_name("playwright.config.mjs")),
    ],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    check=False,
)
for path in Path(os.environ["SPACE_REPORT_DIR"]).rglob("*"):
    if path.is_file() and path.suffix in {".json", ".txt", ".md", ".html", ".csv", ".log"}:
        content = path.read_text(encoding="utf-8", errors="replace")
        if key in content:
            path.write_text(content.replace(key, "[REDACTED]"), encoding="utf-8")
print((result.stdout + result.stderr).replace(key, "[REDACTED]"))
sys.exit(result.returncode)
