"""Client for the F-61 internal venue upsert endpoint."""

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import required_env


def post_internal_venue(payload: dict[str, Any]) -> dict[str, Any]:
    # 전처리된 공간을 F-61 내부 API에 등록하거나 갱신한다.
    base_url = os.getenv("INTERNAL_API_BASE_URL", "http://api1:8000").rstrip("/")
    request = Request(
        f"{base_url}/internal/venues",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Internal-Key": required_env("INTERNAL_API_KEY"),
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=20) as response:
            if response.status not in (200, 201):
                raise RuntimeError(f"/internal/venues returned HTTP {response.status}")
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"/internal/venues returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach /internal/venues: {exc.reason}") from exc

    venue_id = body.get("venue_id")
    ignored_facilities = body.get("ignored_facilities")
    if not isinstance(venue_id, int) or venue_id < 1:
        raise RuntimeError("/internal/venues response has no valid venue_id")
    if not isinstance(ignored_facilities, list):
        raise RuntimeError("/internal/venues response has no ignored_facilities list")
    return body
