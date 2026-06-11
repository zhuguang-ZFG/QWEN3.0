"""预设图形库 - 常用基础图形的 SVG 生成"""
import math
from typing import Dict, Any


def get_preset_svg(shape: str, size: int = 180) -> Dict[str, Any]:
    """
    获取预设图形的 SVG 路径

    Args:
        shape: 图形名称 (circle/square/triangle/star/heart/crescent)
        size: 目标尺寸

    Returns:
        {
            'status': 'success' | 'failed',
            'svg_path': str,
            'width': int,
            'height': int,
            'shape': str,
            'error': str | None
        }
    """
    generators = {
        'circle': _circle_path,
        'square': _square_path,
        'triangle': _triangle_path,
        'star': _star_path,
        'heart': _heart_path,
        'crescent': _crescent_path
    }

    if shape not in generators:
        return {
            'status': 'failed',
            'svg_path': '',
            'width': 0,
            'height': 0,
            'shape': shape,
            'error': f'Unknown shape: {shape}'
        }

    svg_path = generators[shape](size)
    return {
        'status': 'success',
        'svg_path': svg_path,
        'width': size,
        'height': size,
        'shape': shape,
        'error': None
    }


def _circle_path(size: int) -> str:
    """圆形"""
    cx, cy = size / 2, size / 2
    r = size * 0.45
    return f"M {cx-r} {cy} A {r} {r} 0 1 1 {cx+r} {cy} A {r} {r} 0 1 1 {cx-r} {cy} Z"


def _square_path(size: int) -> str:
    """正方形"""
    margin = size * 0.1
    return f"M {margin} {margin} L {size-margin} {margin} L {size-margin} {size-margin} L {margin} {size-margin} Z"


def _triangle_path(size: int) -> str:
    """等边三角形"""
    cx, cy = size / 2, size / 2
    r = size * 0.45
    x1, y1 = cx, cy - r
    x2, y2 = cx - r * 0.866, cy + r * 0.5
    x3, y3 = cx + r * 0.866, cy + r * 0.5
    return f"M {x1} {y1} L {x2} {y2} L {x3} {y3} Z"


def _star_path(size: int) -> str:
    """五角星"""
    cx, cy = size / 2, size / 2
    outer_r = size * 0.45
    inner_r = outer_r * 0.382
    points = []
    for i in range(10):
        angle = math.pi / 2 - (2 * math.pi * i / 10)
        r = outer_r if i % 2 == 0 else inner_r
        x = cx + r * math.cos(angle)
        y = cy - r * math.sin(angle)
        points.append((x, y))
    path = f"M {points[0][0]} {points[0][1]}"
    for x, y in points[1:]:
        path += f" L {x} {y}"
    return path + " Z"


def _heart_path(size: int) -> str:
    """心形"""
    cx, cy = size / 2, size / 2
    w = size * 0.8
    h = size * 0.7
    # 简化心形路径（两个圆 + 三角形）
    return f"M {cx} {cy+h*0.3} C {cx-w*0.5} {cy-h*0.1} {cx-w*0.4} {cy-h*0.4} {cx} {cy-h*0.2} C {cx+w*0.4} {cy-h*0.4} {cx+w*0.5} {cy-h*0.1} {cx} {cy+h*0.3} Z"


def _crescent_path(size: int) -> str:
    """月牙"""
    cx, cy = size / 2, size / 2
    r = size * 0.45
    offset = r * 0.3
    # 两个圆弧相减
    return f"M {cx+offset} {cy} A {r} {r} 0 1 1 {cx+offset} {cy+0.01} A {r*0.7} {r*0.7} 0 1 0 {cx+offset} {cy} Z"
