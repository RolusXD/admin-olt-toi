from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import Olt, Onu, Zone
from app.services.zone_reconstruction_preview_service import ZoneReconstructionPreviewService


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


def test_pcm_lagunas_zone_is_proposed_for_pcm_not_reusing_lab_zone():
    """Para OLT-PCM-ZTE-01 se debe proponer Zone Lagunas propia.

    - Existe una Zone "Lagunas" en LAB.
    - No existe Zone "Lagunas" en PCM.
    - Hay ONUs PCM con parsed_zone_name == "Lagunas".

    El preview debe:
    - Incluir "Lagunas" en zones_missing_proposed de PCM.
    - No considerar la Zone Lab como reutilizable para PCM.
    - Marcar las ONUs PCM con proposed_zone_name == "Lagunas" y
      proposed_zone_olt_id == olt_pcm.id.
    """

    session = _setup_db()
    with session:
        olt_lab = _create_olt(session, code="OLT-LAB-ZTE-01", environment="lab")
        olt_pcm = _create_olt(session, code="OLT-PCM-ZTE-01", environment="production")

        lab_zone_lagunas = Zone(
            olt_id=olt_lab.id,
            olt_code_snapshot=olt_lab.olt_code,
            name="Lagunas",
            code="Lagunas",
            description="Zona de laboratorio Lagunas",
            source="manual",
        )
        session.add(lab_zone_lagunas)
        session.commit()

        onu_pcm_1 = Onu(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            customer_name="Cliente PCM 1",
            serial_number="SN-PCM-001",
            onu_interface="gpon-onu_1/2/3:1",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            parsed_zone_name="Lagunas",
        )
        onu_pcm_2 = Onu(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            customer_name="Cliente PCM 2",
            serial_number="SN-PCM-002",
            onu_interface="gpon-onu_1/2/3:2",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            parsed_zone_name="Lagunas",
        )
        session.add_all([onu_pcm_1, onu_pcm_2])
        session.commit()

        service = ZoneReconstructionPreviewService(session)
        preview = service.preview()

        pcm_summary = next(s for s in preview.summaries if s.olt_id == olt_pcm.id)
        assert "Lagunas" in pcm_summary.zones_missing_proposed
        assert "Lagunas" not in pcm_summary.zones_existing

        lab_summary = next(s for s in preview.summaries if s.olt_id == olt_lab.id)
        assert "Lagunas" in lab_summary.zones_existing

        pcm_rows = [row for row in preview.onus if row.olt_id == olt_pcm.id]
        assert len(pcm_rows) == 2
        for row in pcm_rows:
            assert row.proposed_zone_name == "Lagunas"
            assert row.proposed_zone_olt_id == olt_pcm.id
            assert row.current_zone_id is None

        # Catálogo consolidado: debe existir una propuesta de Zone Lagunas para PCM.
        pcm_catalog = [c for c in preview.catalog_proposals if c.olt_id == olt_pcm.id]
        lagunas_catalog = next(c for c in pcm_catalog if c.proposed_zone_name == "Lagunas")
        assert lagunas_catalog.exists_in_olt is False
        assert lagunas_catalog.existing_zone_id is None
        assert lagunas_catalog.onu_count == 2
        assert lagunas_catalog.confidence == "ALTA"
        assert "zone_missing_in_olt" in lagunas_catalog.reasons
        assert "from_parsed_zone_name" in lagunas_catalog.reasons
        assert "parsed_zone_name" in lagunas_catalog.source_fields


def test_existing_pcm_zone_is_treated_as_correct():
    """Una Zone existente en PCM se considera zona correcta.

    Si la ONU PCM ya está apuntando a una Zone PCM coherente, el resumen
    debe contarla como `onus_with_correct_zone` y no como reasignable.
    """

    session = _setup_db()
    with session:
        olt_pcm = _create_olt(session, code="OLT-PCM-ZTE-01", environment="production")

        pcm_zone_lagunas = Zone(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            name="Lagunas",
            code="Lagunas",
            description="Zona PCM Lagunas",
            source="manual",
        )
        session.add(pcm_zone_lagunas)
        session.commit()
        session.refresh(pcm_zone_lagunas)

        onu = Onu(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            customer_name="Cliente PCM",
            serial_number="SN-PCM-003",
            onu_interface="gpon-onu_1/2/3:3",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            zone_id=pcm_zone_lagunas.id,
            zone_name="Lagunas",
        )
        session.add(onu)
        session.commit()

        service = ZoneReconstructionPreviewService(session)
        preview = service.preview()

        pcm_summary = next(s for s in preview.summaries if s.olt_id == olt_pcm.id)
        assert pcm_summary.total_onus == 1
        assert pcm_summary.onus_with_correct_zone == 1
        assert pcm_summary.onus_reassignable == 0
        assert pcm_summary.onus_with_cross_olt_zone == 0

        # Catálogo consolidado debe marcar Lagunas como existente en PCM.
        lagunas_catalog = next(
            c
            for c in preview.catalog_proposals
            if c.olt_id == olt_pcm.id and c.proposed_zone_name == "Lagunas"
        )
        assert lagunas_catalog.exists_in_olt is True
        assert lagunas_catalog.existing_zone_id == pcm_zone_lagunas.id
        assert lagunas_catalog.onu_count == 1


def test_cross_olt_zone_is_detected_and_marked_reassignable():
    """Zona cruzada (PCM usando Zone de LAB) se detecta como cross-OLT.

    La ONU debe aparecer con `cross_olt_zone_detected` en razones y el
    resumen debe incrementar `onus_with_cross_olt_zone` y
    `onus_reassignable` para PCM.
    """

    session = _setup_db()
    with session:
        olt_lab = _create_olt(session, code="OLT-LAB-ZTE-01", environment="lab")
        olt_pcm = _create_olt(session, code="OLT-PCM-ZTE-01", environment="production")

        lab_zone = Zone(
            olt_id=olt_lab.id,
            olt_code_snapshot=olt_lab.olt_code,
            name="Lagunas",
            code="Lagunas",
            description="Zona LAB Lagunas",
            source="manual",
        )
        session.add(lab_zone)
        session.commit()
        session.refresh(lab_zone)

        onu = Onu(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            customer_name="Cliente PCM",
            serial_number="SN-PCM-004",
            onu_interface="gpon-onu_1/2/3:4",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            zone_id=lab_zone.id,
            zone_name="Lagunas",
            parsed_zone_name="Lagunas",
        )
        session.add(onu)
        session.commit()

        service = ZoneReconstructionPreviewService(session)
        preview = service.preview()

        pcm_summary = next(s for s in preview.summaries if s.olt_id == olt_pcm.id)
        assert pcm_summary.onus_with_cross_olt_zone == 1
        assert pcm_summary.onus_reassignable == 1

        row = next(r for r in preview.onus if r.onu_id == onu.id)
        assert "cross_olt_zone_detected" in row.reasons
        assert row.current_zone_olt_id == olt_lab.id
        assert row.proposed_zone_olt_id == olt_pcm.id

        # Catálogo consolidado debe marcar la propuesta como afectada por cruce.
        lagunas_catalog = next(
            c
            for c in preview.catalog_proposals
            if c.olt_id == olt_pcm.id and c.proposed_zone_name == "Lagunas"
        )
        assert lagunas_catalog.onu_count == 1
        assert "affected_by_cross_olt_zone" in lagunas_catalog.reasons


def test_onu_without_any_zone_information_is_blocked():
    """Sin evidencia de zona, la ONU debe marcarse como BLOQUEADO."""

    session = _setup_db()
    with session:
        olt = _create_olt(session, code="OLT-PCM-ZTE-01", environment="production")

        onu = Onu(
            olt_id=olt.id,
            olt_code_snapshot=olt.olt_code,
            customer_name="Cliente PCM",
            serial_number="SN-PCM-005",
            onu_interface="gpon-onu_1/2/3:5",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            zone_id=None,
            zone_name=None,
            parsed_zone_name=None,
        )
        session.add(onu)
        session.commit()

        service = ZoneReconstructionPreviewService(session)
        preview = service.preview()

        row = next(r for r in preview.onus if r.onu_id == onu.id)
        assert row.confidence == "BLOQUEADO"
        assert "no_zone_evidence" in row.reasons
