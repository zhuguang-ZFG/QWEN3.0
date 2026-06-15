# esp32S_XYZ 管理

> 更新时间: 2026-06-15

## 目的

`esp32S_XYZ` 是 LiMa 的一级下游产品发行版。它包含双 ESP32-S3 板项目、固件基线、小智/管理服务、设备模式、监控、假设备工具和硬件证据。

主 LiMa 仓库通过 `esp32S_XYZ` 子模块来管理它，因为 LiMa 将作为该产品的 AI/后端控制平面，但设备项目必须保留自己的源历史记录和发布流程。

LiMa 还被授权在产品仓库内部进行深度优化和基于证据的重构，当这是改进后端集成、可靠性、可测试性或硬件发布就绪性的正确方法时。优化过程在 `docs/ESP32S_XYZ_OPTIMIZATION_ROADMAP.md` 中跟踪。

## 边界

LiMa 拥有：

- 模型路由、AI 后端选择、记忆、安全策略和后端健康；
- 产品使用的 VPS 托管的公共/私有端点；
- API 密钥和提供商密钥保管；
- 跨仓库集成记录和发布证据；
- 用于 LiMa 兼容性的固定 `esp32S_XYZ` 版本。

`esp32S_XYZ` 拥有：

- U1 电机 MCU 固件和 U8 AI MCU 固件；
- Edge-A/B/C/D 设备模式和示例；
- 小智服务器、管理 API、管理 Web/移动端和产品特定运维；
- 硬件验证、配置、OTA、自检、监控和发布证据；
- 在实际设备验证之前使用的假 U1/设备/AI 测试工具。

## 仓库入口

| 路径 | 类型 | 远程仓库 | 分支 |
|---|---|---|---|
| `esp32S_XYZ` | Git 子模块 | `https://github.com/zhuguang-ZFG/esp32S_XYZ.git` | `main` |

当前固定版本：

```text
a4cab61 route_policy hard contract + backend field closeout
```

## 集成模型

使用契约优先集成：

1. 保持 LiMa 服务器作为模型路由、AI 任务、记忆、安全和外部托管端点的后端控制平面。
2. 保持 `esp32S_XYZ` 作为固件、设备协议、管理 API/移动端/Web 和硬件发布证据的产品实现。
3. 任何面向 LiMa 的产品更改必须说明更改了哪个契约：聊天/LLM、图像/矢量生成、语音/ASR/TTS、内容安全、OTA 规划、设备遥测、监控或任务编排。
4. 如果契约更改涉及双方，先提交并推送 `esp32S_XYZ`，然后更新主 LiMa 子模块指针以及匹配的 LiMa 文档/测试。
5. 不要在仓库之间复制提供商凭证、设备密钥、VPS 密码、证书私钥或生产 API 密钥。

对于云端模型选择、提供商准入、AI 绘图/写字任务族、回退行为和设备感知路由规则，使用 `docs/AI_DRAWING_WRITING_MODEL_ROUTING_GUIDE_CN.md`。

## 重构权限

LiMa 在处理此产品时可以直接修改 `D:\QWEN3.0\esp32S_XYZ`。允许的工作包括：

- 代码质量修复和测试加固；
- 管理 API、小智服务器、移动端/Web、假设备、模式和运维重构；
- 面向 LiMa 托管的 AI、语音、图像/矢量、安全、遥测和任务编排的产品端适配器；
- 文档、运行手册和 CI 改进；
- 在产品仓库更改提交并推送后更新主 LiMa 仓库中的子模块指针。

门控工作仍需要明确的发布证据：生产 VPS 更改、OTA 行为更改、配置行为更改、硬件运动执行、密钥轮换、证书/密钥处理和任何破坏性硬件操作。

## 验证

在推进产品/后端集成的子模块指针之前，使用产品仓库中与所触及区域匹配的 CI 等效检查：

```powershell
cd D:\QWEN3.0\esp32S_XYZ
python tools/validate_schemas.py
python tools/check_gpio.py
python tools/test_check_gpio.py -v
python -m unittest tools.tests.test_check_gpio -v
python -m unittest discover -s tests -p "test_*.py" -v
python -m unittest tools.fake_u1.tests.test_app -v
python -m unittest tools.fake_device_server.tests.test_app -v
python -m unittest tools.fake_ai.tests.test_app -v
python -m unittest tools.fake_lima_u8.tests.test_app -v
python -m unittest tests.ci.test_fake_integration -v
```

对于管理 API 更改：

```powershell
cd D:\QWEN3.0\esp32S_XYZ\server\xiaozhi-esp32-server\main\manager-api
mvn test
```

对于管理移动端更改：

```powershell
cd D:\QWEN3.0\esp32S_XYZ\server\xiaozhi-esp32-server\main\manager-mobile
corepack pnpm install --frozen-lockfile --ignore-scripts
corepack pnpm run type-check
corepack pnpm run build:mp-weixin
```

对于影响此产品的 LiMa 后端更改，还需验证相关的主仓库后端测试和公共/私有端点冒烟测试，然后将证据记录在 `STATUS.md`、`docs/LIMA_MEMORY_CN.md` 和 `progress.md` 中。

## 运维记录

当此产品开始使用 LiMa 托管的后端端点时，记录在：

- `docs/ONLINE_DISTRIBUTIONS_CN.md` 用于公共/私有端点所有权；
- `infra/vps/` 用于如果 VPS 服务更改时的消毒 nginx/systemd 快照；
- `STATUS.md` 用于短期运维快照；
- `docs/LIMA_MEMORY_CN.md` 用于持久跨会话上下文；
- `progress.md` 用于按时间顺序的关闭证据。

## LiMa 直接设备网关证据

产品仓库现在包括 `tools/fake_lima_u8/`，一个用于 LiMa `/device/v1/ws` 的确定性假 U8 客户端。

当前假 U8 范围：

- 发送带有 `protocol=lima-device-v1` 的 `hello`；
- 发送 `heartbeat`；
- 发送文本 `transcript`；
- 期望带有 `capability=run_path` 的 LiMa `motion_task`；
- 发送 `motion_event` `progress` 和 `done`；
- 在运动事件中包含 `device_id` 和 `session_id` 以兼容现有 Edge-C 约定。

CLI 仅在连接到真实 LiMa 服务器时才导入可选的 `websockets` 包。单元测试使用内存传输，因此产品 CI 可以在不添加网络依赖的情况下验证协议脚本。

最新 LiMa 后端证据：

- `https://chat.donglicao.com/device/v1/health` 报告 Redis 支持的任务存储和 Redis 会话总线。
- 公共假 U8 冒烟测试针对 `wss://chat.donglicao.com/device/v1/ws` 完成。
- 通过在私有临时路由器上创建任务同时设备 WebSocket 保持连接到公共主路由器，验证了跨进程交付。
- LiMa 设备任务现在包括用于 `device_control`、`device_write`、`device_draw`、`device_vector` 和 `device_unknown` 的 `route_policy` 元数据。
- `esp32S_XYZ` Edge-B 和 Edge-C `motion_task` 模式接受相同的 `route_policy` 契约，并且 run_path 示例包含 `device_vector` 策略。

## 安全边界

将真实硬件、OTA、配置、声纹、图像生成、矢量化处理和运动执行视为门控发布面。设计时测试和假设备证据是有用的，但它们不能替代发布声明的物理设备验证。
