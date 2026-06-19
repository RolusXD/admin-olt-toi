from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.base import Base
from app.models.entities import (
    DriverCommandLog,
    GponProfile,
    Nap,
    NapPort,
    Olt,
    Onu,
    OnuServiceModeTemplate,
    OnuType,
    ProfileCatalog,
    ProvisioningPlan,
    ProvisioningTemplate,
    UnauthorizedOnu,
    Vlan,
    Zone,
)
from app.schemas.entities import ProvisioningPlanCreate
from app.drivers.zte.c300_v125p3_telnet.parsers import CardInfo, OnuState
from app.services.provisioning_service import ProvisioningPreflightService, ProvisioningService


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
            Vlan(olt_id=olt.id, vlan_id=600, name="Troncal/Especial", description="Troncal/Especial"),
            Vlan(olt_id=lab.id, vlan_id=600, name="LAB", description="LAB", is_active=False),
            GponProfile(olt_id=olt.id, profile_type="tcont", name="SMARTOLT-1G-UP", upstream_rate=None, downstream_rate=None),
            GponProfile(olt_id=olt.id, profile_type="traffic", name="SMARTOLT-1G-DOWN", upstream_rate=None, downstream_rate=None),
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
            OnuType(
                olt_id=olt.id,
                name="Prueba-vSol-no-usar",
                display_name="VSOL / 2 LAN + WiFi",
                operational_alias="VSOL",
                vendor_detected="VSOL",
                max_tcont=8,
                max_gemport=32,
                max_ports=2,
                ethernet_ports=2,
                is_provisioning_allowed=True,
            ),
            OnuServiceModeTemplate(
                olt_id=olt.id,
                mode_code="bridge_tag_internet",
                name="Modo Bridge TAG Internet",
                vlan_mode="tag",
                dhcp_source="from-internet",
                use_veip=True,
                use_loop_detect=True,
                template_body=(
                    "loop-detect ethuni {ethernet_port} enable\n"
                    "flow mode 1 tag-filter vid-filter untag-filter discard\n"
                    "flow 1 priority 0 vid {vlan}\n"
                    "gemport 1 flow 1\n"
                    "switchport-bind switch_0/1 veip 1\n"
                    "vlan port {ethernet_port} mode tag vlan {vlan}\n"
                    "dhcp-ip ethuni {ethernet_port} from-internet"
                ),
                source="imported",
            ),
            OnuServiceModeTemplate(
                olt_id=olt.id,
                mode_code="router_iphost",
                name="Modo Router IPHost",
                vlan_mode="unknown",
                dhcp_source="from-onu",
                use_iphost=True,
                use_veip=True,
                use_vlan_filter=True,
                template_body=(
                    "flow 1 priority 0 vid {vlan}\n"
                    "switchport-bind switch_0/1 iphost 1\n"
                    "switchport-bind switch_0/1 veip 1\n"
                    "vlan-filter-mode iphost 1 tag-filter vid-filter untag-filter discard\n"
                    "vlan-filter iphost 1 priority 0 vid {vlan}\n{dhcp_lines}"
                ),
                source="imported",
            ),
            OnuServiceModeTemplate(
                olt_id=olt.id,
                mode_code="transparent_special",
                name="Modo Transparent Especial",
                vlan_mode="transparent",
                dhcp_source="from-internet",
                use_iphost=True,
                use_veip=True,
                use_vlan_filter=True,
                disable_wifi=True,
                template_body=(
                    "flow 1 priority 0 vid {vlan}\n"
                    "switchport-bind switch_0/1 iphost 1\n"
                    "switchport-bind switch_0/1 veip 1\n"
                    "vlan-filter-mode iphost 1 tag-filter vid-filter untag-filter discard\n"
                    "vlan-filter iphost 1 priority 0 vid {vlan}\n"
                    "{ethernet_vlan_lines}\n{dhcp_lines}\nwifi disable"
                ),
                source="imported",
            ),
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
                    "description {description_generated}\n"
                    "tcont 1 profile {speed_profile_up}\n"
                    "gemport 1 unicast tcont 1 dir both\n"
                    "gemport 1 traffic-limit downstream {speed_profile_down}\n"
                    "switchport mode hybrid vport 1\n"
                    "switchport vlan {vlan} tag vport 1\n"
                    "exit\n"
                    "pon-onu-mng {onu_interface}\n"
                    "loop-detect ethuni {ethernet_port} enable\n"
                    "flow mode 1 tag-filter vid-filter untag-filter discard\n"
                    "flow 1 priority 0 vid {vlan}\n"
                    "gemport 1 flow 1\n"
                    "switchport-bind switch_0/1 veip 1\n"
                    "vlan port {ethernet_port} mode {vlan_lan_mode} vlan {vlan}\n"
                    "dhcp-ip ethuni {ethernet_port} {dhcp_mode}\n"
                    "security-mng 998 state enable mode permit ingress-type lan protocol web https\n"
                    "security-mng 999 state enable ingress-type lan protocol ftp telnet ssh snmp tr069\n"
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
    selected_onu_id: int = 1,
    vlan: int = 200,
    speed_profile_up: str = "SMARTOLT-1G-UP",
    speed_profile_down: str = "SMARTOLT-1G-DOWN",
    onu_type: str = "Prueba-vSol-no-usar",
    upload_profile_id: int = 1,
    download_profile_id: int = 2,
    onu_name: str = "Cliente_Prueba",
    onu_description: str = "$$$$zone_Zone_1_descr__extid_GPON00CBAC10_authd_20210124",
    customer_name: str = "Cliente Prueba",
    service_mode_code: str = "bridge_tag_internet",
) -> ProvisioningPlanCreate:
    return ProvisioningPlanCreate(
        unauthorized_onu_id=pending_id,
        customer_name=customer_name,
        customer_reference="TEST-001",
        onu_name=onu_name,
        onu_description=onu_description,
        technical_comment="Dry run controlado",
        address="Direccion de prueba",
        notes="No ejecutar",
        zone_id=zone_id,
        nap_id=nap_id,
        nap_port=nap_port,
        onu_type=onu_type,
        vlan=vlan,
        speed_profile_up=speed_profile_up,
        speed_profile_down=speed_profile_down,
        upload_profile_id=upload_profile_id,
        download_profile_id=download_profile_id,
        selected_onu_id=selected_onu_id,
        service_mode_code=service_mode_code,
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
    assert approved.onu_type == "Prueba-vSol-no-usar"
    assert "onu 1 type Prueba-vSol-no-usar sn GPON00CBAC10" in approved.generated_cli
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

    plan = ProvisioningService(db_session).create_plan(payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id, selected_onu_id=4))
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

    plan = ProvisioningService(db_session).create_plan(payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id, selected_onu_id=4))
    _, result = ProvisioningService(db_session).validate_and_update(plan.id)

    assert any("ya esta registrada en esta OLT" in error for error in result.errors)


def test_dry_run_does_not_use_telnet_or_ssh(db_session, catalog, monkeypatch):
    def fail_if_driver_is_requested(*_args, **_kwargs):
        raise AssertionError("Dry-run provisioning must not request network drivers")

    monkeypatch.setattr("app.services.olt_service.OltService.driver_for", fail_if_driver_is_requested)

    plan = ProvisioningService(db_session).create_plan(
        payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id, selected_onu_id=4)
    )

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

    plan = ProvisioningService(db_session).create_plan(
        payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id, selected_onu_id=4)
    )
    _, result = ProvisioningService(db_session).validate_and_update(plan.id)

    assert result.suggested_onu_id == 4
    assert "onu 4 type Prueba-vSol-no-usar sn GPON00CBAC10" in result.cli_preview


def test_onu_type_alias_uses_real_name_in_cli(db_session, catalog):
    plan = ProvisioningService(db_session).create_plan(payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id))
    _, result = ProvisioningService(db_session).validate_and_update(plan.id)

    assert result.is_valid is True
    assert plan.onu_type == "Prueba-vSol-no-usar"
    assert "type Prueba-vSol-no-usar sn GPON00CBAC10" in result.cli_preview
    assert "type VSOL sn" not in result.cli_preview
    assert not any("Tipo ONU detectado" in warning for warning in result.warnings)


def test_disabled_onu_type_blocks_provisioning(db_session, catalog):
    onu_type = db_session.scalar(select(OnuType).where(OnuType.operational_alias == "VSOL"))
    onu_type.is_provisioning_allowed = False
    db_session.commit()

    plan = ProvisioningService(db_session).create_plan(payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id))
    _, result = ProvisioningService(db_session).validate_and_update(plan.id)

    assert result.is_valid is False
    assert any("no esta habilitado para aprovisionamiento" in error for error in result.errors)


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
            upload_profile_id=999,
            download_profile_id=998,
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


def test_create_plan_without_vlan_fails_validation(catalog):
    with pytest.raises(ValidationError):
        ProvisioningPlanCreate(
            unauthorized_onu_id=catalog["pending"].id,
            customer_name="Cliente",
            onu_name="ONU",
            onu_description="desc",
            zone_id=catalog["zone"].id,
            nap_id=catalog["nap"].id,
            nap_port=1,
            onu_type="Prueba-vSol-no-usar",
            vlan=0,
            upload_profile_id=1,
            download_profile_id=2,
            selected_onu_id=1,
            service_mode_code="bridge_tag_internet",
        )


def test_create_plan_without_onu_type_fails_validation(catalog):
    with pytest.raises(ValidationError):
        payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id, onu_type="   ")


def test_create_plan_without_upload_profile_fails_validation(catalog):
    with pytest.raises(ValidationError):
        ProvisioningPlanCreate(
            unauthorized_onu_id=catalog["pending"].id,
            customer_name="Cliente",
            onu_name="ONU",
            onu_description="desc",
            zone_id=catalog["zone"].id,
            nap_id=catalog["nap"].id,
            nap_port=1,
            onu_type="Prueba-vSol-no-usar",
            vlan=600,
            download_profile_id=2,
            selected_onu_id=1,
            service_mode_code="bridge_tag_internet",
        )


def test_create_plan_without_download_profile_fails_validation(catalog):
    with pytest.raises(ValidationError):
        ProvisioningPlanCreate(
            unauthorized_onu_id=catalog["pending"].id,
            customer_name="Cliente",
            onu_name="ONU",
            onu_description="desc",
            zone_id=catalog["zone"].id,
            nap_id=catalog["nap"].id,
            nap_port=1,
            onu_type="Prueba-vSol-no-usar",
            vlan=600,
            upload_profile_id=1,
            selected_onu_id=1,
            service_mode_code="bridge_tag_internet",
        )


def test_create_plan_without_service_mode_fails_validation(catalog):
    data = payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id).model_dump()
    data.pop("service_mode_code")

    with pytest.raises(ValidationError):
        ProvisioningPlanCreate(**data)


def test_vlan_selector_data_filters_by_olt_and_active(db_session, catalog):
    visible_vlans = db_session.scalars(
        select(Vlan).where(Vlan.olt_id == catalog["olt"].id, Vlan.is_active.is_(True)).order_by(Vlan.vlan_id)
    ).all()

    assert [vlan.vlan_id for vlan in visible_vlans] == [200, 600]
    assert all(vlan.olt_id == catalog["olt"].id for vlan in visible_vlans)


def test_gpon00cbac10_generates_real_zte_cli_with_vlan_600(db_session, catalog):
    plan = ProvisioningService(db_session).create_plan(
        payload(
            catalog["pending"].id,
            catalog["zone"].id,
            catalog["nap"].id,
            nap_port=2,
            selected_onu_id=1,
            vlan=600,
            customer_name="TR Camacho FO",
            onu_description="$$$$zone_Zone_1_descr__extid_GPON00CBAC10_authd_20210124",
            service_mode_code="transparent_special",
        )
    )

    expected = """interface gpon-olt_1/2/15
onu 1 type Prueba-vSol-no-usar sn GPON00CBAC10
exit
interface gpon-onu_1/2/15:1
name TR_Camacho_FO
description $$$$zone_Zone_1_descr__extid_GPON00CBAC10_authd_20210124
tcont 1 profile SMARTOLT-1G-UP
gemport 1 unicast tcont 1 dir both
gemport 1 traffic-limit downstream SMARTOLT-1G-DOWN
switchport mode hybrid vport 1
switchport vlan 600 tag vport 1
exit
pon-onu-mng gpon-onu_1/2/15:1
flow 1 priority 0 vid 600
switchport-bind switch_0/1 iphost 1
switchport-bind switch_0/1 veip 1
vlan-filter-mode iphost 1 tag-filter vid-filter untag-filter discard
vlan-filter iphost 1 priority 0 vid 600
vlan port eth_0/1 mode transparent
vlan port eth_0/2 mode transparent
dhcp-ip ethuni eth_0/1 from-internet
dhcp-ip ethuni eth_0/2 from-internet
wifi disable
exit"""

    assert plan.generated_cli == expected
    assert "type Prueba-vSol-no-usar sn GPON00CBAC10" in plan.generated_cli
    assert "switchport vlan 600 tag vport 1" in plan.generated_cli
    assert "SMARTOLT-1G-UP" in plan.generated_cli
    assert "SMARTOLT-1G-DOWN" in plan.generated_cli
    assert "pon-onu-mng gpon-onu_1/2/15:1" in plan.generated_cli
    assert "vlan-filter iphost 1 priority 0 vid 600" in plan.generated_cli
    assert "vlan port eth_0/1 mode transparent" in plan.generated_cli
    assert "vlan port eth_0/2 mode transparent" in plan.generated_cli


def test_nap_port_is_optional_and_cli_keeps_management_block(db_session, catalog):
    plan = ProvisioningService(db_session).create_plan(
        payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id, nap_port=None, selected_onu_id=1, vlan=600)
    )
    _, result = ProvisioningService(db_session).validate_and_update(plan.id)

    assert result.errors == []
    assert plan.nap_port is None
    assert "pon-onu-mng gpon-onu_1/2/15:1" in plan.generated_cli
    assert "vlan port eth_0/1 mode tag vlan 600" in plan.generated_cli
    assert "dhcp-ip ethuni eth_0/1 from-internet" in plan.generated_cli


class FakePreflightDriver:
    def __init__(self, state_onu_id: int | None = None, uncfg_serial: str = "GPON00CBAC10"):
        self.commands: list[str] = []
        self.connected = False
        self.state_onu_id = state_onu_id
        self.uncfg_serial = uncfg_serial

    def connect(self, disable_paging=True):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def execute(self, command: str, read_only: bool = True):
        self.commands.append(command)
        assert read_only is True
        assert command == "show version-running"
        return "ZXA10 C300 Software Version V1.2.5P3"

    def show_card(self):
        self.commands.append("show card")
        return [CardInfo(slot="1/1/2", card_type="GTGHG", status="online", real_type="GTGHG", firmware="V1.2.5P3", ports=16)]

    def show_uncfg_raw(self):
        self.commands.append("show gpon onu uncfg")
        return f"gpon-onu_1/2/15:1        {self.uncfg_serial}        VSOL"

    def show_onu_state(self):
        self.commands.append("show gpon onu state")
        if self.state_onu_id is None:
            return []
        return [OnuState(f"gpon-onu_1/2/15:{self.state_onu_id}", "ZTEGOCCUPIED", "online", "working", None)]


def approved_plan(db_session, catalog):
    service = ProvisioningService(db_session)
    plan = service.create_plan(payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id, selected_onu_id=1))
    return service.approve(plan.id)


def test_preflight_passes_for_approved_plan_and_logs_read_only_commands(db_session, catalog, monkeypatch):
    plan = approved_plan(db_session, catalog)
    driver = FakePreflightDriver()
    monkeypatch.setattr("app.services.olt_service.OltService.driver_for", lambda *_args, **_kwargs: driver)

    plan, result = ProvisioningPreflightService(db_session).run(plan.id)

    assert result["is_valid"] is True
    assert plan.status == "preflight_passed"
    assert result["checks"] == {
        "olt_accessible": True,
        "card_exists": True,
        "pon_exists": True,
        "onu_detected": True,
        "serial_detected": True,
        "onu_id_available": True,
        "vlan_exists": True,
        "upload_profile_exists": True,
        "download_profile_exists": True,
        "onu_type_exists": True,
    }
    assert driver.commands == ["show version-running", "show card", "show gpon onu uncfg", "show gpon onu state"]
    logs = db_session.scalars(select(DriverCommandLog).where(DriverCommandLog.olt_id == catalog["olt"].id)).all()
    assert [log.command for log in logs] == driver.commands
    assert all(log.read_only is True for log in logs)


def test_preflight_detects_occupied_onu_id(db_session, catalog, monkeypatch):
    plan = approved_plan(db_session, catalog)
    driver = FakePreflightDriver(state_onu_id=1)
    monkeypatch.setattr("app.services.olt_service.OltService.driver_for", lambda *_args, **_kwargs: driver)

    plan, result = ProvisioningPreflightService(db_session).run(plan.id)

    assert result["is_valid"] is False
    assert plan.status == "preflight_failed"
    assert result["checks"]["onu_id_available"] is False
    assert any("ONU ID 1" in error for error in result["errors"])


def test_preflight_requires_approved_plan(db_session, catalog, monkeypatch):
    plan = ProvisioningService(db_session).create_plan(payload(catalog["pending"].id, catalog["zone"].id, catalog["nap"].id))

    def fail_if_driver_is_requested(*_args, **_kwargs):
        raise AssertionError("Preflight must not connect unless plan is approved")

    monkeypatch.setattr("app.services.olt_service.OltService.driver_for", fail_if_driver_is_requested)

    with pytest.raises(HTTPException) as exc:
        ProvisioningPreflightService(db_session).run(plan.id)
    assert "approved" in exc.value.detail
