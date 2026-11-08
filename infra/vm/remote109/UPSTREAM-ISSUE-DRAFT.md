# 이슈 초안 — 사용자 지정 VM 경로 사용 시 provider `.path` 불일치

게시 대상: https://github.com/naelonambul/wsl-vmware-lab/issues

https://github.com/naelonambul/wsl-vmware-lab/issues/1 에 게시한 익명화 초안의 보관본입니다. 원본 로그·Terraform state·inventory·인증 파일은 첨부하지 않습니다.

## 현상

등록된 Ubuntu 템플릿과 `lib/config.sh`를 재사용한 별도 Terraform 프로젝트에서, `vmworkstation_virtual_machine.path`를 기본 VM 폴더 밖으로 지정하면 clone 생성 후 provider의 경로 일관성 오류가 발생했습니다.

이 저장소의 기본 예제를 그대로 실행한 재현은 아닙니다. 사용자 지정 `LAB_VM_ROOT_WIN`의 지원 범위를 문서에서 확인하고 싶습니다.

## 환경

- Windows + WSL2 Ubuntu 24.04, mirrored networking
- Terraform 1.17.1
- `elsudano/vmworkstation` 2.0.1
- 준비된 Ubuntu 24.04 cloud image, preflight exit 0
- vmrest 인증 정보·기존 Terraform state는 별도 프로젝트로 복사하지 않았습니다.

## 최소 구성 요지

```hcl
resource "vmworkstation_virtual_machine" "example" {
  sourceid     = data.vmworkstation_virtual_machine.base.id
  denomination = "example-app"
  description  = data.vmworkstation_virtual_machine.base.description
  path         = "C:\\Users\\<USER>\\custom-lab\\example-app\\example-app.vmx"
  processors   = 1
  memory       = 1536
  state        = "off"
}
```

## 관측한 오류 (익명화)

```text
Provider produced inconsistent result after apply
unexpected new value: .path
planned: C:\Users\<USER>\custom-lab\example-app\example-app.vmx
actual:  C:\Users\<USER>\Documents\Virtual Machines\example-app\example-app.vmx
```

VM은 실제 기본 폴더에 생성돼 있었고, state의 새 리소스는 tainted가 되어 다음 plan이 교체를 요구했습니다.

## 안전하게 복구한 방법

1. API 경로·실제 VMX/VMDK·현재 state를 비교했습니다.
2. HCL의 path를 실제 기본 경로로 맞췄습니다.
3. clone 자체가 정상이고 아직 bootstrap되지 않은 새 리소스만 확인한 뒤 실패 표시를 해제했습니다.
4. 새 plan이 VM 삭제·교체 0건임을 확인한 다음 bootstrap과 부팅을 진행했습니다.
5. 원본 템플릿·기존 VM을 변경하지 않고 새 VM의 SSH·Ansible 연결이 성공했습니다.

## 제안

- provider 2.0.1에서 사용자 지정 `LAB_VM_ROOT_WIN`이 실제로 지원되는 범위를 명시하면 좋겠습니다.
- `reference/pitfalls.md`에 `.description` 외에 `.path` 불일치도 추가하면 도움이 될 것 같습니다.
- 실패 뒤에는 clone이 이미 존재할 수 있으므로, 재시도 전에 API·state·실제 파일·삭제 계획을 비교하라는 안내가 필요해 보입니다.

provider 또는 vmrest의 근본 구현 원인까지는 조사하지 않았습니다. 이 기록은 현재 관측한 동작과 복구 결과입니다.
