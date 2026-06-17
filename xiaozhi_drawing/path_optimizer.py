"""SVG 路径优化器

简化路径、缩放适配、笔画顺序优化。
"""

from dataclasses import dataclass
import re


@dataclass
class OptimizationResult:
    """优化结果"""

    optimized_path: str
    original_points: int
    optimized_points: int
    reduction_ratio: float


def optimize_svg_path(
    path_data: str, tolerance: float = 2.0, target_size: tuple[float, float] = (180.0, 180.0)
) -> OptimizationResult:
    """优化 SVG 路径

    Args:
        path_data: 原始 SVG path
        tolerance: 简化容差（像素）
        target_size: 目标尺寸 (width, height)

    Returns:
        OptimizationResult
    """
    # 解析原始路径
    points = _parse_points(path_data)
    original_count = len(points)

    if original_count == 0:
        return OptimizationResult(path_data, 0, 0, 0.0)

    # 1. 简化路径（Douglas-Peucker）
    simplified = _simplify_points(points, tolerance)

    # 2. 缩放适配
    scaled = _scale_to_fit(simplified, target_size)

    # 3. 居中
    centered = _center_points(scaled, target_size)

    # 4. 重建路径字符串
    optimized_path = _rebuild_path(centered)
    optimized_count = len(centered)
    reduction = 1.0 - (optimized_count / original_count) if original_count > 0 else 0.0

    return OptimizationResult(
        optimized_path=optimized_path,
        original_points=original_count,
        optimized_points=optimized_count,
        reduction_ratio=reduction,
    )


def _parse_points(path_data: str) -> list[tuple[float, float]]:
    """解析路径为点序列"""
    pattern = r"([MLCQZmlcqz])\s*([-\d.,\s]*)"
    matches = re.findall(pattern, path_data)
    points = []

    for cmd, coords in matches:
        if cmd.upper() == "Z":
            continue
        coords_clean = coords.replace(",", " ").strip()
        if coords_clean:
            nums = [float(x) for x in coords_clean.split()]
            if cmd.upper() in ("M", "L"):
                for i in range(0, len(nums), 2):
                    if i + 1 < len(nums):
                        points.append((nums[i], nums[i + 1]))
            elif cmd.upper() == "C":
                for i in range(0, len(nums), 6):
                    if i + 5 < len(nums):
                        points.append((nums[i + 4], nums[i + 5]))
            elif cmd.upper() == "Q":
                for i in range(0, len(nums), 4):
                    if i + 3 < len(nums):
                        points.append((nums[i + 2], nums[i + 3]))

    return points


def _simplify_points(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    """Douglas-Peucker 算法简化"""
    if len(points) < 3:
        return points

    # 找最远点
    first, last = points[0], points[-1]
    max_dist = 0.0
    max_idx = 0

    for i in range(1, len(points) - 1):
        dist = _perpendicular_distance(points[i], first, last)
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    # 递归简化
    if max_dist > tolerance:
        left = _simplify_points(points[: max_idx + 1], tolerance)
        right = _simplify_points(points[max_idx:], tolerance)
        return left[:-1] + right
    else:
        return [first, last]


def _perpendicular_distance(
    point: tuple[float, float], line_start: tuple[float, float], line_end: tuple[float, float]
) -> float:
    """点到线段的垂直距离"""
    x0, y0 = point
    x1, y1 = line_start
    x2, y2 = line_end

    dx = x2 - x1
    dy = y2 - y1

    if dx == 0 and dy == 0:
        return ((x0 - x1) ** 2 + (y0 - y1) ** 2) ** 0.5

    t = max(0, min(1, ((x0 - x1) * dx + (y0 - y1) * dy) / (dx * dx + dy * dy)))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy

    return ((x0 - proj_x) ** 2 + (y0 - proj_y) ** 2) ** 0.5


def _scale_to_fit(points: list[tuple[float, float]], target_size: tuple[float, float]) -> list[tuple[float, float]]:
    """缩放适配目标尺寸，保持宽高比"""
    if not points:
        return points

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x
    height = max_y - min_y

    if width == 0 or height == 0:
        return points

    # 计算缩放比例（保持宽高比）
    target_w, target_h = target_size
    scale = min(target_w / width, target_h / height)

    # 缩放
    return [(scale * x, scale * y) for x, y in points]


def _center_points(points: list[tuple[float, float]], target_size: tuple[float, float]) -> list[tuple[float, float]]:
    """居中路径"""
    if not points:
        return points

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x
    height = max_y - min_y

    # 计算偏移量
    target_w, target_h = target_size
    offset_x = (target_w - width) / 2 - min_x
    offset_y = (target_h - height) / 2 - min_y

    return [(x + offset_x, y + offset_y) for x, y in points]


def _rebuild_path(points: list[tuple[float, float]]) -> str:
    """重建 SVG 路径字符串"""
    if not points:
        return ""

    path_parts = [f"M {points[0][0]:.2f} {points[0][1]:.2f}"]
    for x, y in points[1:]:
        path_parts.append(f"L {x:.2f} {y:.2f}")
    path_parts.append("Z")

    return " ".join(path_parts)
