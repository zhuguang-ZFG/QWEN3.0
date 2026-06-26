"""SVG 路径验证器

验证 SVG path 的有效性、复杂度和工作区适配。
"""

from dataclasses import dataclass
import re


@dataclass
class ValidationResult:
    """验证结果"""

    valid: bool
    errors: list[str]
    warnings: list[str]
    complexity: dict  # {point_count, stroke_count, bbox}


def _validate_complexity(point_count: int, max_points: int, errors: list, warnings: list) -> None:
    if point_count > max_points:
        errors.append(f"路径点数 {point_count} 超过限制 {max_points}")
    elif point_count > max_points * 0.8:
        warnings.append(f"路径点数 {point_count} 接近限制")


def _validate_bbox(bbox: dict, workspace: tuple[float, float], errors: list, warnings: list) -> None:
    if not bbox:
        return
    w, h = workspace
    if bbox["min_x"] < 0 or bbox["min_y"] < 0 or bbox["max_x"] > w or bbox["max_y"] > h:
        errors.append(f"路径超出工作区 ({w}x{h})")
    elif bbox["max_x"] > w * 0.95 or bbox["max_y"] > h * 0.95:
        warnings.append("路径接近工作区边界")


def validate_svg_path(
    path_data: str, workspace: tuple[float, float] = (200.0, 200.0), max_points: int = 5000
) -> ValidationResult:
    """验证 SVG 路径

    Args:
        path_data: SVG path 字符串
        workspace: 工作区尺寸 (width, height)
        max_points: 最大点数限制

    Returns:
        ValidationResult
    """
    errors = []
    warnings = []

    if not path_data or not path_data.strip():
        errors.append("路径为空")
        return ValidationResult(False, errors, warnings, {})

    try:
        commands, points = _parse_path(path_data)
    except ValueError as e:
        errors.append(f"路径解析失败: {e}")
        return ValidationResult(False, errors, warnings, {})

    point_count = len(points)
    bbox = _calculate_bbox(points)
    complexity = {"point_count": point_count, "stroke_count": commands.count("M"), "bbox": bbox}

    _validate_complexity(point_count, max_points, errors, warnings)
    _validate_bbox(bbox, workspace, errors, warnings)

    return ValidationResult(len(errors) == 0, errors, warnings, complexity)


def _parse_path(path_data: str) -> tuple[list[str], list[tuple[float, float]]]:
    """解析 SVG path，提取指令和坐标点"""
    # 支持的指令：M L C Q Z
    pattern = r"([MLCQZmlcqz])\s*([-\d.,\s]*)"
    matches = re.findall(pattern, path_data)

    if not matches:
        raise ValueError("未找到有效的 SVG 指令")

    commands = []
    points = []

    for cmd, coords in matches:
        commands.append(cmd.upper())

        # Z 指令无坐标
        if cmd.upper() == "Z":
            continue

        # 解析坐标
        coords_clean = coords.replace(",", " ").strip()
        if coords_clean:
            nums = [float(x) for x in coords_clean.split()]
            # 按指令类型解析坐标对
            if cmd.upper() in ("M", "L"):
                for i in range(0, len(nums), 2):
                    if i + 1 < len(nums):
                        points.append((nums[i], nums[i + 1]))
            elif cmd.upper() == "C":  # 三次贝塞尔
                for i in range(0, len(nums), 6):
                    if i + 5 < len(nums):
                        points.append((nums[i + 4], nums[i + 5]))
            elif cmd.upper() == "Q":  # 二次贝塞尔
                for i in range(0, len(nums), 4):
                    if i + 3 < len(nums):
                        points.append((nums[i + 2], nums[i + 3]))

    return commands, points


def _calculate_bbox(points: list[tuple[float, float]]) -> dict:
    """计算路径边界框"""
    if not points:
        return {}

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    return {
        "min_x": min(xs),
        "max_x": max(xs),
        "min_y": min(ys),
        "max_y": max(ys),
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
    }
