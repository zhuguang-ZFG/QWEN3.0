import re
import urllib.parse
import ipaddress

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


_BLOCKED_HOSTNAMES = (
    "localhost",
    "metadata",
    "metadata.google.internal",
)


def sanitize_error_text(text: str, *, max_chars: int = 2000) -> str:
    redacted = redact_sensitive_query((text or "")[:5000])
    return redacted[:max_chars]


def _parse_ip_literal(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass

    try:
        if host.startswith(("0x", "0X")):
            value = int(host, 16)
        elif host.isdigit():
            value = int(host, 10)
        else:
            return None
        if 0 <= value <= 0xFFFFFFFF:
            return ipaddress.IPv4Address(value)
    except ValueError:
        return None
    return None


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
    if host in _BLOCKED_HOSTNAMES or host.endswith(".localhost"):
        return False
    ip = _parse_ip_literal(host)
    if ip is not None:
        if not ip.is_global:
            return False
    return True
