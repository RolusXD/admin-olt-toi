import datetime as dt
import json

from app.models.entities import Onu
from app.services.onu_data_quality_service import (
    DATA_QUALITY_BLOCKED,
    DATA_QUALITY_COMPLETE,
    DATA_QUALITY_LEGACY_INCOMPLETE,
    DATA_QUALITY_NEEDS_REVIEW,
    OnuDataQualityService,
)


def _make_onu(**overrides) -> Onu:
    """Helper para instanciar una Onu en memoria para pruebas de calidad.

    No se persiste en base de datos; sólo se inicializan los campos
    relevantes para el evaluador de calidad documental.
    """

    base = dict(
        olt_id=1,
        olt_code_snapshot="OLT-TEST-01",
        customer_name="Cliente Test",
        serial_number="TESTSN0001",
        onu_interface="gpon-onu_1/1/1:1",
        onu_type="BTPON",
        vlan=200,
        speed_profile="imported",
    )
    base.update(overrides)
    return Onu(**base)


def test_respects_blocked_status():
    onu = _make_onu(data_quality_status=DATA_QUALITY_BLOCKED)

    service = OnuDataQualityService(db=None)
    result = service.evaluate(onu)

    assert result.status == DATA_QUALITY_BLOCKED
    assert result.missing_fields == []
    assert onu.data_quality_status == DATA_QUALITY_BLOCKED
    assert onu.data_quality_missing_fields == "[]"


def test_complete_when_all_critical_and_recommended_present():
    onu = _make_onu(
        zone_id=10,
        zone_name="Lagunas",
        address_reference="Calle 1 #123",
        nap_id=20,
        nap_name="NAP-01",
        nap_port=5,
        external_id="EXT123",
        auth_date=dt.datetime(2026, 6, 20, tzinfo=dt.timezone.utc),
    )

    service = OnuDataQualityService(db=None)
    result = service.evaluate(onu)

    assert result.status == DATA_QUALITY_COMPLETE
    assert result.missing_fields == []
    assert onu.data_quality_status == DATA_QUALITY_COMPLETE
    assert json.loads(onu.data_quality_missing_fields or "[]") == []


def test_needs_review_when_only_recommended_fields_missing():
    onu = _make_onu(
        zone_id=10,
        zone_name="Lagunas",
        address_reference="Calle 1 #123",
        nap_id=20,
        nap_name="NAP-01",
        nap_port=5,
        external_id="",
        auth_date=None,
    )

    service = OnuDataQualityService(db=None)
    result = service.evaluate(onu)

    assert result.status == DATA_QUALITY_NEEDS_REVIEW
    # No faltan críticos, sólo recomendados.
    assert "external_id" in result.missing_fields
    assert "auth_date" in result.missing_fields
    assert "customer_name" not in result.missing_fields
    assert onu.data_quality_status == DATA_QUALITY_NEEDS_REVIEW
    assert json.loads(onu.data_quality_missing_fields or "[]") == result.missing_fields


def test_legacy_incomplete_when_critical_fields_missing():
    onu = _make_onu(
        customer_name=" ",  # sin nombre de cliente
        zone_id=None,
        zone_name="SIN_ZONA",
        address_reference=None,
        nap_id=None,
        nap_name=None,
        nap_port=None,
        onu_type="",  # tipo vacío
        vlan=0,
        external_id=None,
        auth_date=None,
    )

    service = OnuDataQualityService(db=None)
    result = service.evaluate(onu)

    assert result.status == DATA_QUALITY_LEGACY_INCOMPLETE
    # Debe reportar faltantes críticos.
    for field in [
        "customer_name",
        "zone",
        "address",
        "nap",
        "nap_port",
        "onu_type",
        "vlan",
    ]:
        assert field in result.missing_fields

    # Y también los recomendados.
    assert "external_id" in result.missing_fields
    assert "auth_date" in result.missing_fields
    assert onu.data_quality_status == DATA_QUALITY_LEGACY_INCOMPLETE
    assert json.loads(onu.data_quality_missing_fields or "[]") == result.missing_fields


