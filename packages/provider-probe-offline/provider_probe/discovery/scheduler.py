"""Unified discovery scheduler: orchestrates all discovery sources.

Runs periodically (via cron/systemd timer) to coordinate GitHub monitoring,
web search, Chinese platform scraping, and browser-based probing.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

from provider_probe import config as probe_config

from . import browser_probe, chinese_platforms, github_monitor, web_search

logger = logging.getLogger(__name__)

OUTPUT_DIR = probe_config.OUTPUT_DIR
KNOWN_PROVIDERS_FILE = OUTPUT_DIR / "known_providers.json"
DISCOVERIES_FILE = OUTPUT_DIR / "discoveries.jsonl"


def _ensure_output_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _load_known_providers() -> set[str]:
    """Load set of already-known provider URLs to avoid duplicates."""
    _ensure_output_dir()
    if KNOWN_PROVIDERS_FILE.exists():
        try:
            data = json.loads(KNOWN_PROVIDERS_FILE.read_text(encoding="utf-8"))
            return set(data.get("urls", []))
        except (json.JSONDecodeError, OSError):
            return set()
    return set()


def _save_known_providers(known: set[str]):
    _ensure_output_dir()
    data = {"urls": sorted(known), "updated_at": datetime.now(timezone.utc).isoformat()}
    KNOWN_PROVIDERS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _log_discovery(entry: dict):
    """Append a discovery to the discoveries log file."""
    _ensure_output_dir()
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(DISCOVERIES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


async def run_all_discovery() -> dict:
    """Run all discovery sources and collect results.

    Returns a summary dict suitable for notification.
    """
    known = _load_known_providers()
    new_providers: list[dict] = []
    summary = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "sources": {},
        "new_count": 0,
        "total_known": len(known),
    }

    # 1. GitHub monitor
    logger.info("=== GitHub Discovery ===")
    try:
        gh_providers = await github_monitor.scan_github()
        for p in gh_providers:
            if p.base_url and p.base_url not in known:
                entry = {
                    "source": p.source,
                    "name": p.name,
                    "url": p.base_url,
                    "is_free": p.is_free,
                }
                new_providers.append(entry)
                known.add(p.base_url)
                _log_discovery(entry)
        summary["sources"]["github"] = len(gh_providers)
    except Exception as exc:
        logger.warning("GitHub discovery failed: %s", type(exc).__name__)
        summary["sources"]["github"] = f"error: {type(exc).__name__}"

    # 2. Web search
    logger.info("=== Web Search Discovery ===")
    try:
        web_results = await web_search.scan_web()
        for r in web_results:
            url = r.get("url", "")
            if url and url not in known:
                entry = {
                    "source": r.get("source", "web"),
                    "name": r.get("title", "")[:80],
                    "url": url,
                    "is_free": r.get("is_free", False),
                    "mentioned_models": r.get("mentioned_models", []),
                }
                new_providers.append(entry)
                known.add(url)
                _log_discovery(entry)
        summary["sources"]["web_search"] = len(web_results)
    except Exception as exc:
        logger.warning("Web search discovery failed: %s", type(exc).__name__)
        summary["sources"]["web_search"] = f"error: {type(exc).__name__}"

    # 3. Chinese platforms
    logger.info("=== Chinese Platforms Discovery ===")
    try:
        cn_results = await chinese_platforms.scan_chinese_platforms()
        for r in cn_results:
            url = r.get("url", "")
            if url and url not in known:
                entry = {
                    "source": r.get("source", "chinese"),
                    "name": r.get("title", r.get("name", ""))[:80],
                    "url": url,
                }
                new_providers.append(entry)
                known.add(url)
                _log_discovery(entry)
        summary["sources"]["chinese_platforms"] = len(cn_results)
    except Exception as exc:
        logger.warning("Chinese platforms discovery failed: %s", type(exc).__name__)
        summary["sources"]["chinese_platforms"] = f"error: {type(exc).__name__}"

    # 4. Browser probe (optional, requires browser service)
    logger.info("=== Browser Probe Discovery ===")
    try:
        browser_results = await browser_probe.probe_known_sites()
        summary["sources"]["browser_probe"] = len(browser_results)
    except Exception as exc:
        logger.warning("Browser probe failed: %s", type(exc).__name__)
        summary["sources"]["browser_probe"] = f"error: {type(exc).__name__}"

    # Final summary
    summary["new_count"] = len(new_providers)
    summary["total_known"] = len(known)
    summary["new_providers"] = new_providers
    summary["finished_at"] = datetime.now(timezone.utc).isoformat()

    _save_known_providers(known)

    logger.info(
        "Discovery complete: %d new, %d total known",
        len(new_providers),
        len(known),
    )
    return summary


async def _main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    start = time.monotonic()
    summary = await run_all_discovery()
    elapsed = time.monotonic() - start
    logger.info("Total time: %.1fs", elapsed)
    logger.info("New providers: %d", summary["new_count"])
    for p in summary.get("new_providers", [])[:10]:
        logger.info("  NEW: [%s] %s", p.get("source", "?"), p.get("name", p.get("url", "?")[:60]))


if __name__ == "__main__":
    asyncio.run(_main())
