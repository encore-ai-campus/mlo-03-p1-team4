"""F-70: 기준 HAProxy 설정에 배포별 주소만 주입한다. 설치·재시작은 하지 않는다."""

import argparse
import ipaddress
import re
from pathlib import Path


def backend_endpoint(value: str) -> str:
    """포트·설정 지시문을 주입할 수 없는 IP 또는 호스트 이름만 받는다."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        labels = value.removesuffix(".").split(".")
        if (
            not value
            or len(value) > 253
            or all(label.isdigit() for label in labels)
            or not all(
                re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                for label in labels
            )
        ):
            raise ValueError("backend 주소는 IP 또는 호스트 이름이어야 합니다") from None
        return f"{value}:80"
    if address.version == 6:
        return f"[{address}]:80"
    return f"{address}:80"


def render_config(template: str, *, api1: str, api2: str, monitor_sources: list[str]) -> str:
    first, second = backend_endpoint(api1), backend_endpoint(api2)
    if first.lower() == second.lower():
        raise ValueError("api1과 api2는 서로 다른 주소여야 합니다")
    if not monitor_sources:
        raise ValueError("monitor-source를 한 개 이상 지정하세요")
    sources = list(
        dict.fromkeys(str(ipaddress.ip_network(x, strict=False)) for x in monitor_sources)
    )
    replacements = {
        "server api1 api1:80": f"server api1 {first}",
        "server api2 api2:80": f"server api2 {second}",
        "acl allowed_monitor src 127.0.0.1": f"acl allowed_monitor src {' '.join(sources)}",
    }
    for original, replacement in replacements.items():
        if template.count(original) != 1:
            raise ValueError("기준 설정의 서버·ACL 위치가 변경됐습니다. 템플릿을 확인하세요")
        template = template.replace(original, replacement, 1)
    return template


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api1", required=True)
    parser.add_argument("--api2", required=True)
    parser.add_argument("--monitor-source", action="append", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    template_path = Path(__file__).with_name("haproxy.cfg")
    try:
        if args.output.resolve() == template_path.resolve():
            raise ValueError("출력 경로는 기준 haproxy.cfg와 달라야 합니다")
        rendered = render_config(
            template_path.read_text(encoding="utf-8"),
            api1=args.api1,
            api2=args.api2,
            monitor_sources=args.monitor_source,
        )
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
