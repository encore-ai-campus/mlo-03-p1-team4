"""전체 Grafana 대시보드를 작은 상태 카드와 일정한 그래프 비율로 정리한다."""

import json
from pathlib import Path

root = Path(__file__).resolve().parent
links = [
    ("overview", "전체 현황"),
    ("servers", "서버"),
    ("nginx", "Nginx"),
    ("api", "FastAPI"),
    ("haproxy", "HAProxy"),
    ("alloy", "Alloy"),
    ("loki", "Loki"),
    ("logs", "로그"),
    ("storage", "저장소"),
]
for path in sorted(root.glob("dashboard-*.json")):
    board = json.loads(path.read_text(encoding="utf-8-sig"))
    panels = board["panels"]
    stats = [p for p in panels if p["type"] == "stat"]
    graphs = [p for p in panels if p["type"] not in ("stat", "logs", "text")]
    notes = [p for p in panels if p["type"] == "text"]
    logs = [p for p in panels if p["type"] == "logs"]
    stat_columns = min(4, max(1, len(stats)))
    stat_width = 24 // stat_columns
    for i, panel in enumerate(stats):
        panel["gridPos"] = {
            "x": i % stat_columns * stat_width,
            "y": i // stat_columns * 3,
            "w": stat_width,
            "h": 3,
        }
        panel["options"] = {
            "colorMode": "value",
            "graphMode": "none",
            "textMode": "value_and_name",
            "justifyMode": "auto",
            "orientation": "horizontal",
            "text": {"valueSize": 16, "titleSize": 11},
            "reduceOptions": {"calcs": ["lastNotNull"], "values": False},
        }
        for target in panel.get("targets", []):
            target["instant"] = True
            if target.get("expr") in ("up", "sum(up)"):
                target["expr"] = "sum(up)"
                panel["title"] = "정상 수집 대상 수"
                panel["options"].update(textMode="value", justifyMode="center")
        if board["uid"] == "spacecube-overview":
            panel["options"].update(textMode="value", justifyMode="center")
            panel["options"]["text"]["valueSize"] = 26
            panel.setdefault("fieldConfig", {}).setdefault("defaults", {})["color"] = {
                "mode": "fixed",
                "fixedColor": "blue",
            }
    y = ((len(stats) + 3) // 4) * 3
    for i, panel in enumerate(graphs):
        panel["gridPos"] = {"x": i % 2 * 12, "y": y + i // 2 * 7, "w": 12, "h": 7}
        if panel["type"] in ("piechart", "heatmap", "state-timeline", "barchart", "table"):
            continue
        panel["options"] = {
            "legend": {"displayMode": "list", "placement": "bottom", "calcs": []},
            "tooltip": {"mode": "multi", "sort": "desc"},
        }
        custom = (
            panel.setdefault("fieldConfig", {}).setdefault("defaults", {}).setdefault("custom", {})
        )
        custom.update(
            drawStyle="line",
            lineInterpolation="linear",
            lineWidth=1,
            fillOpacity=6,
            showPoints="never",
            spanNulls=False,
            axisBorderShow=False,
        )
    y += ((len(graphs) + 1) // 2) * 7
    for panel in notes:
        panel["gridPos"] = {"x": 0, "y": y, "w": 24, "h": 4}
        y += 4
    for panel in logs:
        panel["gridPos"] = {"x": 0, "y": y, "w": 24, "h": 16 if len(panels) == 1 else 9}
        panel.setdefault("options", {}).update(
            showTime=True,
            showLabels=False,
            wrapLogMessage=False,
            sortOrder="Descending",
            enableLogDetails=True,
        )
        y += panel["gridPos"]["h"]
    for panel in panels:
        defaults = panel.setdefault("fieldConfig", {}).setdefault("defaults", {})
        defaults["noValue"] = "수집 없음"
        if "unit" not in defaults:
            title = panel.get("title", "")
            defaults["unit"] = (
                "percent" if "사용률" in title else "bytes" if "디스크 여유" in title else "short"
            )
        unit = defaults["unit"]
        if panel["type"] in ("stat", "timeseries"):
            defaults.setdefault("min", 0)
            defaults["decimals"] = 1 if unit in ("percent", "reqps", "cps", "ops", "bytes") else 0
            if unit == "percent":
                defaults["max"] = 100
            if unit == "s":
                defaults["unit"] = "ms"
                for target in panel.get("targets", []):
                    target["expr"] = "1000 * (" + target["expr"] + ")"
            for target in panel.get("targets", []):
                expr = target.get("expr", "").replace(
                    'mode="idle"[$__rate_interval]', 'mode="idle"}[$__rate_interval]'
                )
                if "node_cpu_seconds_total" in expr:
                    expr = expr.replace("avg by(instance)", "avg by(server)")
                target["expr"] = expr
                target["interval"] = "15s"
                if not target.get("legendFormat"):
                    target["legendFormat"] = "{{server}} · {{instance}}"
    board["panels"] = stats + graphs + notes + logs
    if board["uid"] == "spacecube-storage":
        for panel in graphs:
            panel["gridPos"]["y"] += 4
            panel["title"] = panel["title"].replace(" — DB 연결 후", " · 수집된 워커")
        for panel in notes:
            panel["gridPos"]["y"] = 0
        board["panels"] = notes + stats + graphs + logs
    board["links"] = [
        {
            "type": "link",
            "title": label,
            "url": "/d/spacecube-" + uid,
            "keepTime": True,
            "includeVars": True,
            "targetBlank": False,
        }
        for uid, label in links
    ]
    board["tags"] = [t for t in board.get("tags", []) if t != "db-disconnected"]
    board["description"] = (
        "109 최소 사양 시험. MariaDB primary·replica exporter가 수집 중이며 MongoDB는 온라인이며 exporter는 미설치입니다. FastAPI 지표는 현재 수집 워커 기준. 빈 구간은 0을 뜻하지 않습니다."
    )
    board["version"] = board.get("version", 1)
    board["refresh"] = "15s"
    board["timepicker"] = {"refresh_intervals": ["15s", "30s", "1m", "5m"]}
    path.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path.name, len(panels))
