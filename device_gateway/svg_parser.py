"""Parse SVG path 'd' attributes into polyline motion paths."""

from __future__ import annotations

from device_gateway.path_data import MAX_PATH_POINTS, clamp_path


def _tokenize_svg_d(d_string: str) -> list[str]:
    tokens: list[str] = []
    current = ""
    for ch in d_string.replace(",", " "):
        if ch.isalpha():
            if current:
                tokens.append(current.strip())
                current = ""
            tokens.append(ch)
        elif ch in (" ", "\t", "\n", "\r"):
            if current:
                tokens.append(current.strip())
                current = ""
        elif ch in ("-", ".") or ch.isdigit():
            current += ch
    if current:
        tokens.append(current.strip())
    return [t for t in tokens if t]


def _bezier_to_polyline(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    x3: float,
    y3: float,
    segments: int,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for i in range(1, segments + 1):
        t = i / segments
        c0 = (1 - t) ** 3
        c1 = 3 * (1 - t) ** 2 * t
        c2 = 3 * (1 - t) * t**2
        c3 = t**3
        x = c0 * x0 + c1 * x1 + c2 * x2 + c3 * x3
        y = c0 * y0 + c1 * y1 + c2 * y2 + c3 * y3
        points.append((x, y))
    return points


def _pt(origin_x: float, origin_y: float, x: float, y: float) -> dict[str, float]:
    return {"x": round(origin_x + x, 2), "y": round(origin_y - y, 2), "z": 0}


def _safe_float(token: str) -> float | None:
    try:
        return float(token)
    except ValueError:
        return None


def _handle_ml(
    tokens: list[str], i: int, cmd: str, cx: float, cy: float, scale: float, ox: float, oy: float, path: list
) -> tuple[int, float, float, float, float]:
    rel = cmd == "m"
    if i + 1 >= len(tokens):
        return len(tokens), cx, cy, cx if rel else 0.0, cy if rel else 0.0
    x = _safe_float(tokens[i])
    y = _safe_float(tokens[i + 1])
    if x is None or y is None:
        return len(tokens), cx, cy, cx if rel else 0.0, cy if rel else 0.0
    x = x * scale + (cx if rel else 0)
    y = y * scale + (cy if rel else 0)
    i += 2
    path.append(_pt(ox, oy, x, y))
    first_x = x if cmd == "M" or (cmd == "m" and not path[:-1]) else 0.0
    first_y = y if cmd == "M" or (cmd == "m" and not path[:-1]) else 0.0
    return i, x, y, first_x, first_y


def _handle_hv(
    tokens: list[str], i: int, cmd: str, cx: float, cy: float, scale: float, ox: float, oy: float, path: list
) -> tuple[int, float, float]:
    rel = cmd in ("h", "v")
    if i >= len(tokens):
        return len(tokens), cx, cy
    value = _safe_float(tokens[i])
    if value is None:
        return len(tokens), cx, cy
    if cmd in ("H", "h"):
        cx = value * scale + (cx if rel else 0)
    else:
        cy = value * scale + (cy if rel else 0)
    i += 1
    path.append(_pt(ox, oy, cx, cy))
    return i, cx, cy


def _handle_cubic(
    tokens: list[str], i: int, cmd: str, cx: float, cy: float, scale: float, ox: float, oy: float, path: list
) -> tuple[int, float, float]:
    if i + 5 >= len(tokens):
        return len(tokens), cx, cy
    coords = [_safe_float(tokens[i + k]) for k in range(6)]
    if any(c is None for c in coords):
        return len(tokens), cx, cy
    x1, y1, x2, y2, x, y = coords  # type: ignore[assignment]
    i += 6
    if cmd == "c":
        x, y = cx + x * scale, cy + y * scale
        x1, y1 = cx + x1 * scale, cy + y1 * scale
        x2, y2 = cx + x2 * scale, cy + y2 * scale
    else:
        x, y = x * scale, y * scale
        x1, y1 = x1 * scale, y1 * scale
        x2, y2 = x2 * scale, y2 * scale
    for pt in _bezier_to_polyline(cx, cy, x1, y1, x2, y2, x, y, 8):
        cx, cy = pt
        path.append(_pt(ox, oy, cx, cy))
    return i, cx, cy


def _handle_quad(
    tokens: list[str], i: int, cmd: str, cx: float, cy: float, scale: float, ox: float, oy: float, path: list
) -> tuple[int, float, float]:
    if i + 3 >= len(tokens):
        return len(tokens), cx, cy
    coords = [_safe_float(tokens[i + k]) for k in range(4)]
    if any(c is None for c in coords):
        return len(tokens), cx, cy
    x1, y1, x, y = coords  # type: ignore[assignment]
    i += 4
    if cmd == "q":
        x, y = cx + x * scale, cy + y * scale
        x1, y1 = cx + x1 * scale, cy + y1 * scale
    else:
        x, y = x * scale, y * scale
        x1, y1 = x1 * scale, y1 * scale
    for pt in _bezier_to_polyline(cx, cy, x1, y1, x1, y1, x, y, 8):
        cx, cy = pt
        path.append(_pt(ox, oy, cx, cy))
    return i, cx, cy


def svg_path_to_motion(
    d_string: str,
    origin_x: float = 5.0,
    origin_y: float = 20.0,
    scale: float = 1.0,
    max_points: int = MAX_PATH_POINTS,
) -> list[dict[str, float]]:
    """Parse SVG path 'd' attribute into a polyline motion path.

    Supports M, L, C (quadratic Bézier → polyline), Q, and Z commands.
    Relative commands (m, l, c, q) are converted to absolute.
    """
    tokens = _tokenize_svg_d(d_string)
    path: list[dict[str, float]] = []
    cx, cy = 0.0, 0.0
    first_x, first_y = 0.0, 0.0
    i = 0
    while i < len(tokens):
        cmd = tokens[i]
        i += 1
        if cmd in ("M", "m"):
            i, cx, cy, first_x, first_y = _handle_ml(tokens, i, cmd, cx, cy, scale, origin_x, origin_y, path)
        elif cmd in ("L", "l"):
            i, cx, cy, _, _ = _handle_ml(tokens, i, cmd, cx, cy, scale, origin_x, origin_y, path)
        elif cmd in ("H", "h", "V", "v"):
            i, cx, cy = _handle_hv(tokens, i, cmd, cx, cy, scale, origin_x, origin_y, path)
        elif cmd in ("C", "c"):
            i, cx, cy = _handle_cubic(tokens, i, cmd, cx, cy, scale, origin_x, origin_y, path)
        elif cmd in ("Q", "q"):
            i, cx, cy = _handle_quad(tokens, i, cmd, cx, cy, scale, origin_x, origin_y, path)
        elif cmd in ("Z", "z"):
            cx, cy = first_x, first_y
            path.append(_pt(origin_x, origin_y, cx, cy))

    return clamp_path(path, max_points)
