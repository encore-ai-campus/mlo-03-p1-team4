"""F-70: 배포 주소 입력 검증과 기준 설정 보존 회귀."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def renderer():
    path = Path(__file__).parents[1] / "render_config.py"
    spec = importlib.util.spec_from_file_location("haproxy_renderer_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def template():
    return (Path(__file__).parents[1] / "haproxy.cfg").read_text(encoding="utf-8")


def test_only_addresses_change_and_post_retry_stays_disabled(renderer):
    rendered = renderer.render_config(
        template(), api1="192.0.2.10", api2="192.0.2.11", monitor_sources=["192.0.2.12"]
    )
    assert "server api1 192.0.2.10:80 maxconn 50 check inter 2s fall 2 rise 2" in rendered
    assert "server api2 192.0.2.11:80 maxconn 50 check inter 2s fall 2 rise 2" in rendered
    assert "acl allowed_monitor src 192.0.2.12/32" in rendered
    assert "retries 0" in rendered
    assert "timeout queue 5s" in rendered
    assert "http-check expect status 200" in rendered


def test_ipv6_and_multiple_monitor_networks(renderer):
    rendered = renderer.render_config(
        template(),
        api1="2001:db8::10",
        api2="api2.example.test",
        monitor_sources=["2001:db8::12", "192.0.2.0/24", "192.0.2.0/24"],
    )
    assert "server api1 [2001:db8::10]:80" in rendered
    assert "server api2 api2.example.test:80" in rendered
    assert "acl allowed_monitor src 2001:db8::12/128 192.0.2.0/24" in rendered


@pytest.mark.parametrize(
    "address", ["", "api1:80", "api1\nretries 1", "../api", "api 1", "-api1", "a_b", "999.1.1.1"]
)
def test_invalid_backend_address_is_rejected(renderer, address):
    with pytest.raises(ValueError):
        renderer.backend_endpoint(address)


@pytest.mark.parametrize("sources", [[], ["monitor.example.test"], ["192.0.2.1\nallow all"]])
def test_invalid_monitor_source_is_rejected(renderer, sources):
    with pytest.raises(ValueError):
        renderer.render_config(template(), api1="api1", api2="api2", monitor_sources=sources)


def test_duplicate_servers_are_rejected(renderer):
    with pytest.raises(ValueError, match="서로 다른"):
        renderer.render_config(template(), api1="api1", api2="api1", monitor_sources=["127.0.0.1"])


def test_changed_template_is_rejected(renderer):
    with pytest.raises(ValueError, match="기준 설정"):
        renderer.render_config(
            template().replace("server api1 api1:80", "server renamed api1:80"),
            api1="api1",
            api2="api2",
            monitor_sources=["127.0.0.1"],
        )


def test_cli_writes_separate_output(renderer, monkeypatch, tmp_path):
    original = template()
    output = tmp_path / "rendered.cfg"
    monkeypatch.setattr(
        "sys.argv",
        [
            "render_config.py",
            "--api1",
            "api1",
            "--api2",
            "api2",
            "--monitor-source",
            "192.0.2.12",
            "--output",
            str(output),
        ],
    )
    renderer.main()
    assert "acl allowed_monitor src 192.0.2.12/32" in output.read_text(encoding="utf-8")
    assert template() == original


def test_cli_cannot_overwrite_reference_template(renderer, monkeypatch):
    original = template()
    reference = Path(renderer.__file__).with_name("haproxy.cfg")
    monkeypatch.setattr(
        "sys.argv",
        [
            "render_config.py",
            "--api1",
            "api1",
            "--api2",
            "api2",
            "--monitor-source",
            "127.0.0.1",
            "--output",
            str(reference),
        ],
    )
    with pytest.raises(SystemExit) as error:
        renderer.main()
    assert error.value.code == 2
    assert template() == original
