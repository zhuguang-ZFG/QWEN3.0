# 写字机轻量后端方案

> 日期：2026-06-09
> 更新：2026-06-10，替换无效编码旧文档并移除退役适配残留
> 状态：当前方案文档
> 范围：AI 画图/写字机的轻量化 LiMa 后端形态

## 目标

为 `esp32S_XYZ` 写字机提供一个轻量、可部署、可观测的 LiMa 后端：

- 保留 OpenAI/Anthropic 兼容 API，方便继续复用现有路由能力；
- 设备侧通过 `/device/v1/*` 与 LiMa 交互；
- 后端优先做任务规划、路径校验、任务队列和运行证据；
- 真实运动执行仍由 `esp32S_XYZ` U8/U1 固件负责；
- 不引入与画图/写字无关的编码助手协议适配。

## 轻量化原则

1. 设备控制优先确定性解析。
2. 普通写字优先模板和本地路径算法。
3. AI 只进入创意规划、图像生成、解释和恢复等需要模型的环节。
4. 所有模型输出必须转换成受控 JSON 或受校验路径。
5. `route_policy` 是云端路由到设备任务之间的解释边界。
6. 发布证据必须区分云端健康、假设备验证和真实硬件验证。

## 后端能力

| 能力 | 当前策略 |
|---|---|
| 文本写字 | 清洗文本、限制长度、选择布局和模板 |
| 创意写字 | 文本模型生成受控规划，路径仍由校验器把关 |
| 简笔画 | 预设 asset 优先，必要时走已准入图像/向量模型 |
| 图片临摹 | 图像预处理、轮廓提取、点数/边界/运行时限制 |
| 控制命令 | 停止、暂停、继续、回零等不调用模型 |
| 任务队列 | Redis-backed task store + WebSocket 下发 |
| 运行证据 | 任务账本、artifact、motion_event、终态记录 |
| 模型路由 | SCNet/Groq/Cloudflare 等低成本或免费后端按证据准入 |

## 不再包含的内容

- 不再适配退役的编码助手协议。
- 不再保留专用编码助手路由、测试、脚本、缓存和参考源码。
- 不把代码编辑、仓库问答、多文件修改等能力放入写字机热路径。
- 不因为某个外部工具可用就把它升级为设备能力。

## 运行拓扑

```text
用户语音/文字/网页
  -> LiMa /device/v1/*
  -> 任务分类和 route_policy
  -> 生成或选择路径
  -> 校验/预览/artifact
  -> Redis task store
  -> U8 WebSocket
  -> U1 确定性运动执行
  -> motion_event / terminal result
```

## 与完整 LiMa 的关系

轻量后端不是独立项目，而是 LiMa 的设备优先部署形态：

- 继续使用 `server.py`、`routes/route_registry.py`、`device_gateway/`；
- 继续使用 `routing_engine.route()` 和 `http_caller` 处理需要模型的请求；
- 继续使用 `observability/`、`health_tracker.py`、`budget_manager.py`；
- 不复活已退役的编码助手专用适配层；
- 不绕过 `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE.md` 的模型准入规则。

## 阶段计划

### 阶段 1：设备任务闭环

- `route_policy` 随 `motion_task` 下发；
- fake U8 消费并回传 route policy；
- device artifact 记录路由证据；
- 控制、写字、绘图、校验失败都有测试。

### 阶段 2：模型准入

- 建立 `docs/model_admission/` 报告；
- 分角色评估 intent parser、text planner、image generator、vectorizer；
- 未通过几何校验的模型不能进入热路径；
- direct LLM-to-SVG 保持实验状态。

### 阶段 3：硬件发布门禁

- 假 U8/U1 先通过；
- 再做真实板卡验证；
- 记录固件版本、板卡版本、路径点数、运行时、终态事件和回滚策略；
- 云端健康不能替代硬件证据。

## 验证命令

LiMa 侧：

```powershell
python -m pytest tests/test_device_gateway_model_routing.py tests/test_device_gateway_protocol.py -q
python scripts/run_ruff_check.py
git diff --check
```

产品侧：

```powershell
cd D:\QWEN3.0\esp32S_XYZ
python tools\validate_schemas.py
python -m unittest tests.ci.test_validate_schemas -v
python -m unittest tools.fake_lima_u8.tests.test_app -v
```

部署侧：

```powershell
python scripts/deploy_unified.py
curl -sf https://chat.donglicao.com/health
curl -sf https://chat.donglicao.com/device/v1/health
```

## 关联文档

- `docs/PROJECT_OPTIMIZATION_ROADMAP.md`
- `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE.md`
- `docs/ESP32S_XYZ_MANAGEMENT.md`
- `docs/REQUEST_PIPELINE_AUTHORITY.md`
- `docs/superpowers/plans/2026-06-09-ai-drawing-writing-robot.md`
