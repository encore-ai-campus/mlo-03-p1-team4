#!/bin/bash
# 109 WSL 전용. 모든 변경은 저장 계획을 검사한 뒤 같은 계획으로 적용한다.
set -euo pipefail
self_dir=$(cd "$(dirname "$0")" && pwd)
cd "$self_dir"
bash /mnt/c/Users/Playdata/wsl-vmware-lab/preflight.sh
export LAB_VM_ROOT_WIN='C:\Users\Playdata\Documents\Virtual Machines'
source /mnt/c/Users/Playdata/wsl-vmware-lab/lib/config.sh
lab_terraform_env
cd "$self_dir"
private="$HOME/.config/spacecube109"
install -d -m 700 "$private"
if test ! -f "$private/id_ed25519"; then
  ssh-keygen -q -t ed25519 -N '' -f "$private/id_ed25519"
fi
terraform init -input=false
terraform validate
plan_file=''
trap 'test -z "${plan_file:-}" || rm -f -- "$plan_file"' EXIT
safe_apply() {
  local desired=$1 policy=$2
  plan_file=$(mktemp "$private/spacecube-plan.XXXXXX.tfplan")
  terraform plan -input=false -out="$plan_file" -var="power_state=$desired"
  terraform show -json "$plan_file" | python3 "$self_dir/plan_guard.py" "$policy"
  terraform apply -input=false -parallelism=1 "$plan_file"
  rm -f -- "$plan_file"
  plan_file=''
}
case "${1:-plan}" in
  plan) terraform plan -input=false -var=power_state=on ;;
  create)
    seeded=$(terraform state list | grep -c '^terraform_data.seed\[' || true)
    if test "$seeded" -eq 4; then
      safe_apply on power
    else
      safe_apply off create
      safe_apply on power
    fi
    ;;
  status) terraform output -json nodes ;;
  on|off)
    owned=$(terraform state list | grep -c '^vmworkstation_virtual_machine.node\[' || true)
    test "$owned" -eq 4 || { echo 'VM 4대가 모두 상태에 있어야 전원을 변경합니다.' >&2; exit 1; }
    safe_apply "$1" power
    ;;
  *) echo '사용법: terraform.sh plan|create|status|on|off' >&2; exit 2 ;;
esac
