#!/usr/bin/env python3
"""Push JDCloud probe results to the LiMa main VPS ingress endpoint.

The script prefers ``stability.json`` (health/latency data produced by the
existing JDCloud probe runtime). When that file is absent, it falls back to
``known_providers.json`` and reports each provider with status ``"unknown"``.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

# Allow same-directory imports when this script is copied standalone.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from push_probe_results_utils import _load_json, _load_jsonl, _sanitize_metadata


def _find_discovery(url: str, discoveries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the first discovery entry whose url matches *url*."""
    for discovery in discoveries:
        if isinstance(discovery, dict) and discovery.get("url") == url:
            return discovery
    return None


def _derive_provider(url_or_key: str) -> str:
    """Derive a provider identifier from a URL or raw key."""
    if not url_or_key:
        return "unknown"
    if url_or_key.startswith(("http://", "https://")):
        return url_or_key.split("//", 1)[1].rstrip("/")
    return url_or_key


def _compute_status(entry: dict[str, Any]) -> str:
    """Determine alive/dead/unknown from success/failure timestamps."""
    last_success = entry.get("last_success")
    last_failure = entry.get("last_failure")
    if last_success and last_failure:
        return "alive" if last_success > last_failure else "dead"
    if last_success:
        return "alive"
    if last_failure:
        return "dead"
    return "unknown"


def _compute_latency(entry: dict[str, Any]) -> float:
    """Average the last up to 20 latency samples.

    Returns ``-1.0`` when no latency samples are available.
    """
    latencies = entry.get("latencies", [])
    if not isinstance(latencies, list) or not latencies:
        return -1.0
    samples = latencies[-20:]
    numeric = [float(x) for x in samples if isinstance(x, (int, float))]
    if not numeric:
        return -1.0
    return round(sum(numeric) / len(numeric), 3)


def _build_probe(
    provider_id: str,
    entry: dict[str, Any],
    discoveries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a single probe event from a stability entry."""
    url = entry.get("url") or ""
    provider = provider_id if provider_id else _derive_provider(url)
    status = _compute_status(entry)
    latency_ms = _compute_latency(entry)
    discovery = _find_discovery(url, discoveries) if url else None
    discovery = discovery or {}
    price_tier = "free" if discovery.get("is_free") else ""

    checks = entry.get("checks", 0)
    successes = entry.get("successes", 0)
    uptime_pct = round(successes / checks * 100, 2) if checks else 0.0

    checked_at = ""
    if status == "alive":
        checked_at = entry.get("last_success", "")
    elif status == "dead":
        checked_at = entry.get("last_failure", "")

    metadata = _sanitize_metadata(
        {
            "url": url,
            "source": discovery.get("source") or "stability",
            "name": discovery.get("name", ""),
            "uptime_pct": uptime_pct,
            "checks": checks,
            "successes": successes,
            "mentioned_models": discovery.get("mentioned_models", []),
        }
    )

    return {
        "provider": provider,
        "status": status,
        "latency_ms": latency_ms,
        "price_tier": price_tier,
        "checked_at": checked_at,
        "metadata": metadata,
    }


def _build_probes_from_stability(
    stability: dict[str, Any],
    discoveries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build probe events for every provider in stability.json."""
    probes: list[dict[str, Any]] = []
    for provider_id, entry in stability.items():
        if not isinstance(entry, dict):
            logging.warning("skipping non-object stability entry for %s", provider_id)
            continue
        probes.append(_build_probe(provider_id, entry, discoveries))
    return probes


def _build_probes_from_known(
    known: dict[str, Any],
    stability: dict[str, Any],
    discoveries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build probe events for known providers absent from stability.json."""
    probes: list[dict[str, Any]] = []
    seen_urls = {entry.get("url") for entry in stability.values() if isinstance(entry, dict)}
    for url in known.get("urls", []):
        if not isinstance(url, str) or url in seen_urls:
            continue
        discovery = _find_discovery(url, discoveries) or {}
        probes.append(
            {
                "provider": _derive_provider(url),
                "status": "unknown",
                "latency_ms": -1.0,  # no latency samples available for known-only providers
                "price_tier": "free" if discovery.get("is_free") else "",
                "checked_at": "",
                "metadata": _sanitize_metadata(
                    {
                        "url": url,
                        "source": discovery.get("source") or "known_providers",
                        "name": discovery.get("name", ""),
                        "mentioned_models": discovery.get("mentioned_models", []),
                    }
                ),
            }
        )
    return probes


def _build_payload(data_dir: Path) -> dict[str, Any]:
    """Assemble the ingress payload from local probe data files.

    ``stability.json`` is optional; when it is missing or empty the payload is
    built solely from ``known_providers.json`` with status ``"unknown"``.
    """
    known = _load_json(data_dir / "known_providers.json") or {}
    stability = _load_json(data_dir / "stability.json") or {}
    discoveries = _load_jsonl(data_dir / "discoveries.jsonl")

    if not isinstance(known, dict):
        known = {}
    if not isinstance(stability, dict):
        stability = {}

    probes: list[dict[str, Any]] = []
    probes.extend(_build_probes_from_stability(stability, discoveries))
    probes.extend(_build_probes_from_known(known, stability, discoveries))
    return {"source": "jdcloud", "probes": probes}


def _post_payload(
    payload: dict[str, Any],
    ingress_url: str,
    token: str,
    timeout: int,
) -> None:
    """POST the payload to the ingress endpoint; log outcome."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        ingress_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": os.environ.get("PROBE_INGRESS_USER_AGENT", "LiMa-Probe-Push/1.0"),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            try:
                result = json.loads(body)
            except json.JSONDecodeError:
                result = {"raw": body}
            logging.info(
                "probe push: status=%s recorded=%s",
                response.status,
                result.get("recorded", "unknown"),
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logging.warning("probe push failed: HTTP %s: %s", exc.code, body)
    except urllib.error.URLError as exc:
        logging.warning("probe push failed: %s", exc.reason)
    except TimeoutError:
        logging.warning("probe push failed: timeout after %ss", timeout)
    except OSError as exc:
        logging.warning("probe push failed: %s", exc)


def main() -> int:
    """Entry point."""
    token = os.environ.get("LIMA_PROBE_INGRESS_TOKEN")
    if not token:
        logging.error("LIMA_PROBE_INGRESS_TOKEN is not set; exiting without push")
        return 0

    data_dir = Path(os.environ.get("PROBE_DATA_DIR", "/opt/lima-probe/data"))
    ingress_url = os.environ.get(
        "LIMA_PROBE_INGRESS_URL",
        "https://chat.donglicao.com/admin/api/probe/ingress",
    )
    try:
        timeout = int(os.environ.get("PROBE_INGRESS_TIMEOUT", "30"))
    except ValueError:
        logging.error("PROBE_INGRESS_TIMEOUT is not a valid integer")
        return 0

    payload = _build_payload(data_dir)
    if not payload["probes"]:
        logging.info("no probe data found; nothing to push")
        return 0

    _post_payload(payload, ingress_url, token, timeout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
