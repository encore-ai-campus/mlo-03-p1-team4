"""저장된 Terraform 계획에서 삭제·교체와 전원 변경 외 작업을 거부한다."""

import json
import sys

plan = json.load(sys.stdin)
policy = sys.argv[1]
roles = ("gw", "api1", "api2", "mon")
vms = {f'vmworkstation_virtual_machine.node["{role}"]' for role in roles}
seeds = {f'terraform_data.seed["{role}"]' for role in roles}
for resource in plan.get("resource_changes", []):
    if resource.get("mode") != "managed":
        continue
    address = resource["address"]
    change = resource["change"]
    actions = change["actions"]
    if address not in vms | seeds or "delete" in actions:
        raise SystemExit("관리 범위 밖 또는 삭제·교체 계획 거부: " + address)
    if actions == ["no-op"]:
        continue
    if policy == "power":
        if address not in vms or actions != ["update"]:
            raise SystemExit("전원 외 리소스 변경 거부: " + address)
        before, after = change.get("before") or {}, change.get("after") or {}
        differences = {
            key for key in before.keys() | after.keys() if before.get(key) != after.get(key)
        }
        if differences - {"state"}:
            raise SystemExit("전원 외 속성 변경 거부: " + address)
    elif policy != "create":
        raise SystemExit("알 수 없는 계획 정책")
print("삭제·교체 없음, 계획 정책 검사 통과")
