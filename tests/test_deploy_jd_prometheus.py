"""Regression tests for deploy/jdcloud/deploy_jd.py Prometheus deployment."""

from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = PROJECT_ROOT / "deploy" / "jdcloud" / "deploy_jd.py"


def _script_text() -> str:
    return DEPLOY_SCRIPT.read_text(encoding="utf-8")


def test_prometheus_download_uses_https():
    text = _script_text()
    urls = re.findall(r"https?://[^\s\"']+", text)
    prometheus_urls = [u for u in urls if "prometheus" in u and u.endswith(".tar.gz")]
    assert prometheus_urls, "no Prometheus download URL found"
    assert all(u.startswith("https://") for u in prometheus_urls), prometheus_urls


def test_prometheus_archive_has_sha256_verification():
    text = _script_text()
    assert "sha256sum -c prometheus.sha256" in text
    # Ensure a pinned SHA256 hash (64 hex chars) exists for the downloaded archive.
    hashes = re.findall(r"[\"']?([0-9a-f]{64})\s+prometheus\.tar\.gz[\"']?", text)
    assert hashes, "expected a pinned 64-character SHA256 hash for prometheus.tar.gz"
