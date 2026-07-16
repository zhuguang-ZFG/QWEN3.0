# 审查覆盖矩阵

审查基线：根仓库 `main@c8383a84244b81df4034d62c26e8b23ac78d69ca`；子模块
`esp32S_XYZ@5783e3c4c344a6b1d666e8659a782ed5979f0ba4`。审查期间保护子模块中既有的
`manager-mobile/src/manifest.json` 修改，不覆盖、不回退。

| 范围 | 生产入口/边界 | 审查方法 | 当前状态 |
| --- | --- | --- | --- |
| FastAPI 装配 | `server_dlc.py`、`dlc_api/`、`routes/` | 路由注册、lifespan、middleware、错误语义、全量测试 | 已审，复核候选中 |
| DLC 核心 | `dlc_core/`、`xiaozhi_drawing/` | 输入/schema/path/safety 到 dispatch 数据流、Bandit、测试 | 已审，无已确认高危 |
| 任务与设备状态 | `device_gateway/`、Redis/SQLite/in-memory | store 契约、CAS、并发、幂等、恢复、资源关闭 | 并行复核中 |
| 小程序 App API | `/device/v1/app/*`、`routes/device_app_*` | JWT、家庭/设备/任务/gallery 所有权、上传下载、限流 | 并行复核中 |
| 语音 | `device_voice/`、voice REST/WS/ticket | ticket、provider 超时、WS idle、取消与资源清理 | 并行复核中 |
| MCP | `dlc_mcp/` -> `/dlc/*` | HTTP 状态、鉴权、幂等、失败输出及直接测试 | 已确认非 2xx 候选，待冻结 |
| 部署 | `scripts/deploy_unified*.py`、`deploy/`、nginx/systemd | dry-run 文件集、备份/回滚、readiness、环境合并 | 已确认高危候选，二次复核中 |
| CI/供应链 | `.github/workflows/`、requirements、Docker | 权限、action pin、Bandit/pip-audit、锁定与生成物 | 并行复核中 |
| SDK/站点/文档 | `sdk/`、`docs-site/`、各 Web 目录 | 活跃 API、域名、端口、退役契约残留 | 并行复核中 |
| 小程序 | `esp32S_XYZ/.../manager-mobile` | type-check、i18n、lint、mp-weixin build、协议调用 | 门禁已跑；lint 红，待修 |
| U1-Grbl | `esp32S_XYZ/firmware/u1-grbl` | PlatformIO release build/native test、fz Host SIL | build 绿；native 配置红 |
| U8 固件 | `esp32S_XYZ/firmware/u8-xiaozhi` | 静态契约、native 测试可信度、IDF build preflight | 静态绿；IDF 环境阻塞 |
| 运动协议 | gateway/FakeDevice/U8/U1/fz | 云端到 U1 命令边界、fz protocol/hardware 分层证据 | protocol 绿；hardware harness 红 |
| 测试有效性 | `tests/`、子模块测试 | collect-only、skip/恒真/重实现、失败路径覆盖 | 已审，发现 U8 重实现测试缺口 |
| 代码质量 | Python/TS/C++ 活跃树 | ruff/format/pyright/size/lint | Python lint 绿；type/size/TS lint 有债 |
| 归档/工具树 | `docs/archive/`、IDE/Trellis、缓存 | 仅检查活跃引用和发布边界，不逐文件当生产代码审查 | 边界检查完成 |

## 已确认边界

- 自托管 `/device/v1/ws` 与旧聊天栈已退役；不恢复到 `server_dlc`。残留发布配置按“退役契约清理”评估。
- fz Host SIL 不等于纸路、蓝牙、OTA 或真机 HIL；任何最终结论保留该限制。
- 不连接/写入生产，不部署、不烧录、不提交、不推送。
