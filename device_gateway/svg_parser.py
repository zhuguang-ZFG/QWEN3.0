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
    x0: float, y0: float, x1: float, y1: float,
    x2: float, y2: float, x3: float, y3: float,
    segments: int,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for i in range(1, segments + 1):
        t = i / segments
        c0 = (1 - t) ** 3
        c1 = 3 * (1 - t) ** 2 * t
        c2 = 3 * (1 - t) * t ** 2
        c3 = t ** 3
        x = c0 * x0 + c1 * x1 + c2 * x2 + c3 * x3
        y = c0 * y0 + c1 * y1 + c2 * y2 + c3 * y3
        points.append((x, y))
    return points


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
            if i + 1 >= len(tokens):
                break
            x = float(tokens[i]) * scale + (cx if cmd == "m" else 0)
            y = float(tokens[i + 1]) * scale + (cy if cmd == "m" else 0)
            i += 2
            cx, cy = x, y
            first_x, first_y = x, y
            path.append({"x": round(origin_x + x, 2), "y": round(origin_y - y, 2), "z": 0})

        elif cmd in ("L", "l"):
            if i + 1 >= len(tokens):
                break
            x = float(tokens[i]) * scale + (cx if cmd == "l" else 0)
            y = float(tokens[i + 1]) * scale + (cy if cmd == "l" else 0)
            i += 2
            cx, cy = x, y
            path.append({"x": round(origin_x + x, 2), "y": round(origin_y - y, 2), "z": 0})

        elif cmd in ("H", "h"):
            if i >= len(tokens):
                break
            x = float(tokens[i]) * scale + (cx if cmd == "h" else 0)
            i += 1
            cx = x
            path.append({"x": round(origin_x + x, 2), "y": round(origin_y - cy, 2), "z": 0})

        elif cmd in ("V", "v"):
            if i >= len(tokens):
                break
            y = float(tokens[i]) * scale + (cy if cmd == "v" else 0)
            i += 1
            cy = y
            path.append({"x": round(origin_x + cx, 2), "y": round(origin_y - y, 2), "z": 0})

        elif cmd in ("C", "c"):
            if i + 5 >= len(tokens):
                break
            x1, y1 = float(tokens[i]), float(tokens[i + 1])
            x2, y2 = float(tokens[i + 2]), float(tokens[i + 3])
            x, y = float(tokens[i + 4]), float(tokens[i + 5])
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
                path.append({"x": round(origin_x + cx, 2), "y": round(origin_y - cy, 2), "z": 0})

        elif cmd in ("Q", "q"):
            if i + 3 >= len(tokens):
                break
            x1, y1 = float(tokens[i]), float(tokens[i + 1])
            x, y = float(tokens[i + 2]), float(tokens[i + 3])
            i += 4
            if cmd == "q":
                x, y = cx + x * scale, cy + y * scale
                x1, y1 = cx + x1 * scale, cy + y1 * scale
            else:
                x, y = x * scale, y * scale
                x1, y1 = x1 * scale, y1 * scale
            for pt in _bezier_to_polyline(cx, cy, x1, y1, x1, y1, x, y, 8):
                cx, cy = pt
                path.append({"x": round(origin_x + cx, 2), "y": round(origin_y - cy, 2), "z": 0})

        elif cmd in ("Z", "z"):
            cx, cy = first_x, first_y
            path.append({"x": round(origin_x + cx, 2), "y": round(origin_y - cy, 2), "z": 0})

    return clamp_path(path, max_points)
