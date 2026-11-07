"""Terraform이 새로 생성해 전원이 꺼진 VM만 브리지·cloud-init으로 준비한다."""

import ipaddress
import os
import re
import struct
import subprocess
from pathlib import Path

VMRUN = "/mnt/c/Program Files/VMware/VMware Workstation/vmrun.exe"
VM_ROOT = Path("/mnt/c/Users/Playdata/Documents/Virtual Machines")
PRIVATE = Path.home() / ".config/spacecube109"


def run(args):
    result = subprocess.run(args, capture_output=True, text=True, check=False)  # noqa: S603 고정 실행 파일과 검증한 시험 VM 인자만 사용
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout.strip()


role = os.environ["VM_ROLE"]
if role not in {"gw", "api1", "api2", "mon"}:
    raise RuntimeError("대상 역할이 허용 목록 밖입니다.")
address = str(ipaddress.IPv4Address(os.environ["VM_IP"]))
vmx = Path(run(["/usr/bin/wslpath", "-u", os.environ["VMX_WIN"]])).resolve()
if vmx != (VM_ROOT / f"spacecube-{role}" / f"spacecube-{role}.vmx").resolve():
    raise RuntimeError("예상한 새 시험 VM 경로가 아닙니다.")
if os.environ["VMX_WIN"] in run([VMRUN, "list"]).splitlines():
    raise RuntimeError("실행 중인 VM의 하드웨어는 수정하지 않습니다.")
disk_match = re.search(r'^scsi0:0\.fileName\s*=\s*"([^"]+)"', vmx.read_text(), re.MULTILINE)
if not disk_match:
    raise RuntimeError("새 VM의 디스크 경로가 없습니다.")
disk = (vmx.parent / disk_match[1]).resolve()
if disk.parent != vmx.parent:
    raise RuntimeError("원본 템플릿 또는 다른 폴더의 디스크는 변경하지 않습니다.")
with disk.open("rb") as stream:
    header = stream.read(512)
if header[:4] != b"KDMV":
    raise RuntimeError("예상한 단일 sparse VMDK 형식이 아닙니다.")
if struct.unpack_from("<Q", header, 12)[0] * 512 < 20 * 1024**3:
    run(
        [
            "/mnt/c/Program Files/VMware/VMware Workstation/vmware-vdiskmanager.exe",
            "-x",
            "20GB",
            run(["/usr/bin/wslpath", "-w", str(disk)]),
        ]
    )
private_key = PRIVATE / "id_ed25519"
public_key = private_key.with_suffix(".pub").read_text().strip()
seed = PRIVATE / f"seed-{role}"
seed.mkdir(mode=0o700, parents=True, exist_ok=True)
(seed / "user-data").write_text(
    "#cloud-config\nusers:\n  - default\nssh_pwauth: false\ndisable_root: true\n"
    f"ssh_authorized_keys:\n  - {public_key}\n"
    "timezone: Asia/Seoul\ngrowpart:\n  mode: auto\n  devices: ['/']\nresize_rootfs: true\n"
)
(seed / "meta-data").write_text(
    f"instance-id: spacecube109-{os.environ['VM_ID']}\nlocal-hostname: spacecube-{role}\n"
)
(seed / "network-config").write_text(
    f"version: 2\nethernets:\n  lan:\n    match:\n      name: 'en*'\n    dhcp4: false\n    addresses: [{address}/24]\n"
    "    routes:\n      - to: default\n        via: 192.168.0.1\n    nameservers:\n      addresses: [192.168.0.1, 1.1.1.1]\n"
)
iso = vmx.parent / "spacecube-seed.iso"
run(
    [
        "/usr/bin/cloud-localds",
        f"--network-config={seed / 'network-config'}",
        str(iso),
        str(seed / "user-data"),
        str(seed / "meta-data"),
    ]
)
settings = {
    "ide1:0.fileName": run(["/usr/bin/wslpath", "-w", str(iso)]),
    "ide1:0.present": "TRUE",
    "ide1:0.startConnected": "TRUE",
    "ide1:0.deviceType": "cdrom-image",
    "ethernet0.connectionType": "bridged",
    "ethernet0.startConnected": "TRUE",
    "ethernet1.present": "FALSE",
    "mks.enable3d": "FALSE",
}
content = vmx.read_text()
content = re.sub(r"(?im)^ethernet0\.vnet\s*=.*\n?", "", content)
for key, value in settings.items():
    pattern = rf"(?im)^\s*{re.escape(key)}\s*=.*$"
    line = f'{key} = "{value}"'
    content = (
        re.sub(pattern, lambda _, line=line: line, content)
        if re.search(pattern, content)
        else content + "\n" + line
    )
vmx.write_text(content + "\n")
print(f"브리지·cloud-init 준비: {role} {address}")
