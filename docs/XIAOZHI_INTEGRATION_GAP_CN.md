# LiMa 替换小智服务器：整合缺口施工手册

> 文档目的：供执行 Agent **直接施工**，无需二次探索。所有指令精确到文件:行，含验收标准与执行顺序。
> 目标：LiMa 形成真正战斗力，完整替换 xiaozhi-esp32-server，接管 U8 固件的语音等全部能力。
> 背景：2026-06-25 小智服务端 4 组件物理删除（Python server / Java manager-api / Vue manager-web / digital-human）。
> 审计日期：2026-06-28｜审计者：ZCode

---

## 执行摘要（TL;DR）

LiMa 已完成约 90% 的能力接管（语音对话、ASR/TTS×11 家、声纹、视觉、管理后台、配网等均已实现）。**有 3 个 CRITICAL 硬阻塞，集中在固件↔LiMa 的对接层**：

1. **OTA 响应缺 websocket 段**（TASK-1）：LiMa 不下发 `websocket` 段 → 固件 `HasWebsocketConfig()=false` → 兜底走 MQTT（application.cc:488-494）→ 连不上 LiMa WS 网关。
2. **OTA 方法/鉴权/URL 三不匹配**（TASK-2）：固件发 POST（ota.cc:189）+ Device-Id header（ota.cc:156），LiMa `/check` 只接 GET + 要 JWT Bearer → 固件请求被拒。固件默认 OTA_URL 还指向小智官方（Kconfig.projbuild:5）。
3. **WS 鉴权 token 永远为空**（TASK-6，已核实铁证）：固件 NVS 的 `token` 字段全代码无写入点 → token 永远空 → 固件连 /ws 不带 Authorization → LiMa `validate_device_token`（auth.py:34）对空 token 返回 False → close(1008)。**这是铁证级硬阻塞**，不解决 TASK-1/2 做完也连不上。

**最小可行路径（让 U8 真正连上 LiMa）**：
1. 【后端】`device_ota_app.py` OTA 响应补 `websocket`/`server_time` 段 —— **TASK-1**
2. 【后端+固件】`/check` 支持 POST + Device-Id 鉴权 + 固件改默认 OTA_URL —— **TASK-2**
3. 【已核实+施工】固件 WS token 永远为空，需打通 token 链路（方案 a/b/c）—— **TASK-6**
4. 【验证】真机烧录 U8 → 开机 → 端到端语音对话 —— **TASK-3**

**核心认知**：不是"改固件一个配置就能通"。TASK-1（补 websocket 段）+ TASK-2（方法/鉴权/URL 三合一）+ TASK-6（token 链路）三者必须都做完，固件才能连上 LiMa。

---

## 一、能力覆盖盘点（已完成项，供参考，无需施工）

### ✅ 已完整接住（13 项，无需改动）

| 小智能力 | LiMa 实现 | 证据（文件:行） |
|---------|----------|---------------|
| 语音对话 ASR→LLM→TTS | dialogue 接通 routing_engine | `device_voice/dialogue.py:105` `_run_llm` |
| 流式实时语音 WS | /voice 流式管线 | `routes/voice_pipeline_ws.py:37` |
| ASR 后端（6 家） | aliyun/dashscope/doubao/funasr/whisper/composite | `device_voice/providers/asr_*.py` |
| TTS 后端（5 家） | aliyun/dashscope/doubao/edge/mimo | `device_voice/providers/tts_*.py` |
| VAD | Silero | `device_voice/vad.py` + `providers/vad_silero.py` |
| 声纹识别 | 注册/管理/识别 | `device_voice/voiceprint*.py` + `routes/device_app_members.py:65` |
| 视觉感知 VLLM | 多模态路由 | `vision_handler.py:95` `_vision_route` |
| 意图识别 | instructor + modal | `routing_intent.py:259` `analyze_intent` |
| 记忆系统 | 比小智更全（学习循环） | `session_memory/`（compactor/embeddings/eval_gate/learning_loop） |
| 知识库检索 | 自研向量检索 | `context_pipeline/retrieval_injection.py:21` |
| 管理后台（19 路由） | 接住 manager-web | `routes/admin*.py` + `routes/admin_ui/` |
| 用户认证 | 接住 manager-api | `routes/device_app_auth.py:102-170` |
| 配网 | provision/confirm | `routes/device_app_misc.py:205-255` |

### ✅ WS 协议契约已兼容（hello_ack，无需改动）

固件 `websocket_protocol.cc:245 ParseServerHello` 期望 `hello_ack` 含 `type/protocol/device_id/server_time/sample_rate`。LiMa `device_gateway/protocol_frames.py:22 hello_ack` 已提供这些字段（`sample_rate=16000` PCM，`server_time=now_iso()`）。**握手层契约匹配，无需改动。**

---

## 二、缺口清单与施工任务

### 🔴 TASK-1（CRITICAL）：LiMa OTA 响应补连接配置字段

**问题**：固件 `ota.cc:242-281` 解析 OTA 响应时，期望顶层 `websocket`/`mqtt`/`server_time` 段。LiMa `device_ota_app.py:30-79` `_ota_status_for_device` 完全不下发这些字段。

**为什么是 CRITICAL（精确机制，必读）**：

固件协议选择逻辑在 `application.cc:488-494`：
```cpp
if (ota_->HasMqttConfig())            → 走 MQTT
else if (ota_->HasWebsocketConfig())  → 走 WebSocket
else                                  → 兜底走 MQTT   ← LiMa OTA 不下发时落这里
```

LiMa 设备网关是 **WebSocket**（`/ws`），**不实现 MQTT**。所以若 LiMa OTA 不下发 `websocket` 段，固件兜底走 MQTT → **连不上 LiMa 的 WS 网关 → 语音链路建不起来**。

**注**：固件 `websocket_protocol.cc:93-94` 有 WS URL 兜底默认值 `wss://chat.donglicao.com/device/v1/ws`（LiMa），但**这个兜底只在固件已选择 WebSocket 协议后才生效**。协议选择本身由 `HasWebsocketConfig()` 决定，而该标志来自 OTA 的 `websocket` 段（`ota.cc:263-278`）。所以**OTA 必须下发 `websocket` 段，固件才会进 WS 分支**，URL 兜底才有意义。

**契约对比表**：

| 固件期望（ota.cc 解析） | LiMa 现状 | 缺口 |
|------------------------|----------|------|
| `websocket`（含 url 等，ota.cc:263-278，决定 HasWebsocketConfig_） | ❌ 缺失 | 🔴 必须补（否则固件兜底走 MQTT） |
| `mqtt`（含 broker 等，ota.cc:242-257，决定 HasMqttConfig_） | ❌ 缺失 | 🟢 不补（固件 mqtt 段缺失则 HasMqttConfig_=false，配合 websocket 段正中下怀） |
| `server_time`（timestamp/timezone_offset，ota.cc:284-303） | ❌ 缺失 | 🟡 建议补（时钟同步，非阻塞） |
| `firmware`（version/url/sha256/signature，ota.cc:312-348） | ⚠️ 仅 selected 时返回 | 🟡 现有逻辑保留 |
| `activation`（message/code/challenge，ota.cc:219-239） | ❌ 缺失 | 🟢 可选（无激活流程则省） |

**施工指令**：

1. **文件**：`routes/device_ota_app.py`
2. **函数**：`_ota_status_for_device`（line 30-79）
3. **顶部 import**：⚠️ **当前文件无 `import time` 和 `import os`**（line 3-16 现有 import：asyncio/fastapi/...，无 time/os）。**必须新增** `import os` 和 `import time`。
4. **新增辅助函数**（避免在两个 return 重复）：

```python
def _device_connection_config() -> dict:
    """固件 OTA 响应所需的连接配置：WebSocket 段 + 服务器时间。

    关键：必须返回 websocket 段（非 null 对象），否则固件 application.cc:488-494
    会因 HasWebsocketConfig()=false 兜底走 MQTT，连不上 LiMa 的 WS 网关。
    mqtt 段不返回（缺失即 HasMqttConfig()=false，配合 websocket 段让固件正确走 WS）。
    """
    ws_url = os.environ.get("LIMA_DEVICE_WS_URL", "wss://chat.donglicao.com/device/v1/ws")
    return {
        "websocket": {"url": ws_url},
        "server_time": {
            "timestamp": int(time.time() * 1000),  # 毫秒（固件 ota.cc:292 按毫秒处理）
            "timezone_offset": 480,  # 中国 UTC+8，单位分钟（ota.cc:296 乘 60*1000）
        },
    }
```

5. **接入点**：在两个 return（line 48-57 no_release 分支 + line 70-79 正常分支）的 dict 中合并 `**_device_connection_config()`。**两个分支都要加**（固件即便无新版本也需 websocket 段来选协议）。
6. **⚠️ 不要返回 `"mqtt": None`**：固件 `ota.cc:243 cJSON_IsObject(mqtt)` 对 null 返回 false → HasMqttConfig()=false（符合预期），但**直接不返回 mqtt 键更干净**（固件走 else 分支 line 258-260 "No mqtt section found"，同样 HasMqttConfig()=false）。
7. **环境变量**：在 `.env.example` 增补 `LIMA_DEVICE_WS_URL=` 并注释（默认 wss://chat.donglicao.com/device/v1/ws）。

**验收标准**：
- [ ] `_ota_status_for_device(...)` 返回的 dict 含 `websocket`（对象，含 url）和 `server_time`（对象，含 timestamp/timezone_offset）两个顶层键
- [ ] **不返回** `mqtt` 键（或返回 null，但推荐省略）
- [ ] `websocket.url` 以 `wss://` 开头
- [ ] `server_time.timestamp` 为正整数（毫秒）
- [ ] 新增测试 `tests/test_device_ota_app.py::test_ota_response_includes_connection_config`，断言：返回含 websocket 段（非 null）、server_time.timestamp>0、无 mqtt 键
- [ ] `.venv310/Scripts/python.exe -m pytest tests/test_device_ota_app.py -v` 通过
- [ ] `ruff check routes/device_ota_app.py` 通过
- [ ] `scripts/check_code_size.py` 通过（device_ota_app.py ≤300 行）

**风险**：
- `websocket` 段必须是**非 null 对象**（含至少一个字段如 url），否则固件 `cJSON_IsObject` 判 false → HasWebsocketConfig()=false → 兜底走 MQTT。
- `server_time` 固件 `cJSON_IsObject` 判断（ota.cc:285），必须返回对象（含 timestamp 数字）。

---

### 🔴 TASK-2（CRITICAL）：U8 固件默认 OTA_URL 切到 LiMa

**问题**：`firmware/u8-xiaozhi/main/Kconfig.projbuild:5` 默认 `CONFIG_OTA_URL` 仍指向小智官方 `https://api.tenclass.net/xiaozhi/ota/`，U8 开机连的是小智官方而非 LiMa。

**施工指令**：

1. **文件**：`esp32S_XYZ/firmware/u8-xiaozhi/main/Kconfig.projbuild`
2. **位置**：line 3-5
3. **改动**：
```
config OTA_URL
    string "Default OTA URL"
    default "https://chat.donglicao.com/device/v1/ota/check"
```
4. **路径依据**：LiMa `device_ota_app.py:90` `@router.get("/check")` + `prefix="/device/v1/ota"`（line 18）→ 完整路径 `/device/v1/ota/check`。
5. **HTTP 方法契约冲突**（必读）：固件 `ota.cc:189` `std::string method = data.length() > 0 ? "POST" : "GET";` —— 有 system_info body（`GetSystemInfoJson()`，ota.cc:188）时发 **POST**。LiMa `/check`（device_ota_app.py:90）是 **GET only**。需二选一：
   - 方案 a（推荐，改后端）：LiMa `/check` 改为同时支持 GET 和 POST（FastAPI `@router.api_route("/check", methods=["GET","POST"])`，POST 分支读 body 但不强解析——固件 body 是 system_info，LiMa 暂不需要）
   - 方案 b（改固件，风险高）：固件改用 GET（改 ota.cc 逻辑）
6. **鉴权契约冲突**（必读，CRITICAL）：固件 `ota.cc:155-164 SetupHttp()` 用 `Device-Id` + `Client-Id` + `Serial-Number` + `Activation-Version` header（**不是** `Authorization: Bearer`）。LiMa `/check`（device_ota_app.py:91）签名 `authorization: str = Header(default="")` → line 97 `authorize(authorization)`。**两套鉴权完全不兼容**。需二选一：
   - 方案 a（推荐，改后端）：在 `/check` 增加替代鉴权分支——当 `authorization` 为空时，回退用 `Device-Id` header 查设备归属。**注意**：现有 `authorize()`（device_logic/auth.py:87）是 JWT 校验（依赖 PyJWT + jwt_secret），**不要改它**。新增独立函数 `authorize_device_by_header(device_id_header)`，按 `Device-Id`（MAC 地址）查 `devices` 表的绑定账户（参考 `device_logic/db.py connect` + `device_logic.access.device_access`）。`Device-Id` 是 MAC（ota.cc:156 `SystemInfo::GetMacAddress()`），需确认 LiMa devices 表用什么字段存 MAC。
   - 方案 b（改固件）：固件 SetupHttp 加 `Authorization: Bearer <token>`（但固件无 LiMa JWT token，需先注册/登录获取，链路长，不推荐）

**验收标准**：
- [ ] `Kconfig.projbuild` 默认 OTA_URL 为 LiMa 地址（`chat.donglicao.com/device/v1/ota/check`）
- [ ] LiMa `/device/v1/ota/check` 支持 POST（固件实际发的方法）
- [ ] LiMa `/check` 能鉴权固件的 `Device-Id` 请求（无 Authorization 也能通过设备绑定校验）
- [ ] 固件烧录后开机日志显示连接 `chat.donglicao.com`（非 tenclass.net）且 OTA 返回 200

**风险**：
- POST vs GET 方法不匹配（ota.cc:189）
- **鉴权方式不匹配是第二个硬阻塞**：固件发 Device-Id header，LiMa 要 Authorization Bearer（JWT）。不改则固件请求被 LiMa 401 拒绝。
- 固件 POST body 是 system_info JSON（`board.GetSystemInfoJson()`），LiMa `/check` 改 POST 后需容忍该 body（不解析也行，但不能因 body 解析失败报错）
- `Device-Id` 鉴权需先确认 LiMa `devices` 表的 MAC 字段名（执行 Agent 需读 `device_logic/db.py` 或现有设备绑定逻辑确认）

---

### 🟡 TASK-3（验证）：真机端到端冒烟

**前置**：TASK-1 + TASK-2 完成且单测通过。

**施工指令**：人工/集成 Agent 执行，需真实硬件。

1. 编译 U8 固件（`esp32S_XYZ` 目录 `make build-u8` 或 PlatformIO/IDF 命令）
2. 烧录到 U8 设备
3. 设备开机，观察串口日志（115200）：
   - 应显示 `Connecting to chat.donglicao.com`（非 tenclass.net）
   - OTA 检查返回 200，含 websocket 配置
   - WS 连接建立，hello/hello_ack 握手成功
4. 按麦克风说话，验证完整链路：
   - 麦克风 → U8 → LiMa /ws → VAD → ASR（识别文字）→ routing_engine → LLM（生成回复）→ TTS → U8 喇叭播放
5. 验证声纹、流式 TTS、连续对话

**验收标准**：
- [ ] 设备串口日志显示连 LiMa（非小智官方）
- [ ] hello_ack 握手成功（日志 `LiMa protocol:` + `Device ID:`）
- [ ] 一次完整语音对话（说话→听到回复）端到端 < 5 秒
- [ ] 连续 3 轮对话无中断

---

### 🟢 TASK-4（P2，非阻塞）：核对 MCP 工具调用覆盖度

**不确定项**：小智支持四类 MCP（客户端 IOT / 客户端 MCP / 服务端 MCP / MCP 接入点）。LiMa 有 `tool_gateway/`（audit/governance）+ `lima_mcp/`，但覆盖度未深入核对。

**施工指令**（调研型，不立即改代码）：

1. 读 `esp32S_XYZ/server/xiaozhi-esp32-server/README.md` MCP 章节，列出四类 MCP 的协议契约
2. 对照 LiMa `tool_gateway/governance.py`、`lima_mcp/`、`routes/device_gateway_ws_handlers.py` 的工具调用处理
3. 输出 gap 清单：哪些 MCP 类型 LiMa 已支持、哪些缺失
4. 若 U8 固件实际用到 MCP（查 `application.cc` 的工具调用），标注优先级

**验收标准**：
- [ ] 产出四类 MCP 覆盖对照表（已支持/部分/缺失）
- [ ] 标注是否阻塞核心语音链路（预期：不阻塞，MCP 是增强能力）

---

### 🟢 TASK-5（P2，非阻塞）：核对 IOT 指令下发格式兼容

**不确定项**：小智用 MQTT 下发 IOT 指令，LiMa 用 WS 任务派发（device_gateway）。格式兼容性未深入。

**施工指令**（调研型）：

1. 读 `esp32S_XYZ/firmware/u8-xiaozhi/main/protocols/mqtt_protocol.cc` 的指令解析（`SendText`/消息处理）
2. 对照 LiMa `device_gateway/protocol_frames.py` 的下行帧格式（`run_path_dispatch_frame` 等）
3. 确认 LiMa WS 下行帧能否被固件正确解析
4. 若格式不兼容，标注需要的适配层

**验收标准**：
- [ ] 产出 IOT 指令格式对照（MQTT vs LiMa WS 帧）
- [ ] 标注是否阻塞（预期：写字机/绘图机任务派发已工作，仅边缘 IOT 指令可能需适配）

---

### 🔴 TASK-6（CRITICAL，已核实）：固件 WS token 永远为空，连 /ws 必被拒

**已核实结论**（证据链完整闭合）：固件 NVS 的 `token` 字段**全代码无任何写入点** → token 永远空 → 固件连 LiMa `/ws` 不带 Authorization → LiMa `validate_device_token` 对空 token 返回 False → 连接被 close(1008) → **语音链路建立不了**。

**完整证据链**（每一步都有代码佐证）：

| 步骤 | 证据（文件:行） | 结论 |
|------|----------------|------|
| ① token 写入点 | 全代码搜 `SetString.*token`/`nvs_set_str`（`firmware/u8-xiaozhi/main/`）→ **零命中**（仅 mcp_server.cc:335 读 vision token，无关） | token 无写入，永远空 |
| ② 固件连 WS 读 token | `websocket_protocol.cc:89` `settings.GetString("token")`（Settings 默认值空，settings.cc:21-28） | token="" |
| ③ token 空的行为 | `websocket_protocol.cc:109-112` `if (!token.empty())` 跳过 → 不发 Authorization；line 113 无条件发 Device-Id | 仅 Device-Id header |
| ④ LiMa 取 token | `device_gateway_dispatch.py:42-56` `extract_ws_token`：无 query ticket（路径A）+ 无 Authorization header（路径B）→ 返回空 | token="" |
| ⑤ LiMa 校验 | `device_gateway/auth.py:30-36` `validate_device_token`：`if not expected or not token: return False` → **空 token 直接 False** | False |
| ⑥ 拒绝动作 | `device_gateway_ws_handlers.py:86-93` `_authenticate_hello` → `close(code=1008)` | 连接关闭 |

**第二层问题**：`validate_device_token`（auth.py:31）用 `configured_device_tokens().get(device_id)` —— 查的是**预配置的 device token 映射**（非设备绑定表），需 `compare_digest(expected, token)` 严格匹配。即使固件有 token，也必须和 LiMa 配置里的 device token 一致。

**注**：固件 `websocket_protocol.cc:113` 无条件发 `Device-Id` header，但 LiMa `extract_ws_token`（dispatch.py:42-56）**不读 Device-Id**——它只认 query ticket 或 Authorization header。所以 Device-Id 在鉴权阶段被忽略（仅 hello 之后用于路由）。

**施工指令**（必须做，否则 TASK-1/2 做完固件仍连不上 WS）：

需打通"固件拿到 token → 连 WS 时带上 → LiMa 校验通过"的完整链路。三个方案（推荐 a，全后端不动固件）：

- **方案 a（推荐，纯后端 + 固件小改）**：OTA 响应下发 token
  1. TASK-1 的 `_device_connection_config()` 在 `websocket` 段补 `token` 字段：`{"url": ..., "token": <device_token>}`
  2. 固件 `ota.cc` 解析 websocket 段时（line 265-277），把 `token` 存入 NVS（`Settings("websocket").SetString("token", ...)`）—— **这是固件唯一需要的改动**（补一个 token 写入点）
  3. LiMa 侧：OTA 端点需为每个设备生成/查询其 device token（`configured_device_tokens` 的来源），下发给固件
  - 优点：固件只改 1 处（ota.cc 解析 token），链路最短
  - 风险：token 经 OTA 明文下发，需确保 HTTPS（TASK-1 已确认固件强制 HTTPS）

- **方案 b（改 LiMa 鉴权，不动固件）**：`extract_ws_token` 增加 Device-Id 兜底
  1. `device_gateway_dispatch.py:extract_ws_token` 当 ticket/Authorization 都空时，读 `Device-Id` header
  2. `validate_device_token` 增 Device-Id 分支：按 MAC 查设备绑定表，若设备已绑定则放行
  - 优点：固件零改动（token 空也行，靠 Device-Id 兜底）
  - 风险：Device-Id 是 MAC 地址，明文可伪造，安全性弱于 token；需评估是否可接受（设备已在局域网/已配网，风险可控？）

- **方案 c（改固件配网流程）**：配网时存 token
  1. LiMa provision 流程（`device_app_misc.py:222` 生成 `provision_token`）下发时，固件配网代码存入 NVS websocket.token
  - 风险：固件配网代码（BluFi/WiFi manager）改动面大，且 provision_token 与 device_token 是否同一需核对

**验收标准**：
- [ ] 选定方案并实施（a/b/c 之一）
- [ ] 真机验证：固件连 `/ws` 时携带有效凭证（token 或 Device-Id）
- [ ] LiMa `_authenticate_hello` 返回 True（非 1008 关闭）
- [ ] hello/hello_ack 握手成功
- [ ] 若选方案 a：固件 `ota.cc` 解析并存储 token；LiMa OTA 响应 websocket 段含 token
- [ ] 若选方案 b：LiMa `extract_ws_token` 支持 Device-Id 兜底；`validate_device_token` 支持 Device-Id 分支

**风险**：
- **这是铁证级硬阻塞**：不解决，TASK-1/2 做完固件仍连不上 WS（token 空 → 1008 关闭）
- 方案 a 最干净但需固件改 1 处；方案 b 零固件改动但安全性弱；方案 c 改动面大
- `configured_device_tokens` 的来源需执行 Agent 读源码确认（环境变量？DB？决定 token 怎么生成/查询）

---

## 三、执行顺序（依赖关系）

```
TASK-1（后端 OTA 补 websocket 字段）──┐
TASK-6（核实/打通 WS token 鉴权）──────┤
TASK-2（/check POST + Device-Id 鉴权 + 固件改 URL）──┤
                                      ├──→ TASK-3（真机冒烟）
TASK-4/5（调研，可并行，不阻塞）────────┘
```

- **TASK-1 + TASK-2 + TASK-6 三者必须都完成才能 TASK-3**：
  - 缺 TASK-1：固件兜底走 MQTT，连不上 LiMa WS
  - 缺 TASK-2：固件连小智官方 OTA，或被 LiMa /check 的方法/鉴权拒绝
  - 缺 TASK-6：固件拿不到 WS ticket，连上 /ws 也被拒
- TASK-1/2/6 可并行（不同文件/不同子系统），但都做完才能真机验证
- TASK-4/5 是独立调研，可与上述并行，不阻塞核心链路

---

## 四、环境与门禁约定（执行 Agent 必读）

- **Python 环境**：必须用 `.venv310`（Python 3.10.20）。**禁止用系统 python 3.14**（会因缺 freezegun 等依赖误报测试失败）。命令前缀 `.venv310/Scripts/python.exe`
- **代码约束**（AGENTS.md 硬规则）：
  - 单文件 ≤300 行，单函数 ≤50 行（`scripts/check_code_size.py` 强制）
  - 禁止 `except Exception: pass` 静默降级（至少 `logger.warning`）
  - 文档类产出用中文
- **门禁三件套**（每次改动后跑）：
  1. `.venv310/Scripts/python.exe -m pytest tests/<相关测试> -v`
  2. `.venv310/Scripts/python.exe -m ruff check <改动文件>`
  3. `.venv310/Scripts/python.exe scripts/check_code_size.py`
- **不要 git commit**（除非用户明确要求）；不要 `git add .`

---

## 五、关键文件索引

| 文件 | 作用 | 关键行 |
|------|------|--------|
| `routes/device_ota_app.py` | LiMa 设备 OTA 端点 | `_ota_status_for_device` line 30-79（TASK-1 改这里） |
| `routes/device_ota.py` | LiMa OTA 内部管理（canary/gradual） | 不改 |
| `device_gateway/protocol_frames.py` | WS 协议帧构造（hello_ack 等） | line 22, 85（已兼容，不改） |
| `routes/device_gateway_ws_handlers.py` | WS 握手处理 | line 97 `_negotiate_hello_protocol`（已兼容） |
| `routes/voice_pipeline_ws.py` | 实时语音 /voice 端点 | line 37（已就绪） |
| `device_voice/dialogue.py` | 语音对话核心（ASR→LLM→TTS） | line 105（已接通 routing_engine） |
| `esp32S_XYZ/firmware/u8-xiaozhi/main/Kconfig.projbuild` | 固件默认 OTA_URL | line 3-5（TASK-2 改这里） |
| `esp32S_XYZ/firmware/u8-xiaozhi/main/ota.cc` | 固件 OTA 解析（期望字段） | line 211-360（契约参考，不改） |
| `esp32S_XYZ/firmware/u8-xiaozhi/main/protocols/websocket_protocol.cc` | 固件 WS 协议（hello_ack 解析） | line 245-270（契约参考，不改） |

---

## 六、审计方法与诚实声明

**已核实**（全部有代码佐证）：
- 小智能力清单（README 功能表）vs LiMa 实现，逐项 grep 验证（13 项已接住）
- OTA 响应契约：读 `ota.cc:211-360` 解析逻辑 vs LiMa `_ota_status_for_device` 实际返回
- WS hello_ack 契约：读 `websocket_protocol.cc:245-270` vs LiMa `protocol_frames.py:22`
- 固件默认配置：读 `Kconfig.projbuild:3-5`（仍指小智官方）
- 固件协议选择机制：读 `application.cc:488-494`（无 websocket 段兜底走 MQTT）
- 固件 WS URL 兜底：读 `websocket_protocol.cc:93-94`（默认已指 LiMa）
- **固件 token 链路（TASK-6 铁证）**：全代码搜 token 写入点（零命中）+ `validate_device_token` 空 token 返回 False（auth.py:34）+ `_authenticate_hello` close(1008)（ws_handlers.py:92）
- OTA 请求方法：固件 `ota.cc:189` POST（有 system_info body 时）+ Device-Id header（ota.cc:156，无 Bearer）

**剩余调研项**（非阻塞，执行 Agent 做 TASK-4/5 时补充）：
- TASK-4（MCP 四类覆盖）：未深入，为调研型任务
- TASK-5（IOT 指令格式）：未深入，为调研型任务
- `configured_device_tokens` 的来源（环境变量/DB）：TASK-6 方案实施时需读源码确认（决定 token 生成方式）

**未做**：
- 真机端到端测试（TASK-3 需真实硬件 + 烧录）
- 方案 a/b/c 的实际编码（本手册给方案，执行 Agent 实施）
