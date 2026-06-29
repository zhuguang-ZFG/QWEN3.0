"""SVG 路径验证器与内容净化

验证 SVG path 的有效性、复杂度和工作区适配；同时提供上传 SVG 标记的
脚本/事件处理器剥离，防止存储型 XSS。
"""

from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET


# AUDIT-11-A1：SVG 上传内容净化上限
_MAX_SVG_SIZE_BYTES = 1 * 1024 * 1024

# 危险标签：script 可直接执行；foreignObject/iframe/object/embed 可引入外部内容；
# style 虽非直接脚本，但可触发 CSS exfil / expression（旧 IE），一并移除以简化攻击面。
_BANNED_SVG_TAGS = frozenset({"script", "foreignobject", "iframe", "object", "embed", "style"})

# 危险 URI scheme
_DANGEROUS_URI_SCHEMES = ("javascript:", "data:text/html", "vbscript:")


@dataclass
class ValidationResult:
    """验证结果"""

    valid: bool
    errors: list[str]
    warnings: list[str]
    complexity: dict  # {point_count, stroke_count, bbox}


@dataclass
class SanitizationResult:
    """SVG 内容净化结果"""

    ok: bool
    cleaned: str
    removed: list[str]
    error: str = ""


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


def _local_name(tag: str) -> str:
    """剥离 XML namespace，只返回本地标签名/属性名。"""
    if tag.startswith("{"):
        return tag.split("}", 1)[-1].lower()
    return tag.lower()


def _is_dangerous_uri(value: str) -> bool:
    """检查属性值是否包含可执行 URI scheme。"""
    lowered = value.strip().lower()
    return any(lowered.startswith(scheme) for scheme in _DANGEROUS_URI_SCHEMES)


def _sanitize_element(element: ET.Element, removed: list[str]) -> bool:
    """递归处理单个元素：返回 True 表示该元素应被保留。"""
    tag_local = _local_name(element.tag)

    if tag_local in _BANNED_SVG_TAGS:
        removed.append(f"<{tag_local}>")
        return False

    # 检查并清洗属性
    for attr_name in list(element.attrib):
        attr_local = _local_name(attr_name)
        value = element.attrib[attr_name]

        if attr_local.startswith("on"):
            removed.append(f"{tag_local}@{attr_local}")
            del element.attrib[attr_name]
            continue

        if attr_local in {"href", "src", "data", "xlink:href"} and _is_dangerous_uri(value):
            removed.append(f"{tag_local}@{attr_local}={value[:40]}")
            del element.attrib[attr_name]
            continue

    # 递归处理子元素：必须倒序删除，避免索引错乱
    for child in list(element):
        if not _sanitize_element(child, removed):
            element.remove(child)

    return True


def sanitize_svg_markup(svg_bytes: bytes | str) -> SanitizationResult:
    """净化 SVG 标记：删除 script/foreignObject/iframe/object/embed/style 标签、
    事件处理器属性以及 javascript:/data:text/html 等危险 URI。

    使用标准库 xml.etree.ElementTree 解析，拒绝 DOCTYPE/处理指令以防御
    XXE/Billion laughs 攻击向量。

    若内容不以 '<' 开头（例如纯 path data），视为无标记内容直接放行。
    """
    if isinstance(svg_bytes, str):
        raw = svg_bytes
    else:
        try:
            raw = svg_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            return SanitizationResult(ok=False, cleaned="", removed=[], error=f"invalid utf-8: {exc}")

    if len(raw.encode("utf-8")) > _MAX_SVG_SIZE_BYTES:
        return SanitizationResult(
            ok=False,
            cleaned="",
            removed=[],
            error=f"SVG exceeds max size {_MAX_SVG_SIZE_BYTES} bytes",
        )

    stripped = raw.strip()
    if not stripped.startswith("<"):
        # 纯路径数据或文本，无 SVG 标记，无需净化
        return SanitizationResult(ok=True, cleaned=raw, removed=[])

    lower_preview = stripped.lower()
    if "<!doctype" in lower_preview:
        return SanitizationResult(ok=False, cleaned="", removed=[], error="DOCTYPE is not allowed in SVG")

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return SanitizationResult(ok=False, cleaned="", removed=[], error=f"SVG parse error: {exc}")

    removed: list[str] = []
    _sanitize_element(root, removed)

    # 固定常见 SVG 命名空间前缀，避免序列化后出现 ns0/ns1
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    # encoding='unicode' 返回 str，不带 XML 声明
    cleaned = ET.tostring(root, encoding="unicode")
    return SanitizationResult(ok=True, cleaned=cleaned, removed=removed)
