"""Generate standalone SVG previews of motion paths."""

from __future__ import annotations


def preview_svg(
    path: list[dict[str, float]],
    width: float = 200,
    height: float = 200,
    *,
    title: str = "motion preview",
) -> str:
    """Generate a standalone SVG preview of a motion path."""
    if not path:
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"><text x="10" y="20" font-size="12">(empty path)</text></svg>'

    points_str = " ".join(f"{p['x']},{p['y']}" for p in path)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" fill="#fafafa" stroke="#ccc"/>'
        f'<polyline points="{points_str}" fill="none" stroke="#2563eb" stroke-width="1.5" stroke-linejoin="round"/>'
        f'<text x="5" y="{height - 5}" font-size="10" fill="#888">{title} — {len(path)} pts</text>'
        f"</svg>"
    )
