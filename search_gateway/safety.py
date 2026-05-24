import re
import urllib.parse
import ipaddress
import socket

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
    "localhost.localdomain",
    "metadata",
    "metadata.google.internal",
    "localtest.me",
    "lvh.me",
)

_PROXY_FAKE_IP_NETWORKS = (
    ipaddress.ip_network("198.18.0.0/15"),
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


def _hostname_resolves_to_global_ips(host: str, port: int) -> bool:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        return False
    if not infos:
        return False
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            return False
        try:
            resolved = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            return False
        if any(resolved in network for network in _PROXY_FAKE_IP_NETWORKS):
            continue
        if not resolved.is_global:
            return False
    return True


def is_public_http_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return False
    if host in _BLOCKED_HOSTNAMES or host.endswith(".localhost"):
        return False
    ip = _parse_ip_literal(host)
    if ip is not None:
        if not ip.is_global:
            return False
        return True
    return _hostname_resolves_to_global_ips(host, port)
