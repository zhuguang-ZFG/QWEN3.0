"""MCP tool schemas exposed by the DLC drawing server."""

from __future__ import annotations

TOOLS = {
    "dlc.write_text": {
        "description": "在绘图机上书写指定文本。需要 device_id 和 text。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "目标绘图机设备 ID"},
                "text": {"type": "string", "description": "要书写的文本"},
            },
            "required": ["device_id", "text"],
        },
    },
    "dlc.draw_generated": {
        "description": "根据提示词 AI 生成图像并在绘图机上绘制。需要 device_id 和 prompt。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "目标绘图机设备 ID"},
                "prompt": {"type": "string", "description": "绘画提示词"},
            },
            "required": ["device_id", "prompt"],
        },
    },
    "dlc.draw_from_image": {
        "description": "将指定图片 URL 矢量化并在绘图机上绘制。需要 device_id 和 image_url。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "目标绘图机设备 ID"},
                "image_url": {"type": "string", "description": "图片 URL（http/https）"},
            },
            "required": ["device_id", "image_url"],
        },
    },
    "dlc.get_device_status": {
        "description": "查询绘图机当前状态（在线/工作/任务/影子）。需要 device_id。",
        "inputSchema": {
            "type": "object",
            "properties": {"device_id": {"type": "string", "description": "目标绘图机设备 ID"}},
            "required": ["device_id"],
        },
    },
}
