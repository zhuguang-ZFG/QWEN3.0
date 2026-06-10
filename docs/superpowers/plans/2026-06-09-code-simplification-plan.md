# LiMa 代码精简与退役适配清理计划

**日期**：2026-06-09
**状态**：执行中
**优先级**：P0 - 战略转型基础清理
**Owner**：zhuguang-ZFG

---

## 一、背景

LiMa 已从“个人编码助手后端”转向“AI 智能设备统一云端服务”。当前清理目标不是删除所有代码能力，而是移除已经退役的旧适配路径，避免后续深度适配 AI 画图机/写字机时继续被历史命名、旧 CLI、旧本地状态目录误导。

本计划替换早期乱码版本。早期版本中“按行数删除 Anthropic、质量门、语义缓存、Agent 编排”等判断已经过时；这些模块目前仍可能服务通用 Chat API、OpenAI/Anthropic 兼容层、设备云端任务编排或质量控制，不再作为本轮删除对象。

---

## 二、清理边界

### 需要清理

- 退役的本地 CLI / Worker 品牌残留。
- 旧本地运行目录与输出文件，例如 `.lima-code/`、`launch_lima.js`、`lima_out.txt`、`lima_err.txt`。
- 当前文档中的乱码、过时删除计划、旧路径验证说明。
- 非归档路径中会误导后续开发的旧命名。

### 暂不清理

- `docs/archive/**` 中的历史材料。
- `STATUS.md`、`progress.md`、`findings.md`、`docs/LIMA_MEMORY*.md` 中的历史证据。
- `model="code"`、通用 coding route、质量门、Anthropic 兼容接口、Agent Task / Agent Worker。
- `tests/test_chat_route_prefs.py` 中针对退役别名的兼容断言。
- `tests/test_repo_hygiene.py` 中阻止旧子模块重新进入索引的断言。

---

## 三、当前执行项

- [x] 删除旧 LiMa 本地启动/输出文件：`launch_lima.js`、`lima_out.txt`、`lima_err.txt`。
- [x] `.gitignore` 移除退役 CLI 路径，保留通用 `.lima-worker/dev/`。
- [x] `worker_daemon.py` 默认状态文件迁移到 `.lima-worker/dev/`。
- [x] 用户可见文案从旧 Worker 品牌改为通用 `Agent Worker`。
- [x] 当前工作区清洁规则文档改为中文 UTF-8，并记录不得重新引入旧 CLI / 旧目录。
- [x] 当前任务计划更新为 AI 智能设备云端服务方向。
- [x] 修复本计划文档乱码与过时删除清单。
- [ ] 复查非归档路径旧命名命中，只保留历史证据和测试兼容断言。
- [ ] 运行聚焦测试与格式检查。
- [ ] 仅暂存本轮相关文件并提交推送。

---

## 四、验证命令

```powershell
python -m pytest tests/test_chat_route_prefs.py tests/test_repo_hygiene.py -q
python scripts/run_ruff_check.py
git diff --check
```

同时执行退役命名扫描，排除归档目录和长期历史证据文档；扫描结果只应剩下“禁止重新引入旧路径”的规则说明，以及兼容测试中的退役别名断言。

---

## 五、后续方向

清理完成后，项目应以设备云端服务为主线推进：

1. 优先完善 `esp32S_XYZ` 的设备接入、任务状态、固件-云端协议和验收文档。
2. 把画图机/写字机抽象为设备任务能力，而不是恢复旧编码助手 CLI。
3. 保持模型路由、预算、健康度、质量门和 Agent Worker 为通用基础设施。
4. 新增设备能力前先更新中文设计文档，再做代码、测试、部署与真实端到端验证。
