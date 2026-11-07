"""Locust 단계별 HTTP 결과와 VM 자원 관측값을 Markdown으로 정리한다."""

import csv
import json
import sys
from pathlib import Path

folder = Path(sys.argv[1]).resolve()
with (folder / "summary.csv").open(encoding="utf-8-sig", newline="") as stream:
    rows = list(csv.DictReader(stream))
lines = [
    "# Locust 조회 부하 단계 기록",
    "",
    "조회 GET 시험. 단계별 실행 시간은 summary.csv의 seconds 열을 확인한다. 동시성·워커 설정은 이 보고서에서 자동 검증하지 않으므로 별도 실험 기록과 대조한다.",
    "",
    "| 목표/실제 최고 사용자 | 요청 | 실패 | RPS | p95 ms | 통과 |",
    "|---|---:|---:|---:|---:|---|",
]
for row in rows:
    lines.append(
        f"| {row['users']}/{row['actual_peak_users']} | {row['requests']} | {row['failures']} | {float(row['rps']):.2f} | {row['p95_ms']} | {row['passed']} |"
    )
lines += [
    "",
    "## 단계별 VM 자원",
    "",
    "CPU는 1분 rate를 15초 간격으로 관측한 값, 메모리는 MemAvailable 기준 점유율이다. 순간 피크·프로세스별 메모리가 아니다. 모니터링 누락은 0으로 해석하지 않는다.",
    "",
    "| 사용자 | 서버 | 지표 | 평균 % | 관측 최고 % | 최고 시각(UTC epoch) |",
    "|---:|---|---|---:|---:|---|",
]
resource_rows = []
for row in rows:
    for kind in ["cpu", "memory"]:
        path = folder / f"{kind}-{row['users']}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        for series in data["data"]["result"]:
            samples = [(float(t), float(v)) for t, v in series.get("values", [])]
            if not samples:
                continue
            peak_t, peak = max(samples, key=lambda item: item[1])
            avg = sum(v for _, v in samples) / len(samples)
            server = series["metric"].get("server", "?")
            lines.append(
                f"| {row['users']} | {server} | {kind} | {avg:.1f} | {peak:.1f} | {peak_t:.0f} |"
            )
            resource_rows.append(
                {
                    "users": row["users"],
                    "server": server,
                    "metric": kind,
                    "average": avg,
                    "maximum": peak,
                    "peak_epoch": peak_t,
                }
            )
lines += [
    "",
    "예비 기준: 실패율 1% 이하·p95 500ms 이하·실제 목표 인원 도달. 실행 시간에는 램프업을 포함하며 절대 최대 성능을 판정하지 않는다.",
    "",
    "HTTP 원본 CSV·HTML 위치는 summary.csv의 report 열, 각 단계 SSH 점검은 before-*.json, 최종 점검은 after.json 참조.",
]
(folder / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
with (folder / "resources.csv").open("w", encoding="utf-8-sig", newline="") as stream:
    writer = csv.DictWriter(
        stream, fieldnames=["users", "server", "metric", "average", "maximum", "peak_epoch"]
    )
    writer.writeheader()
    writer.writerows(resource_rows)
print(str(folder / "RESULTS.md"))
