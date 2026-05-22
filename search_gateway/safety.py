import re

_TOKEN_RE = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{20,})")
_WIN_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s]+")
_PRIVATE_IP_RE = re.compile(
    r"\b(10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)\b"
)


def redact_sensitive_query(query: str) -> str:
    query = _TOKEN_RE.sub("[REDACTED_TOKEN]", query)
    query = _WIN_PATH_RE.sub("[REDACTED_PATH]", query)
    query = _PRIVATE_IP_RE.sub("[REDACTED_PRIVATE_IP]", query)
    return query
