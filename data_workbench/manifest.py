"""Artifact manifest typed schema for research artifact tracking.

Each artifact has a manifest record with provenance, privacy classification,
retention policy, and evidence references. Stored as JSON for portability.
"""
from __future__ import annotations


import logging

_log = logging.getLogger(__name__)
import json
import os
import time
from dataclasses import asdict, dataclass, field

from data_workbench.policy import (
    ArtifactKind, PrivacyClass,
    DEFAULT_RETENTION_DAYS, validate_retention_days,
    normalize_artifact_path, redact_schema_key_list, redact_text_body,
)


@dataclass
class ArtifactManifest:
    artifact_id: str
    kind: ArtifactKind
    source_url: str = ""
    retrieval_date: float = field(default_factory=time.time)
    title: str = ""
    summary: str = ""
    file_path: str = ""          # local path to stored artifact
    file_size_bytes: int = 0
    evidence_refs: list[str] = field(default_factory=list)
    privacy_class: PrivacyClass = PrivacyClass.INTERNAL
    retention_days: int = DEFAULT_RETENTION_DAYS
    expires_at: float = 0.0
    tags: list[str] = field(default_factory=list)
    schema_keys: list[str] = field(default_factory=list)  # redacted
    generated_by: str = ""       # worker_id or "manual"

    def __post_init__(self) -> None:
        if not self.artifact_id:
            self.artifact_id = _make_artifact_id()
        if self.retention_days != DEFAULT_RETENTION_DAYS:
            self.retention_days = validate_retention_days(self.retention_days)
        if self.expires_at <= 0:
            self.expires_at = self.retrieval_date + (self.retention_days * 86400)
        self.source_url = redact_text_body(self.source_url)
        self.title = redact_text_body(self.title)
        self.summary = redact_text_body(self.summary)
        self.file_path = normalize_artifact_path(self.file_path)
        self.evidence_refs = [
            redact_text_body(ref) for ref in self.evidence_refs if ref
        ][:100]
        self.tags = [redact_text_body(tag) for tag in self.tags if tag][:50]
        self.schema_keys = [
            key for key in redact_schema_key_list(self.schema_keys) if len(key) < 200
        ][:50]
        self.generated_by = redact_text_body(self.generated_by)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["kind"] = self.kind.value
        d["privacy_class"] = self.privacy_class.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


def _make_artifact_id() -> str:
    import uuid
    return f"artifact-{uuid.uuid4().hex[:12]}"


# Manifest store (local JSON)

_DEFAULT_STORE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)


def _store_path() -> str:
    return os.environ.get("LIMA_ARTIFACT_MANIFEST") or os.path.join(
        _DEFAULT_STORE_DIR, "artifact_manifests.jsonl"
    )


def save_manifest(manifest: ArtifactManifest) -> bool:
    try:
        store_path = _store_path()
        store_dir = os.path.dirname(store_path)
        os.makedirs(store_dir, exist_ok=True)
        with open(store_path, "a", encoding="utf-8") as f:
            f.write(manifest.to_json() + "\n")
        return True
    except OSError:
        return False


def load_manifests(limit: int = 100, kind: str = "") -> list[ArtifactManifest]:
    store_path = _store_path()
    if not os.path.exists(store_path):
        return []
    results = []
    with open(store_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                if kind and d.get("kind") != kind:
                    continue
                d["kind"] = ArtifactKind(d.get("kind", "reference"))
                d["privacy_class"] = PrivacyClass(d.get("privacy_class", "internal"))
                results.append(ArtifactManifest(**d))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            if len(results) >= limit:
                break
    return results


def count_manifests(kind: str = "") -> int:
    return len(load_manifests(limit=10000, kind=kind))


def reset_manifests() -> None:
    try:
        os.remove(_store_path())
    except OSError:
        _log.debug("manifest: optional dependency or operation failed", exc_info=True)