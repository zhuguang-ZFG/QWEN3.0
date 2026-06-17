"""Deployment inventory for LiMa VPS operations.

This module keeps deployment topology, rollback steps, and smoke commands as
small typed data. It is intentionally descriptive: it does not execute remote
commands, restart services, or read credentials.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ServiceEntry:
    name: str
    port: int
    description: str
    systemd_unit: str = ""
    health_path: str = "/health"
    protocol: str = "http"


@dataclass
class DeploymentInventory:
    services: list[ServiceEntry] = field(default_factory=list)
    backup_dir: str = "/opt/lima-router/backups"
    deploy_user: str = "root"
    deploy_host: str = "47.112.162.80"
    remote_path: str = "/opt/lima-router"
    systemd_service: str = "lima-router"
    restart_command: str = "systemctl restart lima-router"
    rollback_steps: list[str] = field(default_factory=list)
    smoke_commands: list[str] = field(default_factory=list)


def build_inventory() -> DeploymentInventory:
    return DeploymentInventory(
        services=[
            ServiceEntry(
                name="lima-router",
                port=8080,
                protocol="http",
                description="LiMa main API server",
                systemd_unit="lima-router.service",
            ),
            ServiceEntry(
                name="lima-voice",
                port=8091,
                protocol="http",
                description="Voice gateway",
                systemd_unit="lima-voice.service",
            ),
            ServiceEntry(
                name="nginx-https",
                port=443,
                protocol="https",
                description="nginx HTTPS edge for chat.donglicao.com",
            ),
            ServiceEntry(
                name="nginx-frp",
                port=8088,
                protocol="http",
                description="FRP tunnel to Windows local router",
            ),
            ServiceEntry(
                name="new-api",
                port=3003,
                protocol="http",
                description="New API gateway on localhost",
            ),
        ],
        backup_dir="/opt/lima-router/backups",
        smoke_commands=[
            "curl -s https://chat.donglicao.com/health",
            "curl -s http://47.112.162.80:8088/health",
            "curl -s -H 'Authorization: Bearer $LIMA_API_KEY' "
            "-H 'Content-Type: application/json' "
            "https://chat.donglicao.com/v1/chat/completions "
            '-d \'{"model":"lima-1.3","messages":[{"role":"user","content":"hi"}]}\'',
        ],
        rollback_steps=[
            "ls /opt/lima-router/backups/  # list available backups",
            "cp -r /opt/lima-router/backups/<date>/* /opt/lima-router/",
            "systemctl restart lima-router",
            "curl -s https://chat.donglicao.com/health",
        ],
    )


def format_inventory_markdown(inv: DeploymentInventory) -> str:
    lines = [
        "## LiMa Deployment Inventory",
        "",
        "| Service | Port | Protocol | Health |",
        "|---------|------|----------|--------|",
    ]
    for service in inv.services:
        health = f"{service.protocol}://localhost:{service.port}{service.health_path}"
        lines.append(f"| {service.name} | {service.port} | {service.protocol} | {health} |")

    lines += [
        "",
        "### Rollback",
        *[f"  {index + 1}. {step}" for index, step in enumerate(inv.rollback_steps)],
        "",
        "### Smoke Commands",
        *[f"  - `{command}`" for command in inv.smoke_commands],
    ]
    return "\n".join(lines)
