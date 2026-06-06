"""Tests for M10: Data Workbench ingestion policy, artifact manifest, redaction."""
import json
import os

import pytest

from data_workbench.manifest import (
    ArtifactManifest,
    count_manifests,
    load_manifests,
    reset_manifests,
    save_manifest,
)
from data_workbench.policy import (
    ACCEPTED_EXTENSIONS,
    DEFAULT_RETENTION_DAYS,
    MAX_DATASET_BYTES,
    ArtifactKind,
    PrivacyClass,
    is_accepted_file_type,
    is_sensitive_schema_key,
    is_within_size_limit,
    normalize_artifact_path,
    redact_schema_key_list,
    redact_schema_keys,
    redact_text_body,
    validate_retention_days,
)


@pytest.fixture(autouse=True)
def isolated_manifest_store(tmp_path, monkeypatch):
    monkeypatch.setenv("LIMA_ARTIFACT_MANIFEST", str(tmp_path / "manifests.jsonl"))
    monkeypatch.setenv("LIMA_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    reset_manifests()
    yield
    reset_manifests()


# File type policy

def test_accepted_extensions():
    assert ".csv" in ACCEPTED_EXTENSIONS
    assert ".json" in ACCEPTED_EXTENSIONS
    assert ".jsonl" in ACCEPTED_EXTENSIONS
    assert ".md" in ACCEPTED_EXTENSIONS
    assert ".txt" in ACCEPTED_EXTENSIONS


def test_is_accepted_file_type():
    assert is_accepted_file_type("data.csv") is True
    assert is_accepted_file_type("report.json") is True
    assert is_accepted_file_type("notes.md") is True
    assert is_accepted_file_type("script.py") is False
    assert is_accepted_file_type("image.png") is False
    assert is_accepted_file_type("binary.exe") is False


def test_is_within_size_limit():
    assert is_within_size_limit(1000) is True
    assert is_within_size_limit(MAX_DATASET_BYTES) is True
    assert is_within_size_limit(MAX_DATASET_BYTES + 1) is False
    assert is_within_size_limit(0) is False
    assert is_within_size_limit(-1) is False


def test_validate_retention_days():
    assert validate_retention_days(30) == 30
    assert validate_retention_days(0) == 1    # clamped to min
    assert validate_retention_days(500) == 365  # clamped to max
    assert validate_retention_days(-5) == 1


# Schema redaction

def test_is_sensitive_schema_key():
    assert is_sensitive_schema_key("api_key") is True
    assert is_sensitive_schema_key("API_KEY") is True
    assert is_sensitive_schema_key("password") is True
    assert is_sensitive_schema_key("token") is True
    assert is_sensitive_schema_key("name") is False
    assert is_sensitive_schema_key("description") is False


def test_redact_schema_keys():
    schema = {"name": "test", "api_key": "sk-secret", "count": 42}
    redacted = redact_schema_keys(schema)
    assert redacted["name"] == "test"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["count"] == 42


def test_redact_schema_key_list():
    redacted = redact_schema_key_list(["name", "api_key", "token_value"])
    assert redacted == ["name", "[REDACTED]", "[REDACTED]"]


def test_redact_text_body():
    text = "Using api key: sk-abcdefghij12345678901234567890 for auth"
    result = redact_text_body(text)
    assert "sk-abcdefghij" not in result


# ArtifactManifest

def test_manifest_defaults():
    m = ArtifactManifest(
        artifact_id="test-1",
        kind=ArtifactKind.DATASET,
        title="Test Dataset",
    )
    assert m.artifact_id == "test-1"
    assert m.kind == ArtifactKind.DATASET
    assert m.privacy_class == PrivacyClass.INTERNAL
    assert m.retention_days == 30
    assert m.expires_at > 0
    assert m.is_expired is False


def test_manifest_auto_id():
    m = ArtifactManifest(artifact_id="", kind=ArtifactKind.REFERENCE)
    assert m.artifact_id.startswith("artifact-")
    assert len(m.artifact_id) == 21  # "artifact-" + 12 hex


def test_manifest_to_dict_and_json():
    m = ArtifactManifest(
        artifact_id="test-2", kind=ArtifactKind.SUMMARY,
        title="Analysis Result", source_url="https://example.com/data.csv",
        evidence_refs=["ref-1", "ref-2"],
        privacy_class=PrivacyClass.PUBLIC, tags=["analysis"],
    )
    d = m.to_dict()
    assert d["artifact_id"] == "test-2"
    assert d["kind"] == "summary"
    assert d["privacy_class"] == "public"

    j = m.to_json()
    parsed = json.loads(j)
    assert parsed["title"] == "Analysis Result"


def test_manifest_redacts_summary():
    m = ArtifactManifest(
        artifact_id="test-3", kind=ArtifactKind.REFERENCE,
        summary="Used token: sk-secret-key-1234567890abcdef",
    )
    assert "sk-secret-key" not in m.summary


def test_manifest_redacts_metadata_fields():
    m = ArtifactManifest(
        artifact_id="secret-fields",
        kind=ArtifactKind.REFERENCE,
        title="token=Bearer abcdefghijklmnopqrstuvwxyz123456",
        source_url="https://example.com/?api_key=sk-abcdefghij12345678901234567890",
        evidence_refs=["sk-abcdefghij12345678901234567890"],
        schema_keys=["name", "api_key"],
        generated_by="Bearer abcdefghijklmnopqrstuvwxyz123456",
    )
    text = m.to_json()
    assert "Bearer abcdefghijklmnopqrstuvwxyz123456" not in text
    assert "sk-abcdefghij12345678901234567890" not in text
    assert "[REDACTED]" in text


def test_manifest_rejects_file_path_escape(tmp_path):
    outside = tmp_path / "outside.txt"
    m = ArtifactManifest(
        artifact_id="escape",
        kind=ArtifactKind.DATASET,
        file_path=str(outside),
    )
    assert m.file_path == ""


def test_manifest_accepts_relative_file_path_under_artifact_root(tmp_path):
    m = ArtifactManifest(
        artifact_id="inside",
        kind=ArtifactKind.DATASET,
        file_path="datasets/data.csv",
    )
    assert m.file_path.endswith(os.path.join("datasets", "data.csv"))
    assert normalize_artifact_path(m.file_path) == m.file_path


def test_manifest_is_expired():
    import time
    m = ArtifactManifest(
        artifact_id="expired", kind=ArtifactKind.REFERENCE,
        retrieval_date=time.time() - 999999, retention_days=1,
    )
    assert m.is_expired is True


def test_manifest_schema_keys_capped():
    m = ArtifactManifest(
        artifact_id="test", kind=ArtifactKind.DATASET,
        schema_keys=[f"col_{i}" for i in range(100)],
    )
    assert len(m.schema_keys) <= 50


# Manifest store

def test_save_and_load_manifest():
    reset_manifests()
    m = ArtifactManifest(
        artifact_id="store-test", kind=ArtifactKind.DATASET, title="Stored Dataset",
    )
    assert save_manifest(m) is True

    loaded = load_manifests(limit=10)
    assert len(loaded) == 1
    assert loaded[0].artifact_id == "store-test"


def test_load_manifests_filter_by_kind():
    reset_manifests()
    save_manifest(ArtifactManifest(artifact_id="d1", kind=ArtifactKind.DATASET))
    save_manifest(ArtifactManifest(artifact_id="s1", kind=ArtifactKind.SUMMARY))

    datasets = load_manifests(kind="dataset", limit=10)
    assert len(datasets) == 1
    assert datasets[0].artifact_id == "d1"


def test_count_manifests():
    reset_manifests()
    for i in range(3):
        save_manifest(ArtifactManifest(artifact_id=f"c{i}", kind=ArtifactKind.REFERENCE))
    assert count_manifests() == 3


def test_load_manifests_respects_limit():
    reset_manifests()
    for i in range(10):
        save_manifest(ArtifactManifest(artifact_id=f"l{i}", kind=ArtifactKind.REFERENCE))
    assert len(load_manifests(limit=3)) == 3


def test_manifest_store_no_secrets_in_file():
    reset_manifests()
    m = ArtifactManifest(
        artifact_id="secret-test", kind=ArtifactKind.REFERENCE,
        summary="key=sk-abcdefghij12345678901234567890",
    )
    save_manifest(m)
    path = os.environ.get("LIMA_ARTIFACT_MANIFEST", "")
    if path and os.path.exists(path):
        content = open(path).read()
        assert "sk-abcdefghij" not in content


def test_manifest_store_uses_runtime_env_path(tmp_path, monkeypatch):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    monkeypatch.setenv("LIMA_ARTIFACT_MANIFEST", str(first))
    save_manifest(ArtifactManifest(artifact_id="first", kind=ArtifactKind.REFERENCE))
    monkeypatch.setenv("LIMA_ARTIFACT_MANIFEST", str(second))
    save_manifest(ArtifactManifest(artifact_id="second", kind=ArtifactKind.REFERENCE))
    assert first.exists()
    assert second.exists()
    assert "first" in first.read_text(encoding="utf-8")
    assert "second" in second.read_text(encoding="utf-8")


# PrivacyClass enum

def test_privacy_class_values():
    assert PrivacyClass.PUBLIC == "public"
    assert PrivacyClass.RESTRICTED == "restricted"
    assert len(PrivacyClass) == 4


def test_artifact_kind_values():
    assert ArtifactKind.DATASET == "dataset"
    assert ArtifactKind.GENERATED_CODE == "generated_code"
    assert len(ArtifactKind) == 5
