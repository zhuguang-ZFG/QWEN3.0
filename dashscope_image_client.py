"""DashScope 图生 API 客户端封装"""

import os
import logging
from typing import Optional, Dict, Any
import dashscope
from dashscope import ImageSynthesis

logger = logging.getLogger(__name__)


class DashScopeImageClient:
    """DashScope 图生 API 客户端（Wanx/Flux）"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ALIYUN_API_KEY", "")
        if self.api_key:
            dashscope.api_key = self.api_key

    def generate(
        self,
        prompt: str,
        model: str = "wanx-v1",
        negative_prompt: Optional[str] = None,
        size: str = "1024*1024",
        n: int = 1,
        **kwargs,
    ) -> Dict[str, Any]:
        """生成图片（同步）"""
        try:
            rsp = ImageSynthesis.call(
                model=model,
                prompt=prompt,
                negative_prompt=negative_prompt,
                n=n,
                size=size,
                api_key=self.api_key,
                **kwargs,
            )
            return self._parse_response(rsp)
        except Exception as e:
            logger.error(f"DashScope 图生失败: {e}")
            return {"status": "failed", "images": [], "task_id": "", "error": str(e)}

    def _parse_response(self, rsp) -> Dict[str, Any]:
        """解析 API 响应"""
        if rsp.status_code == 200:
            output = rsp.output
            results = output.get("results", [])
            return {
                "status": "success",
                "images": [{"url": r["url"]} for r in results],
                "task_id": output.get("task_id", ""),
                "error": None,
            }
        return {"status": "failed", "images": [], "task_id": "", "error": f"API error: {rsp.code} {rsp.message}"}

    async def generate_async(self, prompt: str, model: str = "wanx-v1", **kwargs) -> Dict[str, Any]:
        """异步生成图片（提交任务，返回 task_id）"""
        try:
            rsp = ImageSynthesis.async_call(model=model, prompt=prompt, api_key=self.api_key, **kwargs)

            if rsp.status_code == 200:
                return {"status": "pending", "task_id": rsp.output["task_id"], "error": None}
            else:
                return {"status": "failed", "task_id": "", "error": f"API error: {rsp.code} {rsp.message}"}
        except Exception as e:
            logger.error(f"DashScope 异步图生失败: {e}")
            return {"status": "failed", "task_id": "", "error": str(e)}

    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        """查询异步任务结果"""
        try:
            rsp = ImageSynthesis.fetch(task_id)

            if rsp.status_code == 200:
                output = rsp.output
                task_status = output.get("task_status", "")

                if task_status == "SUCCEEDED":
                    results = output.get("results", [])
                    return {
                        "status": "success",
                        "images": [{"url": r["url"]} for r in results],
                        "task_id": task_id,
                        "error": None,
                    }
                elif task_status in ["PENDING", "RUNNING"]:
                    return {"status": "pending", "images": [], "task_id": task_id, "error": None}
                else:
                    return {"status": "failed", "images": [], "task_id": task_id, "error": f"Task {task_status}"}
            else:
                return {
                    "status": "failed",
                    "images": [],
                    "task_id": task_id,
                    "error": f"API error: {rsp.code} {rsp.message}",
                }
        except Exception as e:
            logger.error(f"查询任务失败: {e}")
            return {"status": "failed", "images": [], "task_id": task_id, "error": str(e)}
