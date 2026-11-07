"""호출자가 출력값을 환경변수로 받기 위한 합성 시험 키 조회기. 콘솔 공유 금지."""

from pathlib import Path

path = Path.home() / ".config/spacecube109/app/.env"
values = dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)
print(values["SYNTHETIC_API_KEY"])
