from pathlib import Path

import pytest

from app.drivers.zte.c300_v125p3_telnet.zte_onu_management_mode_parser import parse_onu_management_modes


@pytest.fixture(scope="module")
def modes():
    fixture = Path(__file__).parent / "fixtures" / "zte_c300_running_config.txt"
    return parse_onu_management_modes(fixture.read_text(encoding="utf-8"))


def test_detects_bridge_tag_internet(modes):
    mode = next(item for item in modes if item.mode_code == "bridge_tag_internet")

    assert mode.vlan_mode == "tag"
    assert mode.dhcp_source == "from-internet"
    assert mode.vlan_id == 200


def test_detects_router_iphost(modes):
    mode = next(item for item in modes if item.mode_code == "router_iphost")

    assert mode.has_iphost is True
    assert mode.has_vlan_filter is True
    assert mode.dhcp_source == "from-onu"


def test_detects_transparent_special(modes):
    mode = next(item for item in modes if item.mode_code == "transparent_special")

    assert mode.vlan_mode == "transparent"
    assert mode.has_iphost is True
    assert mode.has_veip is True


def test_gpon00cbac10_fixture_mode_is_transparent_vlan_600(modes):
    mode = next(item for item in modes if item.onu_interface == "gpon-onu_1/2/15:1")

    assert mode.mode_code == "transparent_special"
    assert mode.vlan_id == 600
    assert mode.ethernet_ports_configured == ["eth_0/1", "eth_0/2"]
    assert mode.wifi_disabled is True
    assert mode.security_profiles == ["998", "999"]
