"""stdin 자격증명을 Git 밖의 보호된 .env에 저장한다. 비밀값은 출력하지 않는다."""

import json
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import quote

os.umask(0o077)
private = Path.home() / ".config/spacecube109"
data = json.load(sys.stdin)
password = data["db_password"]
if not password:
    raise SystemExit("DB 비밀번호가 필요합니다.")
app = private / "app/.env"
app.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
old = (
    dict(line.split("=", 1) for line in app.read_text().splitlines() if "=" in line)
    if app.exists()
    else {}
)
username = quote(data.get("db_user", "team4"), safe="")
encoded_password = quote(password, safe="")
settings = {
    "DB_WRITE_URL": f"mysql+pymysql://{username}:{encoded_password}@192.168.0.212:3306/spacecube?charset=utf8mb4",
    "DB_READ_URL": f"mysql+pymysql://{username}:{encoded_password}@192.168.0.213:3306/spacecube?charset=utf8mb4",
    "MONGO_URL": "",
    "MONGO_DB": "spacecube",
    "JWT_SECRET": old.get("JWT_SECRET") or secrets.token_hex(32),
    "SYNTHETIC_API_KEY": old.get("SYNTHETIC_API_KEY") or secrets.token_hex(32),
    "INTERNAL_API_KEY": old.get("INTERNAL_API_KEY") or secrets.token_hex(32),
    "CORS_ORIGINS": "http://192.168.0.218,http://localhost:5173",
    "TODAY_OVERRIDE": "",
}
app.write_text("\n".join(f"{key}={value}" for key, value in settings.items()) + "\n")
app.chmod(0o600)
grafana = private / "grafana/.env"
grafana.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
if not grafana.exists():
    grafana.write_text("GF_SECURITY_ADMIN_PASSWORD=" + secrets.token_urlsafe(24) + "\n")
    grafana.chmod(0o600)
print("앱·Grafana 보호된 .env 준비 완료 (비밀값 출력 없음)")
