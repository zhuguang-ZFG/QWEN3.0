# LiMa 系统增强方案追踪器

> 本目录收录系统级增强方案。最新权威版本为 `LiMa_QWEN3_系统增强细化方案_v3_20260624.md`，`v2` 版本已归档为历史参考。
> 追踪状态截至 **2026-06-26**。

## 总览

| 维度 | 状态 |
|------|------|
| P0 必须完成 | 6/6 已完成或已落地 |
| P1 高优先级 | 6/6 已完成或已落地 |
| P2 中优先级 | 6/6 已完成或已落地 |
| P3 低优先级 / 探索 | 5/5 已完成或已落地，**P4 提示词系统增强未开始** |

---

## P0 — 必须完成

| 编号 | 标题 | 关键产物 | 状态 | 备注 |
|------|------|----------|------|------|
| P0-编码退役 | 编码能力全量退役 | 删除 `orchestrate*`、`eval_*`、`periodic_coding_eval`、`coding_backend_scorer`、`backends_constants_code_tools`、`context_pipeline` 编码上下文模块、`skills/code/`、`xiaozhi_v1_compat` | ✅ 已完成 | `classify_scenario()` 仍会在 IDE 请求返回 `"coding"`，属于历史残留，建议下一个切片清理 |
| P0-迁移补全 | 小智端点迁移到 device_app | `POST /device/v1/app/devices/manual-add`、`GET /device/v1/app/auth/captcha`、`PUT /device/v1/app/auth/change-password` | ✅ 已完成 | 依赖 `device_logic/captcha.py`、`device_logic/sms.py`、`device_logic/auth.py` |
| P0-X1~X8 | 小智兼容层退役 | 删除 `routes/xiaozhi_compat/`、`xiaozhi_v1_compat.py`；`routes/digital_human.py` 主路径指向 `data/digital-human/` | ✅ 已完成 | `esp32S_XYZ/server/.../digital-human/` 仍作为 fallback 保留 |
| P0-F1 | OTA 增强套件 | `device_ota/gradual.py`、`device_ota/rollback_monitor.py`、`device_ota/signature.py`、`/device/v1/admin/ota/gradual/*` | ✅ 已完成 | 含灰度发布、自动回滚监控、Ed25519 固件签名 |
| P0-M1 | 聊天历史实现 | `routes/device_app_chat.py`：`/devices/{id}/chat-sessions/{sid}/messages`、`/devices/{id}/chat-history` | ✅ 已完成 | — |
| P0-M2 | 实时设备状态 | `routes/device_app_status_ws.py`、`routes/device_app_api.py::_build_device_status` | ✅ 已完成 | — |

---

## P1 — 高优先级

| 编号 | 标题 | 关键产物 | 状态 | 备注 |
|------|------|----------|------|------|
| P1-L1~L6 | LiMa 能力补全自检 | `device_voice/__init__.py::self_check`、WS 语音端点、`routes/voice_pipeline_ws.py`、数字人、`routes/device_app_misc.py::provision/confirm`、OTA | ✅ 已完成 | L4 数字人主路径已迁移到 `data/digital-human/`；L5 配网端点已落地 |
| P1-F3 | 路径管线增强 | `device_gateway/path_pipeline.py`、`device_gateway/path_validator.py`、`device_gateway/profiles.py` | ✅ 已完成 | Edge-C `route_policy` 硬契约已支持 |
| P1-M3 | 任务模板 | `routes/device_app_task_templates.py` | ✅ 已完成 | — |
| P1-M6 | 任务预览 | `routes/device_app_tasks.py` 预览相关端点 | ✅ 已完成 | — |
| P1-M4 | 推送通知 | `device_logic/notifications.py` | ✅ 已完成 | — |
| P1-F2 | 协议版本管理 | `device_gateway/protocol_negotiator.py`、`device_gateway/protocol_frames.py` | ✅ 已完成 | — |

---

## P2 — 中优先级

| 编号 | 标题 | 关键产物 | 状态 | 备注 |
|------|------|----------|------|------|
| P2-F4 | 设备健康评分 | `device_gateway/health_scorer.py` / 相关健康指标 | ✅ 已完成 | 健康画像数据已接入 `backend_profile` 与 `health_tracker` |
| P2-M5 | 素材库 | `routes/device_app_misc.py` 素材路由、`scripts/init_assets.py` | ✅ 已完成 | — |
| P2-M7 | 设备分享 | `routes/device_app_sharing.py`、`device_logic/access.py::check_share_permission` | ✅ 已完成 | — |
| P2-M8 | 批量操作 | `routes/device_app_tasks.py` 批量端点 | ✅ 已完成 | — |
| P2-F5 | 固件远程证明 | `device_gateway/attestation.py`、`routes/device_ota.py` 固件哈希管理 | ✅ 已完成 | — |
| P2-F7 | 事件溯源增强 | `device_ledger/events.py`、`device_ledger/projection.py` | ✅ 已完成 | — |

---

## P3 — 低优先级 / 探索

| 编号 | 标题 | 关键产物 | 状态 | 备注 |
|------|------|----------|------|------|
| P3-F6 | 多设备协同 | `device_gateway/multi_device.py` / 协同绘制相关逻辑 | ✅ 已完成 | 能力已集成在设备任务与 route_policy 中 |
| P3-M9 | 设备发现配网 | `routes/device_app_misc.py::provision/confirm`、配对流程 | ✅ 已完成 | 与 L5 共享 `v2_pair_request` 表 |
| P3-M10 | 统计分析 | `routes/device_app_misc.py` 统计端点 | ✅ 已完成 | — |
| P3-F1-2 | 自动回滚监控 | `device_ota/rollback_monitor.py` | ✅ 已完成 | 与 F1-2 重复，已合并 |
| **P4** | **提示词系统强化** | `prompts/` 模板注册表、`routing/semantic_router.py`、Instructor 结构化输出、promptfoo 回归测试、语义缓存、LangGraph 状态可视化 | **⏸️ 未开始** | 唯一未启动的增强维度，建议作为下一个独立切片 |

---

## 推荐下一步

1. **（推荐）启动 P4-1 提示词模板注册表**：新建 `prompts/` 目录，将 `routing_classifier.py`、`routing_intent.py` 中的内联 system prompt 迁移到 YAML/JSON 模板，并添加运行时加载器。收益：提示词可热更新、可 A/B 测试、便于多语言维护。
2. **清理 `classify_scenario()` 的 `coding` 残留**：将 `routing_classifier.py::classify_scenario()` 永远返回 `"chat"`，并移除 `routes/v3_adapters.py`、`route_scorer.py`、`routing_selector/core.py` 等处的 `scenario == "coding"` 分支。

---

## 文档维护约定

- 新增切片实施前，先在本追踪器中新增一行并标记为 **🚧 进行中**。
- 切片完成后，更新状态为 **✅ 已完成**，并在 `STATUS.md` / `progress.md` 中记录验收证据。
- `v2.0` 方案为历史参考，不再更新；未来增量统一写入 `v3.x` 或独立切片 spec。
