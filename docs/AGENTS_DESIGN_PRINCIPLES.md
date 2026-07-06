# LiMa 设计第二原则

> 本文件是 LiMa 仓库的**第二开发原则**，仅次于 [`docs/AGENTS_PONYTAIL.md`](AGENTS_PONYTAIL.md) 所定义的 Ponytail 第一原则。
>
> 当 Ponytail 第一原则与本文件冲突时，以 Ponytail 为准；但 Ponytail 也不得绕过 LiMa 硬规则（输入验证、错误处理、安全措施、测试门禁、文档同步、Git 规则）。

---

## 原则总览

| 原则 | 核心含义 | LiMa 场景关键词 |
|------|----------|-----------------|
| 单一职责 SRP | 一个类/模块只应有一个引起变化的原因 | `dlc_core` 只负责路径算法；`dlc_api` 只负责 HTTP；`dlc_mcp` 只负责 MCP 适配 |
| 开闭 OCP | 对扩展开放，对修改关闭 | 新增 MCP tool 通过 `dlc_mcp/server.py` 的 `TOOLS`/`TOOL_HANDLERS` 注册，不修改 `dlc_core`；新增设备能力通过 `device_gateway` 的 capability 白名单扩展 |
| 里氏替换 LSP | 子类可透明替换基类 | `PathValidator` 统一 `validate(path) -> ValidationResult` 接口，不同运动边界实现可互换 |
| 接口隔离 ISP | 客户端不应依赖不需要的接口 | `dlc.validate_path` 与 `dlc.dispatch_task` 分离，设备端不强制实现预览接口 |
| 依赖倒置 DIP | 面向接口/抽象编程，高层不依赖低层 | `dlc_core` 通过 `handle_draw`/`handle_write` 等函数抽象暴露能力，`dlc_api`/`dlc_mcp` 依赖这些抽象而非具体实现 |
| 迪米特 LoD | 最少知道原则，减少模块间直接交互 | 设备端只认识 `dlc_api`，不直接访问 `device_draw_handler` 内部 |
| 合成复用 CRP | 优先组合/聚合，而非继承 | `dlc_mcp` 组合 `dlc_core` 能力，而不是继承绘图类 |
| 清晰指令 | 提示、接口、配置语义明确无歧义 | MCP tool 的 `inputSchema` 必填/类型/范围完整；环境变量命名自解释 |
| 精简上下文 | 只传递必要上下文，主动压缩 | Agent 会话中用 Headroom 压缩大输出；函数入参避免把整个 `request` 对象传下去 |
| 健壮工具接口 | 简单、幂等、无歧义、失败可观测 | HTTP API 返回统一 `{status, error, data}`；工具调用失败返回明确错误码 |
| 自动化验证循环 | 每次改动后有编译/测试/静态检查闭环 | `ruff` + `pyright` + `pytest` + `check_code_size.py` |

---

## 1. 单一职责原则（SRP）

> “术业有专攻”。一个模块应该只做一件事，并做好它。

### LiMa 示例

- `dlc_core/`：纯路径算法（`text_to_path`、`svg_path_to_motion`、`validate_path`），无 HTTP、无 MCP、无数据库。
- `dlc_api/`：FastAPI HTTP 入口，负责鉴权、路由、序列化，不实现算法。
- `dlc_mcp/`：MCP 协议适配，负责 tool 注册/调用分发，不实现算法。
- `device_gateway/`：设备通信协议（WebSocket/MQTT），不实现路径生成。

### 反例

不要把 `dashscope` 图片生成、`grbl` 串口下发、HTTP 鉴权全部塞进一个 `device_draw_handler.py`。

---

## 2. 开闭原则（OCP）

> 通过增加新代码扩展功能，而不是修改已有代码。

### LiMa 示例

- 新增 MCP tool：在 `dlc_mcp/server.py` 的 `TOOLS`/`TOOL_HANDLERS` 中追加条目，不修改 `dlc_core`。
- 新增设备能力：在固件中新增 `AddTool("self.plotter.xxx")`，不修改现有 `self.plotter.write_text`。
- 新增图形预设：在 `dlc_core/presets.py` 增加新图形函数，不修改 `handle_draw` 主流程。

---

## 3. 里氏替换原则（LSP）

> 所有引用基类的地方，必须能透明使用子类对象。

### LiMa 示例

- `DeviceTaskStore` 抽象定义入队/出队/状态接口；`InMemoryDeviceTaskStore` 与 Redis 后端实现可互换（测试用内存、生产用 Redis）。
- `PathValidator` 基类定义 `validate(path) -> ValidationResult`；不同运动边界实现可互换。

---

## 4. 接口隔离原则（ISP）

> 客户端不应依赖它不需要的接口。

### LiMa 示例

- 设备端 MCP tool 暴露：
  - `self.plotter.write_text`（写字）
  - `self.plotter.draw_generated`（绘图）
  - `self.plotter.run_path`（执行路径）
  - 不强制暴露 `self.plotter.preview_svg` 等调试接口。
- `dlc_api` 路由：
  - `/dlc/tasks/preview` 供小程序预览
  - `/dlc/tasks/dispatch` 供固件/小程序下发
  - 不把管理接口混入公共设备接口。

---

## 5. 依赖倒置原则（DIP）

> 高层模块不依赖低层模块，二者都依赖抽象。

### LiMa 示例

- `dlc_api` 路由依赖 `dlc_core` 的函数签名（`handle_draw`/`handle_write`/`dispatch_task`），不依赖具体路径算法实现。
- `dlc_mcp` 依赖 `dlc_core` 的函数签名，不依赖具体算法实现。
- 测试用 `FakePathValidator` 替换真实校验器，不修改被测代码。

---

## 6. 迪米特法则（LoD）

> 一个实体应当尽量少地与其他实体发生直接相互作用。

### LiMa 示例

- 设备端只通过 `dlc_api` 获取路径，不直接访问 `device_draw_handler` 的内部函数。
- 小程序只调用 `v2SubmitTask(deviceId, type, params)`，不直接操作设备网关队列。
- `dlc_core` 不读取 `.env`，配置由调用方注入。

---

## 7. 合成复用原则（CRP）

> 优先使用对象组合/聚合，而非继承。

### LiMa 示例

- `dlc_mcp` 组合 `dlc_core.handle_write` / `handle_draw` / `validate_path`，不继承它们。
- `dlc_api` 通过依赖注入组合 `dlc_core` 能力。
- 固件 `Plotter` 类组合 `HttpClient` 和 `GrblWriter`，不继承网络或串口类。

---

## 8. 清晰指令

> 提示、接口、配置语义明确无歧义。

### LiMa 示例

- MCP tool 的 `inputSchema` 明确：
  - `type: object`
  - `required: ["text"]`
  - `properties.text.type: string`
  - `properties.text.minLength: 1`
  - `properties.text.maxLength: 40`
- 环境变量命名：`DLC_API_TOKEN`、`MCP_ENDPOINT`、`XIAOZHI_MCP_TOKEN`，避免 `TOKEN1`、`TOKEN2`。
- 错误响应：`{"status": "error", "code": "PATH_OUT_OF_BOUNDS", "message": "..."}`。

---

## 9. 精简上下文管理

> 只传递必要上下文，主动压缩冗余信息。

### LiMa 示例

- Agent 会话中，大输出先用 Headroom 压缩再推理。
- 函数入参只传 `path: list[Point]`，不传整个 `request` 对象。
- 日志只记录关键字段（device_id、task_id、status），不记录完整消息体。

---

## 10. 健壮工具接口

> 简单、幂等、无歧义、失败可观测。

### LiMa 示例

- `/dlc/tasks/dispatch` 幂等：同一 `task_id` 重复调用返回同一结果，不重复执行。
- `/health` 与 `/health/ready` 分离：liveness vs readiness。
- 工具调用失败返回结构化错误，不抛裸异常，不吞掉错误。

---

## 11. 自动化验证循环

> 每次改动后必须经过编译、测试、静态检查闭环。

### LiMa 标准循环

```bash
# 1. 聚焦测试
python -m pytest tests/<相关文件> -v

# 2. 全量测试（生产改动）
python -m pytest --tb=short -q

# 3. 静态检查
ruff check .
ruff format --check
pyright <改动文件>

# 4. 代码大小检查
python scripts/check_code_size.py
```

---

## 自检问题

在架构决策或编码前，问自己：

1. 这个模块是否只负责一件事？（SRP）
2. 能否不修改现有代码就扩展功能？（OCP）
3. 子类能否无感替换基类？（LSP）
4. 客户端是否被迫依赖不需要的接口？（ISP）
5. 高层模块是否依赖具体实现？（DIP）
6. 这个模块是否知道太多其他模块的细节？（LoD）
7. 这里用组合是否比继承更合适？（CRP）
8. 接口/配置/错误信息是否清晰无歧义？
9. 上下文是否可以再精简？
10. 这个接口是否幂等、可观测、失败可追踪？
11. 改动后能否跑通测试 + 静态检查闭环？
