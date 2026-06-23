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


def test_bridge_hybrid_nodo_matilde_parses_structured_fields():
    raw = """pon-onu-mng gpon-onu_1/2/10:111
flow mode 1 tag-filter vid-filter untag-filter discard
flow 1 priority 0 vid 21
flow 1 priority 0 vid 200
flow 1 priority 0 vid 700
gemport 1 flow 1
switchport-bind switch_0/1 veip 1
vlan port eth_0/1 mode hybrid def-vlan 700
vlan port eth_0/1 vlan 21,200
dhcp-ip ethuni eth_0/1 from-internet
security-mng 998 state enable mode permit ingress-type lan protocol web https
security-mng 999 state enable ingress-type lan protocol ftp telnet ssh snmp tr069
!
"""

    modes = parse_onu_management_modes(raw)
    assert len(modes) == 1
    mode = modes[0]

    assert mode.onu_interface == "gpon-onu_1/2/10:111"
    assert mode.mode_code == "bridge_tag_internet"
    assert mode.mode_simple == "bridge"
    assert mode.port_mode == "hybrid"
    assert mode.native_vlan == 700
    assert mode.allowed_vlans == [21, 200]
    assert mode.service_vlans == [21, 200, 700]
    assert mode.dhcp_source == "from-internet"
    assert mode.has_veip is True
    assert mode.has_iphost is False


def test_bridge_trunk_centro_salud_parses_structured_fields():
    raw = """pon-onu-mng gpon-onu_1/2/13:4
flow mode 1 tag-filter vid-filter untag-filter discard
flow 1 priority 0 vid 200
flow 1 priority 0 vid 700
flow 1 priority 0 vid 735
flow 1 priority 0 vid 835
gemport 1 flow 1
switchport-bind switch_0/1 veip 1
vlan port eth_0/1 mode trunk
vlan port eth_0/1 vlan 700,735,835
dhcp-ip ethuni eth_0/1 from-internet
security-mng 998 state enable mode permit ingress-type lan protocol web https
security-mng 999 state enable ingress-type lan protocol ftp telnet ssh snmp tr069
!
"""

    modes = parse_onu_management_modes(raw)
    assert len(modes) == 1
    mode = modes[0]

    assert mode.onu_interface == "gpon-onu_1/2/13:4"
    assert mode.mode_code == "bridge_tag_internet"
    assert mode.mode_simple == "bridge"
    assert mode.port_mode == "trunk"
    assert mode.allowed_vlans == [700, 735, 835]
    # VLAN 200 viene de los flows aunque no esté en allowed_vlans
    assert mode.service_vlans == [200, 700, 735, 835]
    assert mode.dhcp_source == "from-internet"
    assert mode.has_veip is True
    assert mode.has_iphost is False


def test_router_iphost_with_vlan_602_parses_wan_vlan_and_flows():
    raw = """pon-onu-mng gpon-onu_1/2/5:29
flow mode 1 tag-filter vid-filter untag-filter discard
flow 1 priority 0 vid 602
flow 1 priority 0 vid 605
gemport 1 flow 1
switchport-bind switch_0/1 iphost 1
switchport-bind switch_0/1 veip 1
vlan-filter-mode iphost 1 tag-filter vid-filter untag-filter discard
vlan-filter iphost 1 priority 0 vid 602
dhcp-ip ethuni eth_0/1 from-onu
dhcp-ip ethuni eth_0/2 from-onu
security-mng 998 state enable mode permit ingress-type lan protocol web https
security-mng 999 state enable ingress-type lan protocol ftp telnet ssh snmp tr069
!
"""

    modes = parse_onu_management_modes(raw)
    assert len(modes) == 1
    mode = modes[0]

    assert mode.onu_interface == "gpon-onu_1/2/5:29"
    assert mode.mode_code == "router_iphost"
    assert mode.mode_simple == "router"
    assert mode.has_iphost is True
    assert mode.has_veip is True
    assert mode.has_vlan_filter is True
    assert mode.dhcp_source == "from-onu"
    # VLAN principal WAN tomada de vlan-filter iphost
    assert mode.wan_vlan_id == 602
    # service_vlans incluye todas las VLAN de flows
    assert mode.service_vlans == [602, 605]


def test_bridge_trunk_with_loop_detect_sets_bridge_mode_and_loop_flag():
    raw = """pon-onu-mng gpon-onu_1/2/20:7
flow mode 1 tag-filter vid-filter untag-filter discard
flow 1 priority 0 vid 200
gemport 1 flow 1
switchport-bind switch_0/1 veip 1
vlan port eth_0/1 mode trunk
vlan port eth_0/1 vlan 200
loop-detect ethuni eth_0/1 enable
dhcp-ip ethuni eth_0/1 from-internet
security-mng 998 state enable mode permit ingress-type lan protocol web https
security-mng 999 state enable ingress-type lan protocol ftp telnet ssh snmp tr069
!
"""

    modes = parse_onu_management_modes(raw)
    assert len(modes) == 1
    mode = modes[0]

    assert mode.mode_code == "bridge_tag_internet"
    assert mode.mode_simple == "bridge"
    assert mode.port_mode == "trunk"
    assert mode.loop_detect_enabled is True
    assert mode.dhcp_source == "from-internet"
