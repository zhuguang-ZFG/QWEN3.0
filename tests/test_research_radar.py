"""Tests for M15 research radar source records and catalog."""

import pytest

from research_radar.catalog import SourceCatalog, build_default_catalog
from research_radar.source import (
    AdoptionState,
    LicenseClass,
    SourceRecord,
)


def test_source_record_to_dict():
    source = SourceRecord(
        source_id="ref-test",
        name="Test Project",
        url="https://example.com",
        description="A test project",
        tags=["test", "example"],
        license_class=LicenseClass.MIT,
        adoption_state=AdoptionState.REFERENCE,
        subsystem="testing",
        notes="test notes",
        added_at="2026-01-01",
    )

    data = source.to_dict()

    assert data["source_id"] == "ref-test"
    assert data["license_class"] == "MIT"
    assert data["adoption_state"] == "reference"
    assert "test" in data["tags"]


def test_source_record_from_dict_round_trip_and_unknown_enums():
    source = SourceRecord.from_dict({
        "source_id": "ref-test",
        "name": "Test",
        "license_class": "not-real",
        "adoption_state": "not-real",
        "tags": ["RAG"],
        "evidence_refs": ["doc"],
    })

    assert source.license_class is LicenseClass.UNKNOWN
    assert source.adoption_state is AdoptionState.REFERENCE
    assert source.to_dict()["tags"] == ["RAG"]


def test_source_record_redacts_secret_like_fields():
    source = SourceRecord(
        source_id="ref-safe",
        name="Test",
        url="https://example.com?token=secret",
        notes="Bearer should not leak",
        evidence_refs=["sk-secret"],
    )
    data = source.to_dict()

    assert data["url"] == "[REDACTED]"
    assert data["notes"] == "[REDACTED]"
    assert data["evidence_refs"] == ["[REDACTED]"]


def test_source_record_requires_identity_fields():
    with pytest.raises(ValueError, match="source_id"):
        SourceRecord(source_id="", name="Name")
    with pytest.raises(ValueError, match="name"):
        SourceRecord(source_id="ref", name="")


def test_source_record_defaults():
    source = SourceRecord(source_id="minimal", name="Minimal")

    assert source.license_class == LicenseClass.UNKNOWN
    assert source.adoption_state == AdoptionState.REFERENCE
    assert source.tags == []


def test_adoption_state_values():
    assert AdoptionState.CONCEPT_ONLY == "concept_only"
    assert AdoptionState.ADOPTED == "adopted"
    assert AdoptionState.REJECTED == "rejected"


def test_license_class_values():
    assert LicenseClass.MIT == "MIT"
    assert LicenseClass.AGPL == "AGPL"
    assert LicenseClass.UNKNOWN == "unknown"


def test_copy_restricted_license_policy():
    assert SourceRecord(
        source_id="mit",
        name="MIT",
        license_class=LicenseClass.MIT,
    ).allows_code_copy
    assert not SourceRecord(
        source_id="agpl",
        name="AGPL",
        license_class=LicenseClass.AGPL,
    ).allows_code_copy
    assert not SourceRecord(source_id="unknown", name="Unknown").allows_code_copy


def test_catalog_register_and_get():
    catalog = SourceCatalog()
    source = SourceRecord(source_id="r1", name="Test", subsystem="testing")
    catalog.register(source)

    assert catalog.get("r1") is source
    assert catalog.get("nonexistent") is None


def test_catalog_rejects_duplicate_source_ids():
    catalog = SourceCatalog()
    catalog.register(SourceRecord(source_id="r1", name="A"))

    with pytest.raises(ValueError, match="duplicate"):
        catalog.register(SourceRecord(source_id="r1", name="B"))


def test_catalog_length():
    catalog = SourceCatalog()
    assert len(catalog) == 0
    catalog.register(SourceRecord(source_id="a", name="A"))
    catalog.register(SourceRecord(source_id="b", name="B"))
    assert len(catalog) == 2


def test_catalog_search():
    catalog = SourceCatalog()
    catalog.register(SourceRecord(
        source_id="r1",
        name="LightRAG",
        description="Graph RAG retrieval",
        tags=["rag", "graph"],
        subsystem="context_pipeline",
    ))
    catalog.register(SourceRecord(
        source_id="r2",
        name="Mem0",
        description="Memory layer",
        tags=["memory"],
        subsystem="session_memory",
    ))

    results = catalog.search("graph rag")

    assert len(results) >= 1
    assert results[0].source_id == "r1"


def test_catalog_search_no_match():
    catalog = SourceCatalog()
    catalog.register(SourceRecord(source_id="r1", name="Test"))

    assert catalog.search("nonexistent_query") == []


def test_catalog_search_empty_or_zero_limit():
    catalog = SourceCatalog()
    catalog.register(SourceRecord(source_id="r1", name="Test"))

    assert catalog.search("") == []
    assert catalog.search("test", limit=0) == []


def test_catalog_filter_by_subsystem():
    catalog = SourceCatalog()
    catalog.register(SourceRecord(source_id="a", name="A", subsystem="ctx"))
    catalog.register(SourceRecord(source_id="b", name="B", subsystem="mem"))

    results = catalog.filter_by_subsystem("ctx")

    assert len(results) == 1
    assert results[0].source_id == "a"


def test_catalog_filter_by_adoption():
    catalog = SourceCatalog()
    catalog.register(SourceRecord(
        source_id="a",
        name="A",
        adoption_state=AdoptionState.ADOPTED,
    ))
    catalog.register(SourceRecord(
        source_id="b",
        name="B",
        adoption_state=AdoptionState.CONCEPT_ONLY,
    ))

    results = catalog.filter_by_adoption(AdoptionState.ADOPTED)

    assert len(results) == 1
    assert results[0].name == "A"


def test_catalog_filter_by_license():
    catalog = SourceCatalog()
    catalog.register(SourceRecord(
        source_id="mit",
        name="MIT Project",
        license_class=LicenseClass.MIT,
    ))
    catalog.register(SourceRecord(
        source_id="agpl",
        name="AGPL Project",
        license_class=LicenseClass.AGPL,
    ))

    results = catalog.filter_by_license(LicenseClass.AGPL)

    assert len(results) == 1
    assert results[0].source_id == "agpl"


def test_catalog_filter_by_tag_is_case_insensitive():
    catalog = SourceCatalog()
    catalog.register(SourceRecord(source_id="a", name="A", tags=["RAG", "graph"]))
    catalog.register(SourceRecord(source_id="b", name="B", tags=["memory"]))

    assert len(catalog.filter_by_tag("rag")) == 1
    assert len(catalog.filter_by_tag("memory")) == 1
    assert len(catalog.filter_by_tag("nonexistent")) == 0


def test_catalog_count_by_subsystem():
    catalog = SourceCatalog()
    catalog.register(SourceRecord(source_id="a", name="A", subsystem="ctx"))
    catalog.register(SourceRecord(source_id="b", name="B", subsystem="ctx"))
    catalog.register(SourceRecord(source_id="c", name="C", subsystem="mem"))

    counts = catalog.count_by_subsystem()

    assert counts["ctx"] == 2
    assert counts["mem"] == 1


def test_catalog_count_by_adoption():
    catalog = SourceCatalog()
    catalog.register(SourceRecord(
        source_id="a",
        name="A",
        adoption_state=AdoptionState.ADOPTED,
    ))
    catalog.register(SourceRecord(
        source_id="b",
        name="B",
        adoption_state=AdoptionState.REFERENCE,
    ))

    counts = catalog.count_by_adoption()

    assert counts["adopted"] == 1
    assert counts["reference"] == 1


def test_build_default_catalog():
    catalog = build_default_catalog()

    assert len(catalog) >= 10
    assert catalog.get("ref-lightrag") is not None
    assert catalog.get("ref-aider") is not None
    assert catalog.get("ref-shadowbroker") is not None


def test_default_catalog_search():
    catalog = build_default_catalog()

    results = catalog.search("rag retrieval")

    assert len(results) >= 1
    assert any("LightRAG" in source.name for source in results)


def test_default_catalog_subsystem_filter():
    catalog = build_default_catalog()

    ctx_sources = catalog.filter_by_subsystem("context_pipeline")

    assert len(ctx_sources) >= 2


def test_default_catalog_no_agpl_adopted():
    catalog = build_default_catalog()
    agpl_sources = catalog.filter_by_license(LicenseClass.AGPL)

    for source in agpl_sources:
        assert source.adoption_state != AdoptionState.ADOPTED
        assert not source.allows_code_copy


def test_default_catalog_known_reference_metadata_is_specific():
    catalog = build_default_catalog()
    shadowbroker = catalog.get("ref-shadowbroker")
    last30days = catalog.get("ref-last30days")
    leann = catalog.get("ref-leann")

    assert shadowbroker.license_class is LicenseClass.AGPL
    assert shadowbroker.adoption_state is AdoptionState.CONCEPT_ONLY
    assert "BigBodyCobain/Shadowbroker" in shadowbroker.url
    assert "mvanhorn/last30days-skill" in last30days.url
    assert leann.license_class is LicenseClass.MIT
    assert "yichuan-w/LEANN" in leann.url
