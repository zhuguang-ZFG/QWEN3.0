"""GitHub monitor: track awesome-lists and trending repos for new AI APIs.

Periodically scans curated lists of free LLM APIs and watches for new
providers being added. Uses GitHub's REST API (no auth for public repos).
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MONITOR_REPOS = [
    ("mnfst/awesome-free-llm-apis", "README.md"),
    ("cheahjs/free-llm-api-resources", "README.md"),
    ("Wan-Verse/awesome-open-source-llm-router", "README.md"),
]

# Markdown patterns to extract provider info
_API_URL_PATTERN = re.compile(
    r"(https?://[^\s\)]+(?:api|gateway|v1|chat/completions)[^\s\)]*)",
    re.IGNORECASE,
)
_FREE_LABEL_PATTERN = re.compile(r"(?i)(free|no.?cost|no.?auth|no.?key|no.?api.?key)")


@dataclass
class DiscoveredProvider:
    source: str
    name: str = ""
    base_url: str = ""
    models: list[str] = field(default_factory=list)
    description: str = ""
    is_free: bool = False
    raw_line: str = ""
    discovered_at: float = field(default_factory=time.time)


async def fetch_github_readme(
    owner: str, repo: str, path: str = "README.md"
) -> str | None:
    """Fetch raw README content from a public GitHub repo."""
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{path}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            # Try master branch
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{path}"
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            logger.debug("fetch_github_readme %s/%s: HTTP %d", owner, repo, resp.status_code)
            return None
    except Exception as exc:
        logger.warning("fetch_github_readme %s/%s: %s", owner, repo, type(exc).__name__)
        return None


def extract_providers_from_markdown(
    content: str, source: str
) -> list[DiscoveredProvider]:
    """Extract potential AI API providers from markdown content.

    Looks for:
    1. Table rows with API URLs and model names
    2. Lines containing known API patterns
    3. Free/zero-cost indicators
    """
    providers: list[DiscoveredProvider] = []

    for line in content.split("\n"):
        line = line.strip()
        if not line or len(line) < 20:
            continue

        # Find API URLs in the line
        urls = _API_URL_PATTERN.findall(line)
        if not urls:
            continue

        is_free = bool(_FREE_LABEL_PATTERN.search(line))

        for url in urls:
            # Clean up common markdown artifacts
            url = url.rstrip(".,;:)]}")

            # Try to extract a name from the line
            name = ""
            # Look for markdown link pattern: [name](url)
            link_match = re.search(rf"\[([^\]]+)\]\s*\(\s*{re.escape(url)}\s*\)", line)
            if link_match:
                name = link_match.group(1).strip()
            else:
                # Use domain as fallback name
                from urllib.parse import urlparse

                parsed = urlparse(url)
                name = parsed.netloc or url[:40]

            providers.append(DiscoveredProvider(
                source=source,
                name=name,
                base_url=url,
                is_free=is_free,
                raw_line=line[:200],
            ))

    return providers


async def scan_github() -> list[DiscoveredProvider]:
    """Scan all monitored GitHub repos for new AI API providers."""
    all_providers: list[DiscoveredProvider] = []

    for owner_repo, path in MONITOR_REPOS:
        logger.info("Scanning GitHub: %s", owner_repo)
        content = await fetch_github_readme(
            owner_repo.split("/")[0], owner_repo.split("/")[1], path
        )
        if content:
            providers = extract_providers_from_markdown(content, f"github:{owner_repo}")
            logger.info("  Found %d potential providers in %s", len(providers), owner_repo)
            all_providers.extend(providers)

    # Deduplicate by base_url
    seen: set[str] = set()
    unique: list[DiscoveredProvider] = []
    for p in all_providers:
        if p.base_url not in seen:
            seen.add(p.base_url)
            unique.append(p)

    logger.info("GitHub scan: %d total, %d unique providers", len(all_providers), len(unique))
    return unique


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

async def _main():
    logging.basicConfig(level=logging.INFO)
    providers = await scan_github()
    for p in providers[:20]:
        print(f"  [{p.source}] {p.name}: {p.base_url}  free={p.is_free}")


if __name__ == "__main__":
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
