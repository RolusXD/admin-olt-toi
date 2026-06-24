import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.onus import get_onu
from app.models.base import Base
from app.models.entities import Olt, Onu, OnuServiceModeTemplate, SpeedProfile, Vlan


@pytest.fixture()
def db_session():
    """SQLite en memoria para probar el detalle de ONU sin tocar OLT real.

    Mantiene el mismo patrón de tests de importación inicial, pero limitado
    a las tablas necesarias para construir el bloque `behavior` de solo
    lectura.
    """

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as session:
        yield session


@pytest.fixture()
def olt(db_session):
    olt = Olt(
        olt_code="OLT-BEHAV-01",
        name="OLT Behavior",
        vendor="ZTE",
        model="C300",
        firmware="V1.2.5P3",
        ip_address="127.0.0.1",
        telnet_port=23,
        username="admin",
        password_encrypted="not-used",
        status="test",
    )
    db_session.add(olt)
    db_session.commit()
    db_session.refresh(olt)
    return olt


def _seed_vlan_and_speed_profile(db_session, olt):
    vlan = Vlan(olt_id=olt.id, olt_code_snapshot=olt.olt_code, vlan_id=200, name="FTTH-INTERNET")
    profile = SpeedProfile(
        olt_id=olt.id,
        olt_code_snapshot=olt.olt_code,
        name="SMARTOLT-1G",
        profile_code="SMARTOLT-1G-PROFILE",
        upstream_profile_name="SMARTOLT-1G-UP",
        downstream_profile_name="SMARTOLT-1G-DOWN",
    )
    db_session.add_all([vlan, profile])
    db_session.commit()
    return vlan, profile


def _create_onu(
    db_session,
    olt,
    *,
    service_mode_code: str | None,
    customer_name: str = "Cliente_Test",
):
    vlan, _profile = _seed_vlan_and_speed_profile(db_session, olt)
    onu = Onu(
        olt_id=olt.id,
        olt_code_snapshot=olt.olt_code,
        customer_name=customer_name,
        serial_number="SN-TEST-0001",
        onu_interface="gpon-onu_1/1/1:1",
        onu_type="BTPON",
        vlan=vlan.vlan_id,
        speed_profile="SMARTOLT-1G-DOWN",
        speed_profile_up="SMARTOLT-1G-UP",
        speed_profile_down="SMARTOLT-1G-DOWN",
        service_mode_code=service_mode_code,
        data_quality_status="complete",
        data_quality_missing_fields=json.dumps([], ensure_ascii=True),
        import_source="manual",
    )
    db_session.add(onu)
    db_session.commit()
    db_session.refresh(onu)
    return onu


def _create_template(
    db_session,
    olt,
    *,
    mode_code: str,
    name: str,
    dhcp_source: str,
    use_iphost: bool,
):
    template = OnuServiceModeTemplate(
        olt_id=olt.id,
        mode_code=mode_code,
        name=name,
        description="template for tests",
        vlan_mode="tag",
        dhcp_source=dhcp_source,
        use_iphost=use_iphost,
        use_veip=True,
        use_vlan_filter=True,
        use_loop_detect=True,
        disable_wifi=False,
        default_for_provisioning=False,
        template_body="pon-onu-mng ...",
        source="manual",
        is_active=True,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


def test_onu_behavior_router_iphost_with_template(db_session, olt):
    _create_template(
        db_session,
        olt,
        mode_code="router_iphost",
        name="Router IPHost",
        dhcp_source="from-internet",
        use_iphost=True,
    )
    onu = _create_onu(db_session, olt, service_mode_code="router_iphost")

    result = get_onu(onu.id, db=db_session)
    behavior = result.behavior

    assert behavior is not None
    assert behavior.service_mode_code == "router_iphost"
    assert behavior.mode_simple == "router"
    assert behavior.mode_label == "Router"
    assert behavior.template_name == "Router IPHost"
    assert behavior.mode_code == "router_iphost"
    assert behavior.vlan_id == 200
    assert behavior.vlan_name == "FTTH-INTERNET"
    assert behavior.dhcp_source == "from-internet"
    assert behavior.use_iphost is True
    assert behavior.use_veip is True
    assert behavior.use_vlan_filter is True
    assert behavior.use_loop_detect is True
    assert behavior.disable_wifi is False
    assert behavior.data_quality_status == "complete"
    assert behavior.data_quality_missing_fields == []
    assert behavior.warnings == []


def test_onu_behavior_bridge_tag_internet_with_template(db_session, olt):
    _create_template(
        db_session,
        olt,
        mode_code="bridge_tag_internet",
        name="Bridge Internet",
        dhcp_source="none",
        use_iphost=False,
    )
    onu = _create_onu(db_session, olt, service_mode_code="bridge_tag_internet")

    result = get_onu(onu.id, db=db_session)
    behavior = result.behavior

    assert behavior is not None
    assert behavior.service_mode_code == "bridge_tag_internet"
    assert behavior.mode_simple == "bridge"
    assert behavior.mode_label == "Bridge"
    assert behavior.template_name == "Bridge Internet"
    assert behavior.use_iphost is False
    assert behavior.dhcp_source == "none"
    assert behavior.warnings == []


def test_onu_behavior_transparent_special_with_template(db_session, olt):
    _create_template(
        db_session,
        olt,
        mode_code="transparent_special",
        name="Transparent Special",
        dhcp_source="none",
        use_iphost=False,
    )
    onu = _create_onu(db_session, olt, service_mode_code="transparent_special")

    result = get_onu(onu.id, db=db_session)
    behavior = result.behavior

    assert behavior is not None
    assert behavior.service_mode_code == "transparent_special"
    assert behavior.mode_simple == "transparent"
    assert behavior.mode_label == "Transparente"
    assert behavior.template_name == "Transparent Special"
    assert behavior.use_iphost is False
    assert behavior.warnings == []


def test_onu_behavior_without_service_mode_code(db_session, olt):
    onu = _create_onu(db_session, olt, service_mode_code=None)

    result = get_onu(onu.id, db=db_session)
    behavior = result.behavior

    assert behavior is not None
    assert behavior.service_mode_code is None
    assert behavior.mode_simple == "unknown"
    assert behavior.mode_label == "Desconocido/importado"
    assert behavior.template_name is None
    assert behavior.mode_code is None
    assert behavior.data_quality_status == "complete"
    assert behavior.data_quality_missing_fields == []
    assert behavior.warnings == []


def test_onu_behavior_with_service_mode_code_but_without_template(db_session, olt):
    # No se crea plantilla para este modo a propósito
    onu = _create_onu(db_session, olt, service_mode_code="router_iphost")

    result = get_onu(onu.id, db=db_session)
    behavior = result.behavior

    assert behavior is not None
    # El código informado se conserva, pero el modo simple se degrada a unknown
    assert behavior.service_mode_code == "router_iphost"
    assert behavior.mode_simple == "unknown"
    assert behavior.mode_label == "Desconocido/importado"
    assert behavior.template_name is None
    # Debe incluir un aviso suave para UI
    assert behavior.warnings
    assert any("Plantilla de modo de servicio no definida" in w for w in behavior.warnings)
