from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from app.models.base import Base
from app.models.entities import GponProfile, Nap, Olt, Onu, ProvisioningPlan, UnauthorizedOnu, Vlan, Zone
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
            nap,
            pending,
            Vlan(olt_id=olt.id, vlan_id=200, name="FTTH-TH1", description="FTTH-TH1"),
            GponProfile(olt_id=olt.id, profile_type="tcont", name="SMARTOLT-1G-UP", upstream_rate=None, downstream_rate=None),
            GponProfile(olt_id=olt.id, profile_type="traffic", name="SMARTOLT-1G-DOWN", upstream_rate=None, downstream_rate=None),
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


def payload(pending_id: int, zone_id: int, nap_id: int, nap_port: int = 14) -> ProvisioningPlanCreate:
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
        vlan=200,
        speed_profile_up="SMARTOLT-1G-UP",
        speed_profile_down="SMARTOLT-1G-DOWN",
    )


def test_create_validate_generate_and_approve_plan(db_session, catalog):
    service = ProvisioningService(db_session)

    plan = service.create_plan(payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id))
    plan, result = service.validate_and_update(plan.id)
    validated_status = plan.status
    approved = service.approve(plan.id)

    assert result.errors == []
    assert "existe en otra OLT" in result.warnings[0]
    assert validated_status == "validated"
    assert approved.status == "approved"
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
