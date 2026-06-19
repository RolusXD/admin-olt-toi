from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from app.api.routes.nap_ports import reserve_nap_port, release_nap_port
from app.api.routes.onu_types import create_onu_type, deactivate_onu_type
from app.api.routes.profile_catalogs import create_profile_catalog, deactivate_profile_catalog
from app.api.routes.speed_profiles import create_speed_profile, deactivate_speed_profile
from app.models.base import Base
from app.models.entities import (
    GponProfile,
    Nap,
    NapPort,
    Olt,
    Onu,
    OnuType,
    ProfileCatalog,
    ProvisioningTemplate,
    SpeedProfile,
    UnauthorizedOnu,
    Vlan,
    Zone,
)
from app.schemas.entities import OnuTypeCreate, ProfileCatalogCreate, ProvisioningPlanCreate, SpeedProfileCreate
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
        olt_code="OLT-MASTER",
        name="OLT Master",
        environment="production",
        ip_address="127.0.0.1",
        username="admin",
        password_encrypted="secret",
    )
    zone = Zone(name="Lagunas", code="LAG", is_active=True, source="manual")
    db_session.add_all([olt, zone])
    db_session.flush()
    nap = Nap(zone_id=zone.id, name="C1", code="C1", capacity=4, is_active=True, source="manual")
    db_session.add(nap)
    db_session.flush()
    db_session.add_all([NapPort(nap_id=nap.id, port_number=port, status="free") for port in range(1, 5)])
    db_session.add_all(
        [
            Vlan(olt_id=olt.id, olt_code_snapshot=olt.olt_code, vlan_id=200, description="FTTH", is_active=True, source="manual"),
            GponProfile(olt_id=olt.id, profile_type="tcont", name="SMARTOLT-1G-UP"),
            GponProfile(olt_id=olt.id, profile_type="traffic", name="SMARTOLT-1G-DOWN"),
            ProfileCatalog(
                olt_id=olt.id,
                olt_code_snapshot=olt.olt_code,
                vendor="ZTE",
                model="C300",
                firmware="V1.2.5P3",
                direction="upload",
                profile_kind="tcont",
                name="SMARTOLT-1G-UP",
                is_active=True,
            ),
            ProfileCatalog(
                olt_id=olt.id,
                olt_code_snapshot=olt.olt_code,
                vendor="ZTE",
                model="C300",
                firmware="V1.2.5P3",
                direction="download",
                profile_kind="traffic",
                name="SMARTOLT-1G-DOWN",
                is_active=True,
            ),
            ProvisioningTemplate(
                name="default",
                vendor="ZTE",
                model="C300",
                firmware="V1.2.5P3",
                template_name="default",
                template_body="onu {onu_index} type {onu_type} sn {serial_number}",
                commands="onu {onu_index} type {onu_type} sn {serial_number}",
                is_default=True,
                is_active=True,
            ),
            UnauthorizedOnu(
                olt_id=olt.id,
                olt_code_snapshot=olt.olt_code,
                pon_port_interface="gpon-olt_1/2/15",
                serial_number="GPON00CBAC10",
                detected_vendor="VSOL",
                status="pending",
            ),
        ]
    )
    db_session.commit()
    return {"olt": olt, "zone": zone, "nap": nap}


def test_crud_onu_type_and_deactivate(db_session, catalog):
    created = create_onu_type(
        OnuTypeCreate(
            olt_id=catalog["olt"].id,
            name="Prueba-vSol-no-usar",
            display_name="VSOL / 2 LAN + WiFi",
            operational_alias="VSOL",
            vendor_detected="VSOL",
            ethernet_ports=2,
            wifi_ports=1,
            is_provisioning_allowed=True,
        ),
        db_session,
    )
    assert created.source == "manual"
    assert created.is_active is True
    assert created.operational_alias == "VSOL"
    assert created.is_provisioning_allowed is True

    deactivated = deactivate_onu_type(created.id, db_session)

    assert deactivated.is_active is False
    assert db_session.scalar(select(OnuType).where(OnuType.name == "Prueba-vSol-no-usar")) is not None


def test_crud_speed_profile_and_deactivate(db_session, catalog):
    created = create_speed_profile(
        SpeedProfileCreate(
            olt_id=catalog["olt"].id,
            name="Plan 1G",
            profile_code="TOI-1G",
            upstream_profile_name="SMARTOLT-1G-UP",
            downstream_profile_name="SMARTOLT-1G-DOWN",
        ),
        db_session,
    )
    assert created.source == "manual"

    deactivated = deactivate_speed_profile(created.id, db_session)

    assert deactivated.is_active is False


def test_crud_profile_catalog_and_deactivate(db_session, catalog):
    created = create_profile_catalog(
        ProfileCatalogCreate(
            olt_id=catalog["olt"].id,
            direction="upload",
            profile_kind="tcont",
            name="MANUAL-UP",
            maximum_kbps=512000,
        ),
        db_session,
    )
    assert created.source == "manual"
    assert created.direction == "upload"

    deactivated = deactivate_profile_catalog(created.id, db_session)

    assert deactivated.is_active is False


def test_profile_catalog_default_is_unique_by_olt_direction_type(db_session, catalog):
    first = create_profile_catalog(
        ProfileCatalogCreate(
            olt_id=catalog["olt"].id,
            direction="upload",
            profile_kind="tcont",
            name="DEFAULT-UP-1",
            service_type="internet",
            maximum_kbps=100000,
            is_default=True,
        ),
        db_session,
    )
    second = create_profile_catalog(
        ProfileCatalogCreate(
            olt_id=catalog["olt"].id,
            direction="upload",
            profile_kind="tcont",
            name="DEFAULT-UP-2",
            service_type="internet",
            maximum_kbps=200000,
            is_default=True,
        ),
        db_session,
    )

    db_session.refresh(first)
    db_session.refresh(second)

    assert first.is_default is False
    assert second.is_default is True
    assert second.speed_kbps == 200000


def test_nap_port_reserve_and_release(db_session, catalog):
    port = db_session.scalar(select(NapPort).where(NapPort.nap_id == catalog["nap"].id, NapPort.port_number == 1))

    reserved = reserve_nap_port(port.id, db_session)
    released = release_nap_port(port.id, db_session)

    assert reserved.status in {"reserved", "free"}
    assert released.status == "free"


def test_provisioning_uses_speed_profile_and_blocks_occupied_nap_port(db_session, catalog):
    onu_type = OnuType(
        olt_id=catalog["olt"].id,
        olt_code_snapshot=catalog["olt"].olt_code,
        name="VSOL",
        vendor_detected="VSOL",
        is_active=True,
        is_provisioning_allowed=True,
    )
    speed = SpeedProfile(
        olt_id=catalog["olt"].id,
        olt_code_snapshot=catalog["olt"].olt_code,
        vendor="ZTE",
        model="C300",
        firmware="V1.2.5P3",
        name="Plan 1G",
        profile_code="TOI-1G",
        upstream_profile_name="SMARTOLT-1G-UP",
        downstream_profile_name="SMARTOLT-1G-DOWN",
        upload_profile_id=db_session.scalar(select(ProfileCatalog).where(ProfileCatalog.name == "SMARTOLT-1G-UP")).id,
        download_profile_id=db_session.scalar(select(ProfileCatalog).where(ProfileCatalog.name == "SMARTOLT-1G-DOWN")).id,
        is_active=True,
    )
    db_session.add_all([onu_type, speed])
    db_session.flush()
    db_session.add(
        Onu(
            olt_id=catalog["olt"].id,
            customer_name="Ocupada",
            serial_number="ZTEGOCCUPIED",
            onu_interface="gpon-onu_1/2/15:2",
            onu_type="VSOL",
            vlan=200,
            speed_profile="SMARTOLT-1G",
            nap_id=catalog["nap"].id,
            nap_port=2,
            status="online",
        )
    )
    occupied_port = db_session.scalar(select(NapPort).where(NapPort.nap_id == catalog["nap"].id, NapPort.port_number == 2))
    occupied_port.status = "occupied"
    db_session.commit()
    unauthorized = db_session.scalar(select(UnauthorizedOnu).where(UnauthorizedOnu.serial_number == "GPON00CBAC10"))

    plan = ProvisioningService(db_session).create_plan(
        ProvisioningPlanCreate(
            unauthorized_onu_id=unauthorized.id,
            customer_name="Cliente",
            onu_name="Cliente_ONU",
            onu_description="$$$$zone_Zone_1_descr__extid_GPON00CBAC10_authd_20210124",
            zone_id=catalog["zone"].id,
            nap_id=catalog["nap"].id,
            nap_port=2,
            onu_type="VSOL",
            vlan=200,
            speed_profile_id=speed.id,
            upload_profile_id=speed.upload_profile_id,
            download_profile_id=speed.download_profile_id,
            selected_onu_id=1,
        )
    )
    _, result = ProvisioningService(db_session).validate_and_update(plan.id)

    assert plan.speed_profile_up == "SMARTOLT-1G-UP"
    assert plan.speed_profile_down == "SMARTOLT-1G-DOWN"
    assert any("puerto NAP 2" in error for error in result.errors)
