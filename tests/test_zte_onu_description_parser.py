from datetime import UTC, datetime

from app.drivers.zte.c300_v125p3_telnet.zte_onu_description_builder import build_onu_description
from app.drivers.zte.c300_v125p3_telnet.zte_onu_description_parser import parse_onu_description


def test_parser_extracts_productive_description_fields():
    parsed = parse_onu_description(
        "$$$$zone_Lagunas_descr_Nap_C1_Puerto_2_Av_Venezuela_odb_ODN_C01_extid_BTPTDD2459E4_authd_20210521"
    )

    assert parsed.description_original.startswith("$$$$zone_Lagunas")
    assert parsed.zone_name == "Lagunas"
    assert parsed.address_reference == "Av_Venezuela"
    assert parsed.nap_name == "C1"
    assert parsed.nap_port_label == "2"
    assert parsed.odb_name == "ODN_C01"
    assert parsed.external_id == "BTPTDD2459E4"
    assert parsed.auth_date == datetime(2021, 5, 21, tzinfo=UTC)
    assert parsed.parse_status == "parsed"


def test_parser_handles_long_variant_with_odb_and_authd():
    parsed = parse_onu_description(
        "$$$$zone_Lagunas_descr_Nap_H1_Puerto_12_19_de_junio_avenida_provincia_moxos_Nro_5485_"
        "odb_ODN_H1_----_19_DE_JUNIO_authd_20220114"
    )

    assert parsed.zone_name == "Lagunas"
    assert parsed.nap_name == "H1"
    assert parsed.nap_port_label == "12"
    assert parsed.address_reference == "19_de_junio_avenida_provincia_moxos_Nro_5485"
    assert parsed.odb_name == "ODN_H1_----_19_DE_JUNIO"
    assert parsed.auth_date == datetime(2022, 1, 14, tzinfo=UTC)


def test_parser_preserves_unstructured_description_as_partial():
    parsed = parse_onu_description("description San_Roque_Urb_Nuevo_Amanecer_Calle_17_de_octubre_N5073")

    assert parsed.description_original == "description San_Roque_Urb_Nuevo_Amanecer_Calle_17_de_octubre_N5073"
    assert parsed.address_reference == "San_Roque_Urb_Nuevo_Amanecer_Calle_17_de_octubre_N5073"
    assert parsed.parse_status == "partial"
    assert "missing zone" in parsed.warnings


def test_parser_accepts_zone_token_case_variants():
    assert parse_onu_description("$$$$ZONE_San_Roque_descr_cliente").zone_name == "San_Roque"
    assert parse_onu_description("zone_Zone_1_descr_cliente").zone_name == "Zone_1"


def test_valid_nap_description_never_falls_back_to_sin_zona():
    original = "$$$$zone_Lagunas_descr_NAP_H5_PUERTO_9_San_Roque"
    parsed = parse_onu_description(original)

    assert parsed.description_original == original
    assert parsed.zone_name == "Lagunas"
    assert parsed.nap_name == "H5"
    assert parsed.nap_port_label == "9"
    assert "missing zone" not in parsed.warnings


def test_builder_generates_productive_compatible_description():
    description = build_onu_description(
        zone="San Roque",
        address_reference="Urb Nuevo Amanecer Calle 17 de octubre N5073",
        nap_name="H1",
        nap_port_label=11,
        serial="GPON00709BF8",
        auth_date="20260618",
    )

    assert (
        description
        == "$$$$zone_San_Roque_descr_Urb_Nuevo_Amanecer_Calle_17_de_octubre_N5073_Nap_H1_Puerto_11_extid_GPON00709BF8_authd_20260618"
    )
