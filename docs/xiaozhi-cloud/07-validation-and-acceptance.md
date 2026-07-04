# 验证与验收矩阵（P0–P4）

> 当前主路线：**在 `D:/QWEN3.0` 内瘦身出 `dlc_core / dlc_api / dlc_mcp`。**
> 关联入口：`docs/xiaozhi-cloud/README.md`
> 关联路线图：`docs/xiaozhi-cloud/00-roadmap.md`
> 关联证据：`docs/xiaozhi-cloud/09-p0-evidence.md`

---

## 1. 本文件的角色

本文件给每个阶段提供**可勾选的验收矩阵**，明确：

- 每阶段验什么
- 用什么命令/操作验
- 通过标准是什么
- 哪些必须真机验证，不能用本地假设备冒充

原则（来自 `AGENTS.md`）：**本地假设备验证不等于真机发布证据。** 涉及真实运动、激光、OTA、配置写入的能力，必须单独做硬件验证。

---

## 2. 通用门禁命令

每次改服务端代码，提交前必须过（来自 `AGENTS.md`）：

```powershell
# 聚焦测试
python -m pytest tests/<改动相关文件> -v

# 完整测试
python -m pytest --tb=short -q

# 静态检查
ruff check .
ruff format --check
pyright <改动文件>
python scripts/check_code_size.py
```

---

## 3. P0 验收矩阵（已完成）

| 项 | 验证方式 | 通过标准 | 状态 |
|----|----------|----------|------|
| `dlc_api` 健康 | `curl http://127.0.0.1:18080/health` | 返回 `{"status":"ok",...}` | ✅ 已验证 |
| `/write` 提交 | POST `/write` | 返回 `task_id` | ✅ 已验证 |
| `dlc_mcp` tools/list | echo JSON-RPC 管道 | 列出 `dlc.write_text`/`dlc.draw_generated` | ✅ 已验证 |
| 官方云 discovery | `mcp_pipe` 连 wss endpoint | broker 发现两个 tool | ✅ 已验证 |
| UTF-8 输出 | `tests/test_dlc_mcp_server.py::test_main_stdout_is_valid_utf8_json` | 子进程 stdout 是合法 UTF-8 | ✅ 已验证 |
| 聚焦测试 | `pytest tests/test_dlc_*` | 13 passed | ✅ 已验证 |
| ruff | `ruff check dlc_api dlc_mcp tests/...` | passed | ✅ 已验证 |

详细证据见 `09-p0-evidence.md`。

---

## 4. P1 验收矩阵（接口与核心闭环）

| 项 | 验证方式 | 通过标准 | 状态 |
|----|----------|----------|------|
| `dlc_core` 模块边界冻结 | `02-service-refactor.md` §3 接口冻结确认 | 接口签名不再变动 | ✅ 已冻结 |
| `intent` 分类 | `tests/test_dlc_core_*.py` + `dlc_core/intent.py` | facade 能解析 write_text/draw | ✅ 已验证 |
| `text_to_path` | `tests/test_dlc_core_write.py` | 返回 path_data / preview_svg | ✅ 已验证 |
| `path_validator` | `tests/test_dlc_core_safety.py` | 常量统一为 `MAX_PATH_POINTS=200` | ✅ 已验证 |
| `dlc_api` 新路由 | `tests/test_dlc_api.py` | `/dlc/tasks/preview`、`/dlc/tasks/dispatch` 可访问；`/write`、`/draw` 404 | ✅ 已验证 |
| `dlc_mcp` tool 切换 | `tests/test_dlc_mcp_server.py` | tool 调 `/dlc/tasks/dispatch` | ✅ 已验证 |
| 写字闭环 | `dlc.write_text` → `/dlc/tasks/dispatch` → `dlc_core.write` | 返回 `queued` + `task_id` | ✅ 已验证（mock） |
| 预设图形闭环 | `dlc.draw_generated` + prompt「圆」 | 返回 `preset:circle` | ✅ 已验证（mock） |
| `draw_generated` 路线决策 | `08-open-questions.md` Q-02 | 明确降级为预设图形优先 | ✅ 已决策 |
| 代码检查 | `ruff check dlc_core dlc_api dlc_mcp tests/test_dlc_*.py` | All checks passed | ✅ 已验证 |
| 类型检查 | `pyright dlc_core dlc_api dlc_mcp` | 0 errors | ✅ 已验证 |

**P1 不要求真机。** 允许假设备 + 单元测试。

详细证据见 `10-p1-evidence.md`。

---

## 5. P2 验收矩阵（固件与小程序接入）

| 项 | 验证方式 | 通过标准 | 真机? |
|----|----------|----------|-------|
| `motion_busy_` 防呆 | 固件单测 + 双任务并发 | 第二个任务被拒 `device is busy` | ✅ 真机 |
| `self.plotter.write_text` | 固件 tool 注册确认 | tools/list 可见 | ✅ 真机 |
| U8→U1 UART 写字 | 真机跑一条写字路径 | U1 返回 DONE，笔迹正确 | ✅ 真机 |
| PATH 序列完整性 | 真机连续路径 | 无乱序/丢段 | ✅ 真机 |
| 小程序登录 | 微信一键登录 | 拿到 token | 小程序 |
| 一键配网 | BLE Blufi / SoftAP fallback | 设备联网并绑定账户 | ✅ 真机 |
| 状态页 | `/devices/{id}/status` + WS | 在线/工作中/任务进度实时 | 小程序 |
| 写画入口 | `write-draw-panel.vue` 提交任务 | 任务下发成功 | 小程序 |

**P2 必须真机验证运动、配网、UART。**

---

## 6. P3 验收矩阵（安全与可运维）

| 项 | 验证方式 | 通过标准 |
|----|----------|----------|
| 失败重试 | 注入 `E_UART_TIMEOUT` | 按 recovery.py 重试 2 次 |
| 死信 | 重试耗尽 | 标记 dead_letter + artifact 落盘 90 天 |
| device_busy 拒绝 | 设备忙时下发 | 返回 `rejected/device_busy` |
| 路径越界拒绝 | 越界路径 | `E_PATH_OUT_OF_BOUNDS` 停止 |
| 双云部署 | `deploy_unified.py --slice core` | 阿里云入口 + JDCloud 数据正常 |
| 公网健康 | `verify_production_deploy.py` | 真实域名 + token 通过 |
| 回滚 | 备份恢复演练 | 可回退到上一版本 |

**P3 公网 API 必须用真实域名 + 真实 token 验证（`AGENTS.md` 硬规则）。**

---

## 7. P4 验收矩阵（LiMa 收缩）

| 项 | 验证方式 | 通过标准 |
|----|----------|----------|
| 旧链路删除前置条件 | 检查 P1–P3 全绿 | 新链路稳定运行 |
| 删除 chat/routing 子系统 | `codegraph impact` + `codegraph_orphans` | 无活跃引用 |
| 文档入口切换 | README 导航 | 全部指向新体系 |
| 删除后回归 | 完整 pytest + 真机冒烟 | 无回归 |
| 用户确认 | 明确授权 | 用户同意大范围瘦身 |

**P4 删除前必须用户明确授权（`AGENTS.md` 硬规则）。**

---

## 8. 真机 vs 假设备边界

| 能力类别 | 本地假设备够吗 | 说明 |
|----------|---------------|------|
| intent/path/validator 单元逻辑 | ✅ 够 | 纯函数 |
| MCP discovery / tools/call 协议 | ✅ 够 | 协议层 |
| 任务队列 queued/dispatch | ✅ 够 | Redis 逻辑 |
| 真实运动/写字/画图 | ❌ 必须真机 | 涉及电机/舵机 |
| 激光 | ❌ 必须真机 | 安全关键 |
| OTA 升级 | ❌ 必须真机 | 不可回退风险 |
| 配网写 NVS | ❌ 必须真机 | 设备侧持久化 |
| 公网 API | ❌ 必须真实域名 | localhost 不算 |

---

## 9. 阶段进入门禁总表

| 阶段 | 进入条件 |
|------|----------|
| P1 | P0 证据收口 + 主路线统一 |
| P2 | 服务端接口冻结 + 固件/小程序依赖输入明确 |
| P3 | 真机基础路径成功 + 用户链路明确 |
| P4 | 新链路稳定 + 文档/测试/部署完整 + 用户授权 |

---

## 10. 当前状态

- **P0：已完成并有证据。**
- **文档收口（D1–D3）+ 专业分册（D2）：本轮完成。**
- 下一步真正落地应从 **P1 接口冻结与核心闭环** 开始，而不是继续写文档。
