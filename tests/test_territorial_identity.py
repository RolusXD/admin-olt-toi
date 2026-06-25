from __future__ import annotations

from app.services.territorial_identity import (
    TerritorialNormalizer,
    TerritorialObjectType,
)


def test_odn_h5_with_notes_is_normalized_with_prefix_and_notes():
    normalizer = TerritorialNormalizer()

    identity = normalizer.normalize_territorial_object(
        "ODN H5------COOPERATIVA", olt_id=3
    )

    assert identity is not None
    assert identity.object_type is TerritorialObjectType.ODN
    assert identity.code == "H5"
    assert identity.canonical_name == "ODN H5"
    assert identity.notes == "COOPERATIVA"
    assert identity.identity_score == 90
    assert "explicit_prefix" in identity.reasons
    assert "notes_extracted" in identity.reasons


def test_odn_c4_with_underscore_normalizes_separator_and_keeps_score_100():
    normalizer = TerritorialNormalizer()

    identity = normalizer.normalize_territorial_object("ODN C4_A", olt_id=3)

    assert identity is not None
    assert identity.object_type is TerritorialObjectType.ODN
    assert identity.code == "C4 A"
    assert identity.canonical_name == "ODN C4 A"
    assert identity.identity_score == 100
    assert "normalized_separator" in identity.reasons


def test_nap_d4_is_normalized_with_uppercase_prefix_and_code():
    normalizer = TerritorialNormalizer()

    identity = normalizer.normalize_territorial_object("nap d4", olt_id=3)

    assert identity is not None
    assert identity.object_type is TerritorialObjectType.NAP
    assert identity.code == "D4"
    assert identity.canonical_name == "NAP D4"


def test_mixed_prefix_odb_odn_prefers_odn_prefix():
    normalizer = TerritorialNormalizer()

    identity = normalizer.normalize_territorial_object(
        "odb_ODN_H5------COOPERATIVA", olt_id=3
    )

    assert identity is not None
    assert identity.object_type is TerritorialObjectType.ODN
    assert identity.code == "H5"
    assert identity.canonical_name == "ODN H5"
    assert identity.notes == "COOPERATIVA"


def test_raw_without_prefix_and_without_default_type_returns_none():
    normalizer = TerritorialNormalizer()

    identity = normalizer.normalize_territorial_object("D4", olt_id=3)

    assert identity is None


def test_raw_without_prefix_and_with_default_type_uses_default():
    normalizer = TerritorialNormalizer()

    identity = normalizer.normalize_territorial_object(
        "D4", olt_id=3, default_type=TerritorialObjectType.NAP
    )

    assert identity is not None
    assert identity.object_type is TerritorialObjectType.NAP
    assert identity.code == "D4"
    assert identity.canonical_name == "NAP D4"
    assert identity.identity_score == 75
    assert "default_type_applied" in identity.reasons


def test_nap_and_odn_with_same_code_are_distinct_identities():
    normalizer = TerritorialNormalizer()

    nap_identity = normalizer.normalize_territorial_object("NAP D4", olt_id=3)
    odn_identity = normalizer.normalize_territorial_object("ODN D4", olt_id=3)

    assert nap_identity is not None
    assert odn_identity is not None
    assert nap_identity.object_type is TerritorialObjectType.NAP
    assert odn_identity.object_type is TerritorialObjectType.ODN
    assert nap_identity.canonical_name == "NAP D4"
    assert odn_identity.canonical_name == "ODN D4"
    assert nap_identity.canonical_name != odn_identity.canonical_name


def test_empty_or_sin_zona_returns_none():
    normalizer = TerritorialNormalizer()

    assert normalizer.normalize_territorial_object("", olt_id=3) is None
    assert normalizer.normalize_territorial_object("   ", olt_id=3) is None
    assert normalizer.normalize_territorial_object("SIN_ZONA", olt_id=3) is None

    # Para zonas, el mismo criterio aplica.
    assert normalizer.normalize_zone("", olt_id=3) is None
    assert normalizer.normalize_zone("SIN_ZONA", olt_id=3) is None
