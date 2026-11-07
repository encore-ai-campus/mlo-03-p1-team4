"""F-61 수집 실행기가 저장소 루트에서 백엔드 공용 모듈을 찾도록 한다."""

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
