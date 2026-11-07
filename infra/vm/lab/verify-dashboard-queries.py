#!/usr/bin/env python3
"""Grafana provisioning files의 PromQL·LogQL을 실제 서버에서 검증한다."""

import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

DASHBOARD_DIR = Path("/var/lib/grafana/dashboards")
PROMETHEUS = "http://127.0.0.1:9090"
LOKI = "http://127.0.0.1:3100"
MACROS = {"$__rate_interval": "5m", "$__range": "30m", "$__interval": "30s"}


def get_json(base, path, params):
    url = f"{base}{path}?{urlencode(params)}"
    with urlopen(url, timeout=12) as response:  # noqa: S310 localhost-only metrics services
        return json.load(response)


def evaluate(source, query):
    if source == "prometheus":
        result = get_json(PROMETHEUS, "/api/v1/query", {"query": query})
    else:
        end = time.time_ns()
        result = get_json(
            LOKI,
            "/loki/api/v1/query_range",
            {
                "query": query,
                "start": end - 1_800_000_000_000,
                "end": end,
                "limit": 1,
                "direction": "backward",
            },
        )
    if result.get("status") != "success":
        raise ValueError(result.get("errorType", "query failed"))
    data = result.get("data", {})
    return bool(data.get("result"))


def main():
    files = sorted(DASHBOARD_DIR.glob("dashboard-*.json"))
    if len(files) != 11:
        raise RuntimeError(f"dashboard files={len(files)}, expected=11")

    checked = {"prometheus": 0, "loki": 0}
    empty = {"prometheus": 0, "loki": 0}
    failures = []
    for path in files:
        dashboard = json.loads(path.read_text(encoding="utf-8"))
        for panel in dashboard.get("panels", []):
            panel_ds = panel.get("datasource", dashboard.get("datasource", {}))
            for target in panel.get("targets", []):
                ds = target.get("datasource", panel_ds)
                source = ds.get("uid", "prometheus") if isinstance(ds, dict) else ds
                source = "loki" if source == "loki" else "prometheus"
                query = target.get("expr") or target.get("query")
                if not query:
                    continue
                for macro, value in MACROS.items():
                    query = query.replace(macro, value)
                checked[source] += 1
                try:
                    if not evaluate(source, query):
                        empty[source] += 1
                except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                    failures.append(
                        {
                            "dashboard": path.name,
                            "panel": panel.get("id"),
                            "source": source,
                            "error": str(exc)[:100],
                        }
                    )

    report = {
        "dashboards": len(files),
        "queries_checked": checked,
        "empty_results": empty,
        "errors": failures,
    }
    print(json.dumps(report, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
