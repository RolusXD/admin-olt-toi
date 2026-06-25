from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import Nap, Olt, Onu, Zone
from app.services.territorial_audit_center_service import (
    TerritorialAuditCenterService,
)


def _setup_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


def _create_olt(session: Session, *, code: str, environment: str) -> Olt:
    olt = Olt(
        olt_code=code,
        name=code,
        ip_address="127.0.0.1",
        telnet_port=23,
        username="admin",
        password_encrypted="not-used",
        environment=environment,
    )
    session.add(olt)
    session.commit()
    session.refresh(olt)
    return olt


def test_olt_with_cross_zone_generates_issue():
    """Una OLT con ONUs usando Zone de otra OLT genera issue CROSS_OLT_ZONE."""

    session = _setup_db()
    with session:
        olt_lab = _create_olt(session, code="OLT-LAB-ZTE-01", environment="lab")
        olt_pcm = _create_olt(
            session, code="OLT-PCM-ZTE-01", environment="production"
        )

        lab_zone = Zone(
            olt_id=olt_lab.id,
            olt_code_snapshot=olt_lab.olt_code,
            name="Lagunas",
            code="Lagunas",
            source="manual",
        )
        session.add(lab_zone)
        session.commit()
        session.refresh(lab_zone)

        onu = Onu(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            customer_name="Cliente PCM",
            serial_number="SN-PCM-001",
            onu_interface="gpon-onu_1/2/3:1",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            zone_id=lab_zone.id,
            zone_name="Lagunas",
            parsed_zone_name="Lagunas",
        )
        session.add(onu)
        session.commit()

        service = TerritorialAuditCenterService(session)
        audit = service.build()

        # Debe existir issue CROSS_OLT_ZONE para PCM.
        cross_zone_issues = [
            i for i in audit.critical_issues if i.issue_type == "CROSS_OLT_ZONE"
        ]
        assert cross_zone_issues
        assert any(i.olt_code == "OLT-PCM-ZTE-01" for i in cross_zone_issues)


def test_olt_without_naps_generates_issue_no_naps():
    """Una OLT sin NAPs propios genera issue NO_NAPS."""

    session = _setup_db()
    with session:
        olt_pcm = _create_olt(
            session, code="OLT-PCM-ZTE-01", environment="production"
        )

        # Crear al menos una ONU sin NAP para que el preview tenga contexto.
        onu = Onu(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            customer_name="Cliente PCM",
            serial_number="SN-PCM-002",
            onu_interface="gpon-onu_1/2/3:2",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
        )
        session.add(onu)
        session.commit()

        service = TerritorialAuditCenterService(session)
        audit = service.build()

        no_naps_issues = [i for i in audit.critical_issues if i.issue_type == "NO_NAPS"]
        assert no_naps_issues
        assert any(i.olt_code == "OLT-PCM-ZTE-01" for i in no_naps_issues)


def test_score_decreases_when_cross_olt_relations_exist():
    """El score territorial baja cuando hay cruces de zone/nap."""

    session = _setup_db()
    with session:
        olt_lab = _create_olt(session, code="OLT-LAB-ZTE-01", environment="lab")
        olt_pcm = _create_olt(
            session, code="OLT-PCM-ZTE-01", environment="production"
        )

        lab_zone = Zone(
            olt_id=olt_lab.id,
            olt_code_snapshot=olt_lab.olt_code,
            name="Lagunas",
            code="Lagunas",
            source="manual",
        )
        session.add(lab_zone)
        session.commit()
        session.refresh(lab_zone)

        lab_nap = Nap(
            olt_id=olt_lab.id,
            olt_code_snapshot=olt_lab.olt_code,
            zone_id=lab_zone.id,
            name="ODN H5",
            code="H5",
            nap_type="ODN",
            source="manual",
        )
        session.add(lab_nap)
        session.commit()
        session.refresh(lab_nap)

        onu = Onu(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            customer_name="Cliente PCM",
            serial_number="SN-PCM-003",
            onu_interface="gpon-onu_1/2/3:3",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            zone_id=lab_zone.id,
            zone_name="Lagunas",
            parsed_zone_name="Lagunas",
            nap_id=lab_nap.id,
            nap_name="ODN H5",
            parsed_odn="ODN_H5------COOPERATIVA",
        )
        session.add(onu)
        session.commit()

        service = TerritorialAuditCenterService(session)
        audit = service.build()

        pcm_summary = next(s for s in audit.olt_summaries if s.olt_id == olt_pcm.id)
        # Score debe ser menor que 100 por los cruces.
        assert pcm_summary.territorial_health_score < 100


def test_status_is_critical_or_degraded_based_on_score():
    """El status se deriva correctamente del score territorial."""

    session = _setup_db()
    with session:
        olt = _create_olt(session, code="OLT-PCM-ZTE-01", environment="production")

        # Crear una ONU sin cruces ni NAPs/Zones para score alto.
        onu = Onu(
            olt_id=olt.id,
            olt_code_snapshot=olt.olt_code,
            customer_name="Cliente PCM",
            serial_number="SN-PCM-004",
            onu_interface="gpon-onu_1/2/3:4",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
        )
        session.add(onu)
        session.commit()

        service = TerritorialAuditCenterService(session)
        audit = service.build()

        summary = next(s for s in audit.olt_summaries if s.olt_id == olt.id)
        # Sin cruces ni NAPs, score cercano a 100 → HEALTHY o NEEDS_REVIEW.
        assert summary.territorial_health_score >= 90
        assert summary.status in {"HEALTHY", "NEEDS_REVIEW"}


def test_recommendations_include_no_apply_when_blocked_or_review():
    """Las recomendaciones incluyen no ejecutar apply con NAPs en REVIEW/BLOCKED."""

    session = _setup_db()
    with session:
        olt = _create_olt(session, code="OLT-PCM-ZTE-01", environment="production")

        # Crear una ONU con evidencia NAP ambigua para forzar un candidato REVIEW.
        onu = Onu(
            olt_id=olt.id,
            olt_code_snapshot=olt.olt_code,
            customer_name="Cliente D4",
            serial_number="SN-PCM-D4-1",
            onu_interface="gpon-onu_1/2/3:5",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            parsed_zone_name="Lagunas",
            parsed_nap_name="D4",
        )
        session.add(onu)
        session.commit()

        service = TerritorialAuditCenterService(session)
        audit = service.build()

        # Debe existir una recomendación que mencione explícitamente no ejecutar apply.
        assert any(
            "No ejecutar apply" in rec or "no ejecutar apply" in rec
            for rec in audit.recommendations
        )
