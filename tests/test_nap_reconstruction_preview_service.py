from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import Nap, Olt, Onu, Zone
from app.services.nap_reconstruction_preview_service import (
    NapReconstructionPreviewService,
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


def test_odn_explicit_with_two_onus_proposes_new_for_pcm():
    """Caso A: ODN explícito con dos ONUs PCM.

    - Dos ONUs PCM con `parsed_odn="ODN_H5------COOPERATIVA"` y
      `parsed_zone_name="Lagunas"`.
    - No existe Nap ODN H5 en PCM.

    Se espera:
    - Propuesta de candidato ODN H5 para PCM con:
      - object_type = "ODN".
      - canonical_name = "ODN H5".
      - notes = "COOPERATIVA".
      - state = NEW.
      - confidence ALTA (prefijo explícito + 2 ONUs + zona conocida).
    """

    session = _setup_db()
    with session:
        olt_pcm = _create_olt(session, code="OLT-PCM-ZTE-01", environment="production")

        # Zona opcional (para coherencia con futuras extensiones)
        zone = Zone(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            name="Lagunas",
            code="Lagunas",
            source="manual",
        )
        session.add(zone)
        session.commit()

        onu1 = Onu(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            customer_name="Cliente 1",
            serial_number="SN-PCM-ODN-H5-1",
            onu_interface="gpon-onu_1/2/3:1",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            parsed_zone_name="Lagunas",
            parsed_odn="ODN_H5------COOPERATIVA",
        )
        onu2 = Onu(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            customer_name="Cliente 2",
            serial_number="SN-PCM-ODN-H5-2",
            onu_interface="gpon-onu_1/2/3:2",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            parsed_zone_name="Lagunas",
            parsed_odn="ODN_H5------COOPERATIVA",
        )
        session.add_all([onu1, onu2])
        session.commit()

        service = NapReconstructionPreviewService(session)
        preview = service.preview()

        # Catálogo PCM: buscar candidato ODN H5.
        pcm_catalog = [c for c in preview.catalog_proposals if c.olt_id == olt_pcm.id]
        candidate = next(
            c
            for c in pcm_catalog
            if c.object_type == "ODN" and c.canonical_name == "ODN H5"
        )

        assert candidate.exists_in_olt is False
        assert candidate.existing_nap_id is None
        assert candidate.onu_count == 2
        assert candidate.state == "NEW"
        assert candidate.confidence == "ALTA"
        assert candidate.notes == "COOPERATIVA"
        assert "ODN" in candidate.canonical_name


def test_parsed_nap_without_prefix_uses_default_type_nap_and_review_state():
    """Caso B: parsed_nap_name="D4" sin prefijo.

    - Una ONU PCM con `parsed_nap_name="D4"` y `parsed_zone_name="Lagunas"`.
    - No existe Nap NAP D4 en PCM.

    Se espera:
    - normalización con `default_type=NAP` → canonical_name = "NAP D4".
    - reasons incluyen `default_type_applied`.
    - state = REVIEW y confidence MEDIA/BAJA (no ALTA).
    """

    session = _setup_db()
    with session:
        olt_pcm = _create_olt(session, code="OLT-PCM-ZTE-01", environment="production")

        onu = Onu(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            customer_name="Cliente D4",
            serial_number="SN-PCM-D4-1",
            onu_interface="gpon-onu_1/2/3:3",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            parsed_zone_name="Lagunas",
            parsed_nap_name="D4",
        )
        session.add(onu)
        session.commit()

        service = NapReconstructionPreviewService(session)
        preview = service.preview()

        # Catálogo PCM: buscar candidato NAP D4.
        pcm_catalog = [c for c in preview.catalog_proposals if c.olt_id == olt_pcm.id]
        candidate = next(
            c
            for c in pcm_catalog
            if c.object_type == "NAP" and c.canonical_name == "NAP D4"
        )

        assert candidate.exists_in_olt is False
        assert candidate.state in {"NEW", "REVIEW"}
        # Debe ser REVIEW por uso de default_type.
        assert candidate.state == "REVIEW"
        assert candidate.confidence in {"MEDIA", "BAJA"}


def test_cross_olt_nap_is_detected_and_not_reused_from_lab():
    """Caso C: ONU PCM con nap_id apuntando a Nap LAB.

    - ONU PCM con `nap_id` de una Nap LAB.
    - parsed_nap_name/parsed_odn sugieren un candidato propio de PCM.

    Se espera:
    - `onus_with_cross_olt_nap` incrementado para PCM.
    - La propuesta NAP/ODN sea para `olt_id` PCM, nunca LAB.
    """

    session = _setup_db()
    with session:
        olt_lab = _create_olt(session, code="OLT-LAB-ZTE-01", environment="lab")
        olt_pcm = _create_olt(session, code="OLT-PCM-ZTE-01", environment="production")

        lab_nap = Nap(
            olt_id=olt_lab.id,
            olt_code_snapshot=olt_lab.olt_code,
            zone_id=1,
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
            serial_number="SN-PCM-CROSS-NAP",
            onu_interface="gpon-onu_1/2/3:4",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            nap_id=lab_nap.id,
            nap_name="ODN H5",
            parsed_odn="ODN_H5------COOPERATIVA",
        )
        session.add(onu)
        session.commit()

        service = NapReconstructionPreviewService(session)
        preview = service.preview()

        pcm_summary = next(s for s in preview.summaries if s.olt_id == olt_pcm.id)
        assert pcm_summary.onus_with_cross_olt_nap == 1

        row = next(r for r in preview.onus if r.onu_id == onu.id)
        assert row.current_nap_olt_id == olt_lab.id
        assert row.proposed_olt_id == olt_pcm.id


def test_nap_d4_and_odn_d4_produce_distinct_catalog_entries():
    """Caso D: NAP D4 y ODN D4 deben ser candidatos distintos.

    - Una ONU con `parsed_nap_name="NAP D4"`.
    - Otra ONU con `parsed_odn="ODN D4"`.

    Se espera:
    - Dos propuestas en catálogo PCM: una `NAP D4` y otra `ODN D4`.
    """

    session = _setup_db()
    with session:
        olt_pcm = _create_olt(session, code="OLT-PCM-ZTE-01", environment="production")

        onu_nap = Onu(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            customer_name="Cliente NAP D4",
            serial_number="SN-PCM-NAP-D4",
            onu_interface="gpon-onu_1/2/3:5",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            parsed_nap_name="NAP D4",
        )
        onu_odn = Onu(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            customer_name="Cliente ODN D4",
            serial_number="SN-PCM-ODN-D4",
            onu_interface="gpon-onu_1/2/3:6",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            parsed_odn="ODN D4",
        )
        session.add_all([onu_nap, onu_odn])
        session.commit()

        service = NapReconstructionPreviewService(session)
        preview = service.preview()

        pcm_catalog = [c for c in preview.catalog_proposals if c.olt_id == olt_pcm.id]
        names = {(c.object_type, c.canonical_name) for c in pcm_catalog}

        assert ("NAP", "NAP D4") in names
        assert ("ODN", "ODN D4") in names


def test_noisy_document_is_marked_review_or_blocked_not_new():
    """Caso E: ruido documental no debe generar NEW con alta confianza.

    - `parsed_nap_name="D1_Calle_Chiquito_Cliente_Garaje"`.

    Se espera:
    - Propuesta con state REVIEW o BLOCKED, nunca NEW con confianza ALTA.
    """

    session = _setup_db()
    with session:
        olt_pcm = _create_olt(session, code="OLT-PCM-ZTE-01", environment="production")

        onu = Onu(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            customer_name="Cliente Ruido",
            serial_number="SN-PCM-RUIDO",
            onu_interface="gpon-onu_1/2/3:7",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            parsed_nap_name="D1_Calle_Chiquito_Cliente_Garaje",
        )
        session.add(onu)
        session.commit()

        service = NapReconstructionPreviewService(session)
        preview = service.preview()

        pcm_catalog = [c for c in preview.catalog_proposals if c.olt_id == olt_pcm.id]
        # Tomar el único candidato.
        assert len(pcm_catalog) == 1
        candidate = pcm_catalog[0]

        assert candidate.state in {"REVIEW", "BLOCKED"}
        if candidate.state == "REVIEW":
            assert candidate.confidence in {"MEDIA", "BAJA"}


def test_existing_pcm_nap_marks_exists_state():
    """Caso F: Nap existente en PCM debe marcar estado EXISTS.

    - Nap PCM "ODN H5" ya existe.
    - ONU PCM con `parsed_odn="ODN_H5------COOPERATIVA"`.

    Se espera:
    - Propuesta con `exists_in_olt=True`, `existing_nap_id` correcto.
    - state = EXISTS.
    """

    session = _setup_db()
    with session:
        olt_pcm = _create_olt(session, code="OLT-PCM-ZTE-01", environment="production")

        zone = Zone(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            name="Lagunas",
            code="Lagunas",
            source="manual",
        )
        session.add(zone)
        session.commit()
        session.refresh(zone)

        pcm_nap = Nap(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            zone_id=zone.id,
            name="ODN H5",
            code="H5",
            nap_type="ODN",
            source="manual",
        )
        session.add(pcm_nap)
        session.commit()
        session.refresh(pcm_nap)

        onu = Onu(
            olt_id=olt_pcm.id,
            olt_code_snapshot=olt_pcm.olt_code,
            customer_name="Cliente PCM",
            serial_number="SN-PCM-ODN-H5-EXISTS",
            onu_interface="gpon-onu_1/2/3:8",
            onu_type="BTPON",
            vlan=200,
            speed_profile="imported",
            parsed_zone_name="Lagunas",
            parsed_odn="ODN_H5------COOPERATIVA",
        )
        session.add(onu)
        session.commit()

        service = NapReconstructionPreviewService(session)
        preview = service.preview()

        pcm_catalog = [c for c in preview.catalog_proposals if c.olt_id == olt_pcm.id]
        candidate = next(
            c
            for c in pcm_catalog
            if c.object_type == "ODN" and c.canonical_name == "ODN H5"
        )

        assert candidate.exists_in_olt is True
        assert candidate.existing_nap_id == pcm_nap.id
        assert candidate.state == "EXISTS"
