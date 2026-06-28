"""Gitee URL parsing, redaction, and HTTPS URL builders."""

from __future__ import annotations

import re
from urllib.parse import quote, urlparse

from config import settings

_OAUTH_RE = re.compile(r"oauth2:[^@]+@", re.IGNORECASE)
_OAUTH_TOKEN_RE = re.compile(r"oauth2:([^@]+)@", re.IGNORECASE)
_TOKEN_IN_USER_RE = re.compile(r"^[^:/]+:[^@]+@")


def extract_gitee_oauth_token(url: str) -> str:
    """Return oauth2 token embedded in a Gitee git remote URL (empty if absent)."""
    text = (url or "").strip()
    if not text or "gitee.com" not in text.lower():
        return ""
    match = _OAUTH_TOKEN_RE.search(text)
    if not match:
        return ""
    from urllib.parse import unquote

    return unquote(match.group(1).strip())


def iter_gitee_remote_urls(remote_v_output: str) -> list[str]:
    """Collect every gitee.com URL from `git remote -v` output."""
    urls: list[str] = []
    seen: set[str] = set()
    for line in (remote_v_output or "").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        url = parts[1]
        if "gitee.com" not in url.lower():
            continue
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def redact_remote_url(url: str) -> str:
    """Remove credentials from git remote URLs for logs and docs."""
    text = (url or "").strip()
    if not text:
        return ""
    text = _OAUTH_RE.sub("oauth2:***@", text)
    if "://" in text:
        scheme, rest = text.split("://", 1)
        if "@" in rest.split("/", 1)[0]:
            user_host, path = rest.split("@", 1)
            if ":" in user_host and not user_host.startswith("git@"):
                user = user_host.split(":", 1)[0]
                rest = f"{user}:***@{path}"
            text = f"{scheme}://{rest}"
    return text


def gitee_env_token() -> str:
    """Return Gitee personal access token from environment, preferring GITEE_TOKEN."""
    return settings.INTEGRATIONS.gitee_token


def _parse_gitee_repo_path(base_url: str) -> str:
    """Extract 'user/repo.git' from a Gitee SSH or HTTPS URL.

    Raises ValueError if the URL is not a Gitee repository URL.
    """
    if base_url.startswith("git@gitee.com:"):
        return base_url[len("git@gitee.com:") :]
    parsed = urlparse(base_url)
    host = parsed.netloc.lower().split("@")[-1]
    if "gitee.com" not in host:
        raise ValueError(f"not a Gitee URL: {base_url}")
    return parsed.path.lstrip("/")


def build_gitee_oauth_push_url(base_url: str, token: str) -> str:
    """Return a token-bearing HTTPS URL for Gitee (redact before logging)."""
    repo_path = _parse_gitee_repo_path(base_url)
    encoded_token = quote(token, safe="")
    return f"https://oauth2:{encoded_token}@gitee.com/{repo_path}"


def build_gitee_https_push_url(base_url: str) -> str:
    """Return a token-less HTTPS URL for use with a git credential helper."""
    repo_path = _parse_gitee_repo_path(base_url)
    return f"https://gitee.com/{repo_path}"


def classify_host(url: str) -> str:
    lowered = url.lower()
    if "gitee.com" in lowered:
        return "gitee"
    if "github.com" in lowered:
        return "github"
    host = urlparse(url).netloc.lower()
    return host or "unknown"
