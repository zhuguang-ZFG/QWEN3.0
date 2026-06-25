#!/usr/bin/env python3
"""Deploy LiMa probe platform and monitoring stack on JDCloud nodes."""

from __future__ import annotations

import subprocess
from pathlib import Path

PROMETHEUS_VERSION = "2.52.0"
PROMETHEUS_TARBALL = "prometheus-2.52.0.linux-amd64.tar.gz"
PROMETHEUS_URL = "https://github.com/prometheus/prometheus/releases/download/v2.52.0/prometheus-2.52.0.linux-amd64.tar.gz"
PROMETHEUS_SHA256 = "7f31c5d6474bbff3e514e627e0b7a7fbbd4e5cea3f315fd0b76cad50be4c1ba3"
INSTALL_DIR = Path("/opt/lima-monitor")


def _run(cmd: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, shell=True, check=check, text=True, capture_output=True)


def install_prometheus() -> None:
    """Download, verify and install Prometheus server."""
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    tarball_path = INSTALL_DIR / "prometheus.tar.gz"

    _run(f"wget -q {PROMETHEUS_URL} -O {tarball_path}")

    checksum_file = INSTALL_DIR / "prometheus.sha256"
    checksum_file.write_text(
        "7f31c5d6474bbff3e514e627e0b7a7fbbd4e5cea3f315fd0b76cad50be4c1ba3  prometheus.tar.gz\n",
        encoding="utf-8",
    )
    _run("sha256sum -c prometheus.sha256", cwd=INSTALL_DIR)

    _run(f"tar -xzf {tarball_path} -C {INSTALL_DIR}")
    extracted = INSTALL_DIR / f"prometheus-{PROMETHEUS_VERSION}.linux-amd64"
    _run(f"ln -sfn {extracted} {INSTALL_DIR / 'prometheus'}")
    _run(f"rm -f {tarball_path} {checksum_file}")


if __name__ == "__main__":
    install_prometheus()
