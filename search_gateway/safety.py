import re
import urllib.parse

_TOKEN_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{12,}"
    r"|gh[pousr]_[A-Za-z0-9_]{20,}"
    r"|jina_[A-Za-z0-9_-]{20,}"
    r"|sk-tinyfish-[A-Za-z0-9_-]{10,}"
    r"|xWVr[A-Za-z0-9]{10,})"
)
_WIN_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s]+")
_PRIVATE_IP_RE = re.compile(
    r"\b(10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)\b"
)


def redact_sensitive_query(query: str) -> str:
    if not query or len(query) > 5000:
        return ""
    query = _TOKEN_RE.sub("[REDACTED_TOKEN]", query)
    query = _WIN_PATH_RE.sub("[REDACTED_PATH]", query)
    query = _PRIVATE_IP_RE.sub("[REDACTED_PRIVATE_IP]", query)
    return query


_PRIVATE_HOST_PREFIXES = (
    "localhost",
    "127.",
    "10.",
    "192.168.",
    "169.254.",
    "0.",
)


def sanitize_error_text(text: str, *, max_chars: int = 2000) -> str:
    redacted = redact_sensitive_query((text or "")[:5000])
    return redacted[:max_chars]


def is_public_http_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if host.startswith(_PRIVATE_HOST_PREFIXES):
        return False
    if host.startswith("172."):
        parts = host.split(".")
        if len(parts) >= 2 and parts[1].isdigit() and 16 <= int(parts[1]) <= 31:
            return False
    return True
