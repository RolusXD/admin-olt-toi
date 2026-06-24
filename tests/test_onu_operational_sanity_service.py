import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import ConfigSnapshot, ImportJob, Olt, Onu
from app.services.onu_operational_sanity_service import OnuOperationalSanityService


def _setup_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


def _create_production_olt(session: Session, *, code: str = "OLT-PROD-01") -> Olt:
    olt = Olt(
        olt_code=code,
        name=code,
        ip_address="127.0.0.1",
        telnet_port=23,
        username="admin",
        password_encrypted="not-used",
        environment="production",
    )
    session.add(olt)
    session.commit()
    session.refresh(olt)
    return olt


def _attach_snapshot_with_mode(session: Session, olt: Olt, *, onu_interface: str, mode_block: str) -> None:
    """Crea un snapshot + import job confirmados con un único bloque pon-onu-mng.

    Esto permite que OnuOperationalSanityService utilice parse_onu_management_modes
    para inferir service_mode_code sin ejecutar Telnet ni reparsear el
    fixture completo.
    """

    raw_config = mode_block
    snapshot = ConfigSnapshot(
        olt_id=olt.id,
        raw_config=raw_config,
        source_command="show running-config",
        status="confirmed",
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)

    job = ImportJob(
        olt_id=olt.id,
        status="confirmed",
        source="text",
        raw_config_snapshot_id=snapshot.id,
        parsed_summary_json=json.dumps({}, ensure_ascii=True),
    )
    session.add(job)
    session.commit()


def test_service_mode_code_null_router_detected_from_snapshot():
    """Cuando service_mode_code es NULL, el servicio debe sugerir router_iphost.

    Usa un bloque pon-onu-mng típico de router_iphost.
    """

    session = _setup_db()
    with session:
        olt = _create_production_olt(session)

        onu = Onu(
            olt_id=olt.id,
            olt_code_snapshot=olt.olt_code,
            customer_name="Cliente Router",
            serial_number="SN-ROUTER-001",
            onu_interface="gpon-onu_1/2/5:29",
            onu_type="BTPON",
            vlan=0,
            speed_profile="imported",
            service_mode_code=None,
        )
        session.add(onu)
        session.commit()
        session.refresh(onu)

        mode_block = """pon-onu-mng gpon-onu_1/2/5:29
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
!
"""

        _attach_snapshot_with_mode(session, olt, onu_interface=onu.onu_interface, mode_block=mode_block)

        service = OnuOperationalSanityService(session)
        preview = service.preview()

        assert preview.summary.total_onus == 1
        assert preview.summary.candidate_service_mode_updates == 1

        change = preview.changes[0]
        assert change.onu_id == onu.id
        assert change.current_service_mode_code is None
        assert change.suggested_service_mode_code == "router_iphost"
        assert "service_mode_from_snapshot" in change.reasons


def test_service_mode_code_null_bridge_detected_from_snapshot():
    """Cuando service_mode_code es NULL, el servicio debe sugerir bridge_tag_internet.

    Usa un bloque pon-onu-mng típico de bridge_tag_internet (sin IPHost,
    con VEIP y DHCP from-internet).
    """

    session = _setup_db()
    with session:
        olt = _create_production_olt(session)

        onu = Onu(
            olt_id=olt.id,
            olt_code_snapshot=olt.olt_code,
            customer_name="Cliente Bridge",
            serial_number="SN-BRIDGE-001",
            onu_interface="gpon-onu_1/2/13:4",
            onu_type="BTPON",
            vlan=0,
            speed_profile="imported",
            service_mode_code=None,
        )
        session.add(onu)
        session.commit()
        session.refresh(onu)

        mode_block = """pon-onu-mng gpon-onu_1/2/13:4
flow mode 1 tag-filter vid-filter untag-filter discard
flow 1 priority 0 vid 200
gemport 1 flow 1
switchport-bind switch_0/1 veip 1
vlan port eth_0/1 mode trunk
vlan port eth_0/1 vlan 200
dhcp-ip ethuni eth_0/1 from-internet
!
"""

        _attach_snapshot_with_mode(session, olt, onu_interface=onu.onu_interface, mode_block=mode_block)

        service = OnuOperationalSanityService(session)
        preview = service.preview()

        assert preview.summary.total_onus == 1
        assert preview.summary.candidate_service_mode_updates == 1

        change = preview.changes[0]
        assert change.onu_id == onu.id
        assert change.current_service_mode_code is None
        assert change.suggested_service_mode_code == "bridge_tag_internet"
        assert "service_mode_from_snapshot" in change.reasons


def test_description_old_zone_recovered_when_missing():
    """Si la ONU no tiene zona pero la descripción sí, se propone la zona.

    Verifica que `parse_onu_description` se use en modo auditoría para
    recuperar la zona desde descripciones históricas.
    """

    session = _setup_db()
    with session:
        olt = _create_production_olt(session)

        onu = Onu(
            olt_id=olt.id,
            olt_code_snapshot=olt.olt_code,
            customer_name="Cliente Descripcion",
            serial_number="SN-DESC-001",
            onu_interface="gpon-onu_1/2/10:111",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            service_mode_code=None,
            zone_name=None,
            parsed_zone_name="SIN_ZONA",
            description_original="zone_Lagunas_authd_20260225",
        )
        session.add(onu)
        session.commit()

        # Snapshot mínimo; el objetivo aquí es ejercitar sólo el parser de descripción.
        mode_block = "pon-onu-mng gpon-onu_1/2/10:111\n!\n"
        _attach_snapshot_with_mode(session, olt, onu_interface=onu.onu_interface, mode_block=mode_block)

        service = OnuOperationalSanityService(session)
        preview = service.preview()

        assert preview.summary.total_onus == 1
        # No esperamos cambios de modo de servicio en este caso.
        assert preview.summary.candidate_service_mode_updates == 0
        assert preview.summary.candidate_zone_updates == 1

        change = preview.changes[0]
        assert change.current_zone_name in {None, "SIN_ZONA"}
        assert change.suggested_zone_name == "Lagunas"
        assert "zone_from_description" in change.reasons
        # También debería detectar AUTHD desde la descripción.
        assert change.suggested_auth_date is not None
        assert "auth_date_from_description" in change.reasons


def test_lab_olt_is_excluded_even_if_environment_misconfigured():
    """La OLT de laboratorio OLT-LAB-ZTE-01 debe ser excluida explícitamente.

    Aunque su `environment` estuviera configurado erróneamente como
    "production", el servicio de saneamiento no debe procesarla.
    """

    session = _setup_db()
    with session:
        lab_olt = _create_production_olt(session, code="OLT-LAB-ZTE-01")

        onu = Onu(
            olt_id=lab_olt.id,
            olt_code_snapshot=lab_olt.olt_code,
            customer_name="Cliente Lab",
            serial_number="SN-LAB-001",
            onu_interface="gpon-onu_1/2/20:7",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            service_mode_code=None,
        )
        session.add(onu)
        session.commit()

        mode_block = """pon-onu-mng gpon-onu_1/2/20:7
flow mode 1 tag-filter vid-filter untag-filter discard
flow 1 priority 0 vid 200
gemport 1 flow 1
switchport-bind switch_0/1 veip 1
vlan port eth_0/1 mode trunk
vlan port eth_0/1 vlan 200
dhcp-ip ethuni eth_0/1 from-internet
!
"""

        _attach_snapshot_with_mode(session, lab_olt, onu_interface=onu.onu_interface, mode_block=mode_block)

        service = OnuOperationalSanityService(session)
        preview = service.preview()

        # La OLT lab debe ser ignorada completamente.
        assert preview.summary.total_onus == 0
        assert preview.changes == []
