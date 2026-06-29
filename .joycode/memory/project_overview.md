---
name: project_overview
description: LiMa项目概览 - AI路由服务器与智能硬件云平台
type: project
---

LiMa（力码）是深圳市动力巢科技有限公司的AI智能硬件云端服务平台。

**核心定位：**
- 多后端AI路由服务器：智能路由到170+个AI后端（Groq、NVIDIA、OpenRouter、DeepSeek、Cloudflare、阿里云等）
- 智能硬件云平台：为ESP32绘图机/写字机/2D数字人提供任务派发、路径规划、状态监控与OTA
- 公网入口：https://chat.donglicao.com

**技术栈：** Python 3.10 + FastAPI + uvicorn + httpx + SQLite + Redis

**关键架构决策：**
- routing_engine.route() 是唯一路由权威入口，13步管线处理
- 后端注册在 backends_registry/ 包，按provider分文件
- 设备网关通过Redis任务队列 + WebSocket/MQTT与ESP32通信
- 会话记忆系统支持长期记忆、学习循环、脱敏压缩

**Why:** 理解项目整体架构有助于后续开发时快速定位模块
**How to apply:** 修改代码时参考请求管线文档，确保不破坏权威路径