"""Deploy / VPS / JDCloud environment configuration (P1-2 phase 3).

Used by scripts under ``scripts/`` and ``deploy/`` so they do not repeat
``os.environ.get()`` calls. Values that need to react to runtime env changes
are exposed as functions; stable defaults are module-level constants.
"""

from __future__ import annotations

import os


LIMA_SERVER: str = "47.112.162.80"
REMOTE_PATH: str = "/opt/lima-router"
JDCLOUD_REMOTE_PROBE_PATH: str = "/opt/lima-probe"

DEPLOY_KEY_PATH: str = os.environ.get("LIMA_DEPLOY_KEY_PATH", "~/.ssh/id_ed25519")

JDCLOUD_SERVER: str = (
    os.environ.get("LIMA_JDCLOUD_SERVER") or os.environ.get("JDCLOUD_HOST") or "117.72.118.95"
)
JDCLOUD_USER: str = os.environ.get("JDCLOUD_USER", "root")
JDCLOUD_ROOT_PASSWORD: str = os.environ.get("LIMA_JDCLOUD_ROOT_PASSWORD", "")

ALIYUN_SERVER: str = os.environ.get("LIMA_ALIYUN_SERVER", "47.112.162.80")
ALIYUN_PASSWORD: str = os.environ.get("LIMA_ALIYUN_PASSWORD", "")

JDCLOUD_REDIS_PORT: int = int(os.environ.get("LIMA_JDCLOUD_REDIS_PORT", "6379"))
JDCLOUD_REDIS_PASSWORD: str = os.environ.get("LIMA_JDCLOUD_REDIS_PASSWORD", "")

VERIFY_HOST: str = os.environ.get("LIMA_VERIFY_HOST", "chat.donglicao.com").strip()


def deploy_known_hosts() -> str | None:
    return os.environ.get("LIMA_DEPLOY_KNOWN_HOSTS")


def expanded_key_path() -> str:
    return os.path.expanduser(DEPLOY_KEY_PATH)


def expanded_known_hosts() -> str:
    return os.path.expanduser(deploy_known_hosts() or "~/.ssh/known_hosts")


def deploy_min_free_mb() -> int:
    raw = os.environ.get("LIMA_DEPLOY_MIN_FREE_MB", "512")
    try:
        return int(raw or "512")
    except ValueError:
        return 512


def deploy_min_mem_mb() -> int:
    raw = os.environ.get("LIMA_DEPLOY_MIN_MEM_MB", "128")
    try:
        return int(raw or "128")
    except ValueError:
        return 128


def deploy_health_wait_s() -> int:
    raw = os.environ.get("LIMA_DEPLOY_HEALTH_WAIT_S", "120")
    try:
        return int(raw or "120")
    except ValueError:
        return 120


def deploy_health_grace_s() -> int:
    raw = os.environ.get("LIMA_DEPLOY_HEALTH_GRACE_S", "30")
    try:
        return int(raw or "30")
    except ValueError:
        return 30


def deploy_use_tar() -> bool:
    return os.environ.get("LIMA_DEPLOY_USE_TAR", "").strip().lower() in {"1", "true", "yes"}


def deploy_use_rsync() -> bool:
    return os.environ.get("LIMA_DEPLOY_USE_RSYNC", "").strip().lower() in {"1", "true", "yes"}


def deploy_pass() -> str:
    return os.environ.get("LIMA_DEPLOY_PASS", "")


def deploy_host() -> str:
    return os.environ.get("LIMA_DEPLOY_HOST", "root@47.112.162.80")


def router_root() -> str:
    return os.environ.get("LIMA_ROUTER_ROOT", "/opt/lima-router")


def deploy_notify_enabled() -> bool:
    return os.environ.get("LIMA_DEPLOY_NOTIFY", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def jdcloud_password() -> str:
    return (
        os.environ.get("LIMA_JDCLOUD_ROOT_PASSWORD", "")
        or os.environ.get("JDCLOUD_SSH_PASSWORD", "")
        or os.environ.get("LIMA_DEPLOY_PASS", "")
    )
