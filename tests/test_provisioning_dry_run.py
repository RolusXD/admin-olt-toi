from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from app.models.base import Base
from app.models.entities import GponProfile, Nap, NapPort, Olt, Onu, OnuType, ProvisioningPlan, ProvisioningTemplate, UnauthorizedOnu, Vlan, Zone
from app.schemas.entities import ProvisioningPlanCreate
from app.services.provisioning_service import ProvisioningService


@pytest.fixture()
def db_session():
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
def catalog(db_session):
    olt = Olt(
        olt_code="OLT-PCM-ZTE-01",
        name="FTTH-PCM-ZTE1",
        environment="production",
        vendor="ZTE",
        model="C300",
        firmware="V1.2.5P3",
        ip_address="127.0.0.1",
        username="admin",
        password_encrypted="secret",
    )
    lab = Olt(
        olt_code="OLT-LAB-ZTE-01",
        name="OLT LAB",
        environment="lab",
        vendor="ZTE",
        model="C300",
        firmware="V1.2.5P3",
        ip_address="127.0.0.2",
        username="admin",
        password_encrypted="secret",
    )
    zone = Zone(name="Lagunas")
    db_session.add_all([olt, lab, zone])
    db_session.flush()
    nap = Nap(zone_id=zone.id, name="C1", capacity=16)
    db_session.add(nap)
    db_session.flush()
    pending = UnauthorizedOnu(
        olt_id=olt.id,
        olt_code_snapshot=olt.olt_code,
        pon_type="gpon",
        slot=2,
        port=15,
        pon_port_interface="gpon-olt_1/2/15",
        serial_number="GPON00CBAC10",
        detected_vendor="VSOL",
        raw_output="gpon-onu_1/2/15:1        GPON00CBAC10        unknown",
        status="pending",
    )
    db_session.add_all(
        [
            *[NapPort(nap_id=nap.id, port_number=port, label=f"Puerto {port}", status="free") for port in range(1, 17)],
            pending,
            Vlan(olt_id=olt.id, vlan_id=200, name="FTTH-TH1", description="FTTH-TH1"),
            GponProfile(olt_id=olt.id, profile_type="tcont", name="SMARTOLT-1G-UP", upstream_rate=None, downstream_rate=None),
            GponProfile(olt_id=olt.id, profile_type="traffic", name="SMARTOLT-1G-DOWN", upstream_rate=None, downstream_rate=None),
            OnuType(olt_id=olt.id, name="VSOL", vendor_detected="VSOL", max_tcont=None, max_gemport=None, max_ports=None),
            ProvisioningTemplate(
                name="ZTE C300 V1.2.5P3 default dry-run",
                vendor="ZTE",
                model="C300",
                firmware="V1.2.5P3",
                template_name="ZTE C300 V1.2.5P3 default dry-run",
                template_body=(
                    "interface {pon_port_interface}\n"
                    "onu {onu_index} type {onu_type} sn {serial_number}\n"
                    "exit\n"
                    "interface {onu_interface}\n"
                    "name {customer_name_cli}\n"
                    "switchport vlan {vlan} tag vport 1\n"
                    "exit"
                ),
                commands="",
                is_default=True,
            ),
            Onu(
                olt_id=lab.id,
                olt_code_snapshot=lab.olt_code,
                customer_name="TR_Camacho_FO",
                serial_number="GPON00CBAC10",
                onu_interface="gpon-onu_1/2/15:1",
                onu_type="VSOL",
                vlan=200,
                speed_profile="SMARTOLT-1G",
                speed_profile_up="SMARTOLT-1G-UP",
                speed_profile_down="SMARTOLT-1G-DOWN",
                status="offline",
                import_source="cli_import",
            ),
        ]
    )
    db_session.commit()
    return {"olt": olt, "lab": lab, "zone": zone, "nap": nap, "pending": pending}


def payload(
    pending_id: int,
    zone_id: int,
    nap_id: int,
    nap_port: int = 14,
    selected_onu_id: int | None = None,
    vlan: int = 200,
    speed_profile_up: str = "SMARTOLT-1G-UP",
    speed_profile_down: str = "SMARTOLT-1G-DOWN",
) -> ProvisioningPlanCreate:
    return ProvisioningPlanCreate(
        unauthorized_onu_id=pending_id,
        customer_name="Cliente Prueba",
        customer_reference="TEST-001",
        technical_comment="Dry run controlado",
        address="Direccion de prueba",
        notes="No ejecutar",
        zone_id=zone_id,
        nap_id=nap_id,
        nap_port=nap_port,
        onu_type="VSOL",
        vlan=vlan,
        speed_profile_up=speed_profile_up,
        speed_profile_down=speed_profile_down,
        selected_onu_id=selected_onu_id,
    )


def test_create_validate_generate_and_approve_plan(db_session, catalog):
    service = ProvisioningService(db_session)

    plan = service.create_plan(payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id))
    plan, result = service.validate_and_update(plan.id)
    validated_status = plan.status
    approved = service.approve(plan.id)

    assert result.errors == []
    assert "existe en laboratorio" in result.warnings[0]
    assert validated_status == "validated"
    assert approved.status == "approved"
    assert approved.suggested_onu_id == 1
    assert approved.validation_result.is_valid is True
    assert "interface gpon-olt_1/2/15" in approved.generated_cli
    assert "onu 1 type VSOL sn GPON00CBAC10" in approved.generated_cli
    assert "switchport vlan 200 tag vport 1" in approved.generated_cli
    assert db_session.scalar(select(ProvisioningPlan)).serial_number == "GPON00CBAC10"


def test_cancel_plan(db_session, catalog):
    service = ProvisioningService(db_session)
    plan = service.create_plan(payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id))

    cancelled = service.cancel(plan.id)

    assert cancelled.status == "cancelled"


def test_occupied_nap_port_generates_error(db_session, catalog):
    db_session.add(
        Onu(
            olt_id=catalog["olt"].id,
            customer_name="Cliente Existente",
            serial_number="ZTEGC0F5D7A9",
            onu_interface="gpon-onu_1/2/15:2",
            onu_type="ZTE-F660",
            vlan=200,
            speed_profile="SMARTOLT-1G",
            speed_profile_up="SMARTOLT-1G-UP",
            speed_profile_down="SMARTOLT-1G-DOWN",
            zone_id=catalog["zone"].id,
            nap_id=catalog["nap"].id,
            nap_port=14,
            status="online",
            import_source="cli_import",
        )
    )
    db_session.commit()

    plan = ProvisioningService(db_session).create_plan(payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id))
    _, result = ProvisioningService(db_session).validate_and_update(plan.id)

    assert any("ya esta ocupado" in error for error in result.errors)
    assert plan.status == "validation_failed"


def test_registered_onu_in_same_olt_generates_error(db_session, catalog):
    db_session.add(
        Onu(
            olt_id=catalog["olt"].id,
            customer_name="ONU Ya Registrada",
            serial_number="GPON00CBAC10",
            onu_interface="gpon-onu_1/2/15:1",
            onu_type="VSOL",
            vlan=200,
            speed_profile="SMARTOLT-1G",
            speed_profile_up="SMARTOLT-1G-UP",
            speed_profile_down="SMARTOLT-1G-DOWN",
            status="online",
            import_source="cli_import",
        )
    )
    db_session.commit()

    plan = ProvisioningService(db_session).create_plan(payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id))
    _, result = ProvisioningService(db_session).validate_and_update(plan.id)

    assert any("ya esta registrada en esta OLT" in error for error in result.errors)


def test_dry_run_does_not_use_telnet_or_ssh(db_session, catalog, monkeypatch):
    def fail_if_driver_is_requested(*_args, **_kwargs):
        raise AssertionError("Dry-run provisioning must not request network drivers")

    monkeypatch.setattr("app.services.olt_service.OltService.driver_for", fail_if_driver_is_requested)

    plan = ProvisioningService(db_session).create_plan(payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id))

    assert plan.generated_cli
    assert "configure terminal" not in plan.generated_cli.lower()
    assert "write" not in plan.generated_cli.lower()


def test_detects_next_available_onu_id(db_session, catalog):
    for onu_id in [1, 2, 3, 5]:
        db_session.add(
            Onu(
                olt_id=catalog["olt"].id,
                customer_name=f"Cliente {onu_id}",
                serial_number=f"ZTEGFREE{onu_id}",
                onu_interface=f"gpon-onu_1/2/15:{onu_id}",
                onu_type="VSOL",
                vlan=200,
                speed_profile="SMARTOLT-1G",
                speed_profile_up="SMARTOLT-1G-UP",
                speed_profile_down="SMARTOLT-1G-DOWN",
                status="online",
                import_source="cli_import",
            )
        )
    db_session.commit()

    plan = ProvisioningService(db_session).create_plan(payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id))
    _, result = ProvisioningService(db_session).validate_and_update(plan.id)

    assert result.suggested_onu_id == 4
    assert "onu 4 type VSOL sn GPON00CBAC10" in result.cli_preview


def test_detects_occupied_selected_onu_id(db_session, catalog):
    db_session.add(
        Onu(
            olt_id=catalog["olt"].id,
            customer_name="Ocupada",
            serial_number="ZTEGOCCUPIED1",
            onu_interface="gpon-onu_1/2/15:1",
            onu_type="VSOL",
            vlan=200,
            speed_profile="SMARTOLT-1G",
            speed_profile_up="SMARTOLT-1G-UP",
            speed_profile_down="SMARTOLT-1G-DOWN",
            status="online",
            import_source="cli_import",
        )
    )
    db_session.commit()

    plan = ProvisioningService(db_session).create_plan(
        payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id, selected_onu_id=1)
    )
    _, result = ProvisioningService(db_session).validate_and_update(plan.id)

    assert result.suggested_onu_id == 2
    assert any("ONU ID 1 ya esta ocupado" in error for error in result.errors)


def test_invalid_vlan_profile_and_template_are_errors(db_session, catalog):
    db_session.query(ProvisioningTemplate).delete()
    db_session.commit()

    plan = ProvisioningService(db_session).create_plan(
        payload(
            catalog["pending"].id,
            catalog["zone"].id,
            catalog["nap"].id,
            vlan=999,
            speed_profile_up="NO-UP",
            speed_profile_down="NO-DOWN",
        )
    )
    _, result = ProvisioningService(db_session).validate_and_update(plan.id)

    assert any("VLAN 999" in error for error in result.errors)
    assert any("perfil UP NO-UP" in error for error in result.errors)
    assert any("perfil DOWN NO-DOWN" in error for error in result.errors)
    assert any("ProvisioningTemplate" in error for error in result.errors)


def test_duplicate_serial_in_production_is_error(db_session, catalog):
    other_prod = Olt(
        olt_code="OLT-PROD-02",
        name="FTTH-PCM-ZTE2",
        environment="production",
        vendor="ZTE",
        model="C300",
        firmware="V1.2.5P3",
        ip_address="127.0.0.3",
        username="admin",
        password_encrypted="secret",
    )
    db_session.add(other_prod)
    db_session.flush()
    db_session.add(
        Onu(
            olt_id=other_prod.id,
            customer_name="Duplicada",
            serial_number="GPON00CBAC10",
            onu_interface="gpon-onu_1/1/1:1",
            onu_type="VSOL",
            vlan=200,
            speed_profile="SMARTOLT-1G",
            speed_profile_up="SMARTOLT-1G-UP",
            speed_profile_down="SMARTOLT-1G-DOWN",
            status="online",
            import_source="cli_import",
        )
    )
    db_session.commit()

    plan = ProvisioningService(db_session).create_plan(payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id))
    _, result = ProvisioningService(db_session).validate_and_update(plan.id)

    assert any("otra OLT de produccion" in error for error in result.errors)
