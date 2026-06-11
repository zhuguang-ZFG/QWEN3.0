"""图像转 SVG 路径转换器 - OpenCV 矢量化"""
import logging
from typing import Dict, Any
from io import BytesIO
import httpx
from PIL import Image
import numpy as np
import cv2

logger = logging.getLogger(__name__)


class SVGConverter:
    """图像 → SVG 路径转换器"""

    async def convert_url_to_svg(
        self,
        image_url: str,
        simplify_epsilon: float = 2.0,
        min_contour_area: int = 100
    ) -> Dict[str, Any]:
        """
        下载图片并转换为 SVG 路径（OpenCV 轮廓检测）

        Args:
            image_url: 图片 URL
            simplify_epsilon: 轮廓简化精度（像素）
            min_contour_area: 最小轮廓面积（过滤噪点）

        Returns:
            {
                'status': 'success' | 'failed',
                'svg_path': str,
                'width': int,
                'height': int,
                'contour_count': int,
                'error': str | None
            }
        """
        try:
            # 1. 下载图片
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(image_url)
                response.raise_for_status()
                image_data = BytesIO(response.content)

            # 2. 加载并预处理
            img = Image.open(image_data).convert('RGB')
            img.thumbnail((512, 512), Image.Resampling.LANCZOS)
            img_array = np.array(img)

            # 3. 灰度化
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

            # 4. 高斯模糊去噪
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)

            # 5. Otsu 二值化
            _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

            # 6. 查找轮廓
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # 7. 过滤和简化轮廓
            svg_paths = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < min_contour_area:
                    continue

                # 简化轮廓
                epsilon = simplify_epsilon
                approx = cv2.approxPolyDP(contour, epsilon, True)

                # 转换为 SVG path
                if len(approx) >= 3:
                    path = self._contour_to_svg_path(approx)
                    svg_paths.append(path)

            if not svg_paths:
                # 无有效轮廓，返回边界框
                h, w = gray.shape
                svg_paths = [f"M 0 0 L {w} 0 L {w} {h} L 0 {h} Z"]

            # 8. 合并路径
            svg_path = " ".join(svg_paths)
            h, w = gray.shape

            return {
                'status': 'success',
                'svg_path': svg_path,
                'width': w,
                'height': h,
                'contour_count': len(svg_paths),
                'error': None
            }

        except httpx.HTTPError as e:
            logger.error(f"下载图片失败: {e}")
            return {'status': 'failed', 'svg_path': '', 'width': 0, 'height': 0, 'contour_count': 0, 'error': f"Download failed: {e}"}
        except Exception as e:
            logger.error(f"转换失败: {e}")
            return {'status': 'failed', 'svg_path': '', 'width': 0, 'height': 0, 'contour_count': 0, 'error': str(e)}

    def _contour_to_svg_path(self, contour: np.ndarray) -> str:
        """将 OpenCV 轮廓转换为 SVG path"""
        points = contour.reshape(-1, 2)
        if len(points) == 0:
            return ""

        # M x y L x y ... Z
        path_parts = [f"M {points[0][0]} {points[0][1]}"]
        for x, y in points[1:]:
            path_parts.append(f"L {x} {y}")
        path_parts.append("Z")

        return " ".join(path_parts)
