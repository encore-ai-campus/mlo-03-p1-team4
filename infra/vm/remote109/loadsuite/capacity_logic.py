"""실패 탐색의 계정 정합성과 지연 중단 판정."""

import math
from itertools import pairwise


def validate_host_sample(record, now):
    if record.get("host_sample_error") or "vmware_windows_host" not in record:
        raise ValueError("host_observation_failed")
    if not 0 <= now - record["time"] <= 75:
        raise ValueError("host_observation_stale")
    if int(record["vmware_windows_host"]["ram_free_kib"]) < 8 * 1024**2:
        raise ValueError("host_memory_low")


def audit_count(audit):
    """자기 시험 계정의 환불/슬롯/복제/이벤트를 확인한다."""
    totals = []
    for db in audit["dbs"]:
        rows = [r.split("\t") for r in db["rows"]]
        states = [
            r
            for r in rows
            if r[0] not in {"users", "remaining_slots", "synthetic_reservations", "151"}
        ]
        if len(states) != 1 or states[0][:2] != ["cancelled", "refunded"]:
            raise ValueError("reservation_payment_not_clean")
        total = int(states[0][2])
        if ["remaining_slots", "0"] not in rows:
            raise ValueError("remaining_slots")
        if ["synthetic_reservations", str(total), str(total)] not in rows:
            raise ValueError("synthetic_mismatch")
        rep = db["replication"]
        if rep and (
            rep.get("Slave_IO_Running") != "Yes"
            or rep.get("Slave_SQL_Running") != "Yes"
            or rep.get("Seconds_Behind_Master") != "0"
        ):
            raise ValueError("replication_not_clean")
        totals.append(total)
    if len(totals) != 2 or totals[0] != totals[1]:
        raise ValueError("db_count_mismatch")
    counts = {r["_id"]: r["count"] for r in audit["mongo"]["own_event_names"]}
    if any(
        counts.get(name, 0) != totals[0]
        for name in ["reservation_complete", "reservation_cancel_complete"]
    ):
        raise ValueError("event_count_mismatch")
    if (
        audit["mongo"]["own_events"] != 2 * totals[0]
        or audit["mongo"]["own_synthetic_events"] != 2 * totals[0]
    ):
        raise ValueError("event_total_mismatch")
    return totals[0]


def latency_failed(rows, start, kind):
    """60초 구간 2개 연속 기준 초과를 판정한다. 경계 요청은 제외한다."""
    limit = 500 if kind == "book" else 300
    failed = []
    for offset in range(3):
        lo, hi = start + offset * 60, start + (offset + 1) * 60
        values = sorted(
            r["ms"]
            for r in rows
            if lo <= r["started"] <= r["finished"] <= hi
            and not r["failed"]
            and (
                (
                    kind == "book"
                    and r["method"] == "POST"
                    and r["name"] == "/reservations"
                    and r["status"] == 201
                )
                or (kind == "public" and r["method"] == "GET")
            )
        )
        failed.append(len(values) >= 100 and values[math.ceil(len(values) * 0.95) - 1] > limit)
    return any(a and b for a, b in pairwise(failed))
