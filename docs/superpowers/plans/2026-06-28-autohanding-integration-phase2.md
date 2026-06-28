# autohanding.com 仿手写集成 Phase 2 执行计划

## 目标

为 LiMa 提供可直接操作的仿手写 Web UI，支持文字输入、字体/纸张/参数选择、SVG 预览，以及一键下发到已绑定设备。

## 任务清单

### Task 1 — 后端选项端点

- 在 `routes/handwriting.py` 新增 `GET /device/v1/app/handwriting/options`，返回字体、纸张、默认值与最大字数，避免前端硬编码。

### Task 2 — Chat Web 手写页面

- 新增 `chat-web/handwriting.html`：
  - 与现有控制台一致的侧边栏导航（对话 / 设备 / 仿手写 / API Key / 用量）。
  - 表单：文字输入框（字数计数）、字体选择、纸张选择、涂改概率/潦草程度/字形随机性滑块。
  - 模式切换："预览 SVG" / "下发设备"。
  - 下发模式显示已绑定设备选择框。
  - 结果区：SVG 预览（白色背景、黑色笔迹）或任务下发结果。
- 新增 `chat-web/js/handwriting.js`：
  - 调用 `/handwriting/options` 填充选项。
  - 调用 `/handwriting` 生成 SVG 预览。
  - 调用 `/devices/{id}/tasks` 以 `capability=handwriting` 下发任务。

### Task 3 — 部署脚本修复

- `scripts/deploy_chat_web.py`：
  - 加载 `.env`，确保 `LIMA_DEPLOY_PASS` 可用。
  - 捕获 `paramiko.AuthenticationException` 后回退密码登录。
  - 将 `handwriting.html` 与 `js/handwriting.js` 加入 `FILES` 列表。

### Task 4 — 导航与测试

- 在 `chat-web/devices.html` 侧边栏增加“仿手写”入口。
- 新增/更新测试覆盖 `/handwriting/options` 端点。
- 运行 `ruff check`、`check_code_size`、聚焦/全量 pytest。

### Task 5 — 部署验证

- `scripts/deploy_unified.py --slice core` 部署后端。
- `scripts/deploy_chat_web.py` 部署静态页面。
- 公网访问 `https://chat.donglicao.com/handwriting.html` 确认页面可达；VPS 日志确认 `/handwriting/options` 返回 401/200。

## 退出标准

- `/handwriting/options` 接口在线。
- `chat-web/handwriting.html` 可通过公网访问。
- 页面能加载字体/纸张选项并渲染 SVG 预览（本地/测试环境 mock）。
- 代码体积与 lint 门禁通过，相关测试通过。
