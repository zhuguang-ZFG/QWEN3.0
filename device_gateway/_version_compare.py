"""Firmware version comparison helpers — semantic (not lexicographic) comparison."""


def parse_version(s: str) -> tuple[int, ...]:
    """Parse a firmware version string like 'v1.10.0' into a comparable tuple.

    Strips a leading 'v' prefix and splits on dots. Non-numeric segments are
    treated as 0. Returns (0,) for empty/invalid input so callers can safely
    compare with ``>=`` without IndexError.
    """
    cleaned = (s or "").strip().lstrip("vV")
    if not cleaned:
        return (0,)
    parts: list[int] = []
    for seg in cleaned.split("."):
        try:
            parts.append(int(seg))
        except ValueError:
            parts.append(0)
    return tuple(parts)
