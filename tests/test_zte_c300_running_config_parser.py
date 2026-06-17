from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.drivers.zte.c300_v125p3_telnet.running_config_parser import parse_running_config


@pytest.fixture(scope="module")
def parsed_config():
    fixture = Path(__file__).parent / "fixtures" / "zte_c300_running_config.txt"
    return parse_running_config(fixture.read_text(encoding="utf-8"))


def test_parses_expected_totals(parsed_config):
    assert len(parsed_config.onus) == 557
    assert len(parsed_config.pon_ports) == 16
    assert len(parsed_config.vlans) == 215
    assert sum(1 for profile in parsed_config.gpon_profiles if profile.profile_type == "tcont") == 14
    assert sum(1 for profile in parsed_config.gpon_profiles if profile.profile_type == "traffic") == 14
    assert len(parsed_config.onu_types) == 13


def test_extracts_known_onu(parsed_config):
    onu = next(item for item in parsed_config.onus if item.serial_number == "BTPTDD2459E4")

    assert onu.onu_interface == "gpon-onu_1/2/3:1"
    assert onu.pon_interface_name == "gpon-olt_1/2/3"
    assert onu.customer_name == "Jhonny_Apaza"
    assert onu.onu_type == "BTPON"
    assert onu.vlan == 200
    assert onu.speed_profile_up == "SMARTOLT-1G-UP"
    assert onu.speed_profile_down == "SMARTOLT-1G-DOWN"
    assert onu.raw_description == (
        "$$$$zone_Lagunas_descr_Nap_C1_Puerto_2_Av_Venezuela_"
        "odb_ODN_C01_extid_BTPTDD2459E4_authd_20210521"
    )
    assert onu.parsed_zone_name == "Lagunas"
    assert onu.parsed_nap_name == "C1"
    assert onu.parsed_nap_port == 2
    assert onu.parsed_odn == "ODN_C01"
    assert onu.auth_date == datetime(2021, 5, 21, tzinfo=UTC)


def test_extracts_known_nap(parsed_config):
    lagunas_c1 = [
        onu
        for onu in parsed_config.onus
        if onu.parsed_zone_name == "Lagunas" and onu.parsed_nap_name == "C1"
    ]

    assert lagunas_c1
    assert any(onu.parsed_nap_port == 2 for onu in lagunas_c1)
    assert any(onu.parsed_odn == "ODN_C01" for onu in lagunas_c1)


def test_extracts_known_vlan(parsed_config):
    vlan = next(item for item in parsed_config.vlans if item.vlan_id == 200)

    assert vlan.description == "FTTH-TH1"


def test_extracts_gpon_profiles_and_onu_types(parsed_config):
    tcont = next(
        profile
        for profile in parsed_config.gpon_profiles
        if profile.profile_type == "tcont" and profile.name == "SMARTOLT-1G-UP"
    )
    traffic = next(
        profile
        for profile in parsed_config.gpon_profiles
        if profile.profile_type == "traffic" and profile.name == "SMARTOLT-1G-DOWN"
    )
    onu_type = next(item for item in parsed_config.onu_types if item.name == "BTPON")

    assert tcont.upstream_rate == 1048064
    assert tcont.type_value == 5
    assert tcont.fixed_kbps == 64
    assert tcont.assured_kbps == 64
    assert tcont.maximum_kbps == 1048064
    assert traffic.downstream_rate == 1048064
    assert traffic.sir_kbps == 1048064
    assert traffic.pir_kbps == 1048064
    assert onu_type.max_tcont == 8
    assert onu_type.max_gemport == 32
    assert onu_type.max_ports == 8
    assert onu_type.max_switch_perslot == 8
    assert onu_type.max_flow_perswitch == 8
    assert onu_type.max_iphost == 5
    assert onu_type.ethernet_ports == 1


def test_extracts_onu_type_interfaces_and_directional_profile_catalogs(parsed_config):
    zte_f660 = next(item for item in parsed_config.onu_types if item.name == "ZTE-F660")
    azul = next(item for item in parsed_config.onu_types if item.name == "azul")
    upload = next(
        profile
        for profile in parsed_config.profile_catalogs
        if profile.direction == "upload" and profile.profile_kind == "tcont" and profile.name == "SMARTOLT-1G-UP"
    )
    download = next(
        profile
        for profile in parsed_config.profile_catalogs
        if profile.direction == "download" and profile.profile_kind == "traffic" and profile.name == "SMARTOLT-1G-DOWN"
    )

    assert len(parsed_config.profile_catalogs) == 28
    assert zte_f660.ethernet_ports == 4
    assert zte_f660.pots_ports == 2
    assert zte_f660.wifi_ports == 4
    assert azul.ethernet_ports == 2
    assert azul.rf_ports == 1
    assert azul.wifi_ports == 1
    assert upload.type_value == 5
    assert upload.maximum_kbps == 1048064
    assert download.pir_kbps == 1048064
