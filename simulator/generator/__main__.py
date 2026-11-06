"""저장소 루트에서 python -m simulator.generator로 실행한다."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from .cli import main

raise SystemExit(main())
