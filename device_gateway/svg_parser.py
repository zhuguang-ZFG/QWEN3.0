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


def _parse_float_args(tokens: list[str], start: int, count: int) -> list[float] | None:
    values: list[float] = []
    for k in range(count):
        value = _safe_float(tokens[start + k])
        if value is None:
            return None
        values.append(value)
    return values


def _handle_ml(
    tokens: list[str], i: int, cmd: str, cx: float, cy: float, scale: float, ox: float, oy: float, path: list,
    *, is_first: bool,
) -> tuple[int, float, float, bool, tuple[float, float] | None]:
    """Consume one (x, y) group for M/m/L/l. Returns (new_i, new_cx, new_cy, consumed, first).

    consumed=False means no group was parsed (end-of-tokens or non-numeric); the
    caller stops looping and lets the outer loop treat the next token as a new
    command. first is set only on the *first* moveto group (M/m) so a multi-group
    moveto (`M x1 y1 x2 y2`) treats subsequent groups as implicit lineto.
    """
    rel = cmd in ("m", "l")
    if i + 1 >= len(tokens):
        return i, cx, cy, False, None
    x = _safe_float(tokens[i])
    y = _safe_float(tokens[i + 1])
    if x is None or y is None:
        return i, cx, cy, False, None
    x = x * scale + (cx if rel else 0)
    y = y * scale + (cy if rel else 0)
    i += 2
    path.append(_pt(ox, oy, x, y))
    first: tuple[float, float] | None = (x, y) if (cmd in ("M", "m") and is_first) else None
    return i, x, y, True, first


def _handle_hv(
    tokens: list[str], i: int, cmd: str, cx: float, cy: float, scale: float, ox: float, oy: float, path: list
) -> tuple[int, float, float, bool]:
    """Consume one scalar group for H/h/V/v. Returns (new_i, new_cx, new_cy, consumed)."""
    rel = cmd in ("h", "v")
    if i >= len(tokens):
        return i, cx, cy, False
    value = _safe_float(tokens[i])
    if value is None:
        return i, cx, cy, False
    if cmd in ("H", "h"):
        cx = value * scale + (cx if rel else 0)
    else:
        cy = value * scale + (cy if rel else 0)
    i += 1
    path.append(_pt(ox, oy, cx, cy))
    return i, cx, cy, True


def _handle_cubic(
    tokens: list[str], i: int, cmd: str, cx: float, cy: float, scale: float, ox: float, oy: float, path: list
) -> tuple[int, float, float, bool]:
    """Consume one 6-arg cubic group for C/c. Returns (new_i, new_cx, new_cy, consumed)."""
    if len(tokens) - i < 6:
        return i, cx, cy, False
    coords = _parse_float_args(tokens, i, 6)
    if coords is None:
        return i, cx, cy, False
    x1, y1, x2, y2, x, y = coords
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
    return i, cx, cy, True


def _handle_quad(
    tokens: list[str], i: int, cmd: str, cx: float, cy: float, scale: float, ox: float, oy: float, path: list
) -> tuple[int, float, float, bool]:
    """Consume one 4-arg quad group for Q/q. Returns (new_i, new_cx, new_cy, consumed)."""
    if len(tokens) - i < 4:
        return i, cx, cy, False
    coords = _parse_float_args(tokens, i, 4)
    if coords is None:
        return i, cx, cy, False
    x1, y1, x, y = coords
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
    return i, cx, cy, True


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
        if cmd in ("M", "m", "L", "l"):
            # SVG allows one command letter followed by multiple coordinate
            # groups (`L x1 y1 x2 y2 ...`); after a moveto's first group the
            # rest are implicit linetos. Consume groups until a non-numeric
            # token ends the run, then let the outer loop treat it as a new
            # command letter.
            is_moveto = cmd in ("M", "m")
            group_idx = 0
            while i < len(tokens):
                if group_idx == 0:
                    linear_cmd = cmd
                elif is_moveto:
                    # Subsequent groups after a moveto are implicit linetos,
                    # preserving the original command's relativity.
                    linear_cmd = "L" if cmd == "M" else "l"
                else:
                    linear_cmd = cmd
                ni, ncx, ncy, consumed, first = _handle_ml(
                    tokens, i, linear_cmd, cx, cy, scale, origin_x, origin_y, path, is_first=(group_idx == 0)
                )
                if not consumed:
                    break
                i, cx, cy = ni, ncx, ncy
                if first is not None:
                    first_x, first_y = first
                group_idx += 1
        elif cmd in ("H", "h", "V", "v"):
            while i < len(tokens):
                ni, ncx, ncy, consumed = _handle_hv(
                    tokens, i, cmd, cx, cy, scale, origin_x, origin_y, path
                )
                if not consumed:
                    break
                i, cx, cy = ni, ncx, ncy
        elif cmd in ("C", "c"):
            while i < len(tokens):
                ni, ncx, ncy, consumed = _handle_cubic(
                    tokens, i, cmd, cx, cy, scale, origin_x, origin_y, path
                )
                if not consumed:
                    break
                i, cx, cy = ni, ncx, ncy
        elif cmd in ("Q", "q"):
            while i < len(tokens):
                ni, ncx, ncy, consumed = _handle_quad(
                    tokens, i, cmd, cx, cy, scale, origin_x, origin_y, path
                )
                if not consumed:
                    break
                i, cx, cy = ni, ncx, ncy
        elif cmd in ("Z", "z"):
            cx, cy = first_x, first_y
            path.append(_pt(origin_x, origin_y, cx, cy))
        # Unknown token: leave i as-is at the next token (already advanced past
        # the command letter) and let the loop re-evaluate it as a command.

    return clamp_path(path, max_points)
