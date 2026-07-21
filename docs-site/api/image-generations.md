# 图像生成

> 更新日期：2026-07-21

设备绘图主路径为 **DLC `draw_generated` / 描图**（DashScope 等），经 `device_gateway` 矢量化后下发，**不是** 通用 OpenAI `/v1/images/generations` 多后端路由。

- 小程序 / 设备任务：见 [设备控制](/api/device-control)
- 仓库实现：`device_gateway/device_draw_handler.py`、`dlc_core/`

历史 Pollinations 兼容页已退役（git history）。
