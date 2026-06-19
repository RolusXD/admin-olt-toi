from app.drivers.zte.c300_v125p3_telnet.zte_c300_interface_parser import parse_show_interface


SHOW_INTERFACE_SAMPLE = """
xgei_1/19/1 is up,  line protocol is up
  Description is -TOI
  Keepalive set:10 sec
  The port negotiation is disable
  The port is optical
  Duplex full
  VLAN mode is trunk, pvid 1          BW 10000000 Kbits
  MTU 1500 bytes

xgei_1/19/2 is down,  line protocol is down
  Description is
  The port is optical
  VLAN mode is hybrid, pvid 20          BW 10000000 Kbits
  MTU 1500 bytes

gei_1/20/1 is up,  line protocol is up
  Description is BACKUP
  The port negotiation is enable
  The port is electrical
  VLAN mode is access, pvid 200          BW 1000000 Kbits
  MTU 1500 bytes
"""


def test_parser_detects_xgei_interface():
    interfaces = parse_show_interface(SHOW_INTERFACE_SAMPLE)

    assert [interface.interface_name for interface in interfaces] == ["xgei_1/19/1", "xgei_1/19/2", "gei_1/20/1"]


def test_parser_extracts_description_mode_pvid_speed_and_mtu():
    uplink = parse_show_interface(SHOW_INTERFACE_SAMPLE)[0]

    assert uplink.description == "-TOI"
    assert uplink.mode == "trunk"
    assert uplink.pvid_untag == 1
    assert uplink.speed_kbps == 10000000
    assert uplink.mtu == 1500
    assert uplink.oper_status == "up"
    assert uplink.line_protocol == "up"
    assert uplink.interface_type == "fiber"


def test_parser_extracts_hybrid_and_copper_access_interfaces():
    interfaces = parse_show_interface(SHOW_INTERFACE_SAMPLE)
    hybrid = interfaces[1]
    copper = interfaces[2]

    assert hybrid.mode == "hybrid"
    assert hybrid.pvid_untag == 20
    assert copper.interface_type == "copper"
    assert copper.mode == "access"
    assert copper.speed_kbps == 1000000


def test_parser_splits_headers_after_terminal_backspaces():
    output = """
gei_1/20/2 is down,  line protocol is down
  Description is none.
  The port is electric
  VLAN mode is hybrid, pvid 1
\b \b\b \bgei_1/20/3 is down,  line protocol is down
  Description is none
  The port is optical
  VLAN mode is hybrid, pvid 1          BW 1000000 Kbits
"""

    interfaces = parse_show_interface(output)

    assert [interface.interface_name for interface in interfaces] == ["gei_1/20/2", "gei_1/20/3"]
    assert interfaces[0].description is None
    assert interfaces[0].interface_type == "copper"
    assert interfaces[1].interface_type == "fiber"
