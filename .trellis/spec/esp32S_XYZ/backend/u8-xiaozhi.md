# U8 / AI_MCU 规范（xiaozhi-esp32）

> U8 = 带无线能力 MCU。**唯一自定义代码**是板目录 `firmware/u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/`（整目录 10 个文件）。其余全是上游 xiaozhi-esp32。

## 目录结构与板选择

- ESP-IDF **`>=5.5.2`**（`main/idf_component.yml` 末尾，强制；`getting-started.md` 说 5.4+ 已过时）。
- 板代码集中在一处：`main/boards/<manufacturer>/<board>/`，含三件套：`config.h`（板级 `#define`）、`config.json`（Kconfig 注入）、`<board>_board.cc`。
- 板选择走 Kconfig `CONFIG_BOARD_TYPE_*` + `main/CMakeLists.txt` 的 `file(GLOB BOARD_SOURCES ...)`。本项目**已锁死单一板型**：`set(MANUFACTURER "zhuguang")` / `set(BOARD_TYPE "dlc-motor-control-p1-ai")`，CMakeLists 注释明示"其他 100 个冗余 board 已删除瘦身"。
- 依赖锁在 `dependencies.lock`：esp-sr `~2.3.0`、esp_codec_dev `~1.5.6`、esp32-camera `^2.1.6`、lvgl `~9.5.0`、esp_lvgl_port `~2.7.2`。

## 板目录文件职责（`dlc-motor-control-p1-ai/`）

| 文件 | 职责 |
|------|------|
| `config.h` | 板级引脚（I2S/U1 UART/摄像头/DLC API）、`AUDIO_*` 常量、`U1_UART_*` |
| `config.json` | Kconfig 注入（`CONFIG_BOARD_TYPE_ZHUGUANG_DLC_MOTOR_CONTROL_P1_AI=y` 等） |
| `dlc_motor_control_p1_ai_board.cc` (30KB) | `class DlcMotorControlP1AiBoard : public WifiBoard`；持有 `U1ProtocolClient`/`MotionEventEmitter`/`MotionExecutor`；含 DLC API HTTPS 调用 |
| `u1_protocol_client.{h,cc}` | Edge-D U8 侧客户端：`@{json}\n` 帧、抢占式命令 |
| `motion_executor.{h,cc}` | capability→HOME/MOVE/PATH_*；`FetchWorkspaceMm` 校验、`motion_busy_` 原子锁 |
| `motion_event_emitter.{h,cc}` | 上行 motion_event |
| `test_u8_protocol_logic.cpp` | 板内 C++ 测试 |

## 编码风格（从代码推断，xiaozhi 上游无 style 文档）

> ⚠️ **U8 命名与 U1 不同**：U8 是 xiaozhi 上游，用 **camelCase 方法名 + CamelCase 类名**（如 `SendU1ProtocolJson`、`NextProtocolMessageId`、`DlcMotorControlP1AiBoard`）。不要把 U1 的 `snake_case` 成员习惯带过来。

| 项 | 规则 |
|----|------|
| 类/继承 | `class XBoard : public WifiBoard`（基类 `main/boards/common/wifi_board.{h,cc}`） |
| JSON | **一律 cJSON**（`#include <cJSON.h>`），不用 nlohmann；cJSON 对象用完必释放，优先 RAII guard |
| 日志 | `ESP_LOGE/I/W/D` + `#define TAG_XXX "..."` 宏（如 `TAG_U1_PROTOCOL`） |
| 凭证 | token 走 NVS（`nvs_open`/`nvs_get_str`），**禁止硬编码**；URL 强制 https；http 超时**禁 0**（0=无限阻塞） |
| 缺省值语义 | 用 `std::optional` 区分"字段缺失"与"显式 0"（见下例） |
| 头文件守卫 | `#ifndef ... #define ... #endif`（上游惯例；config.h 用 `_BOARD_CONFIG_H_`） |

## 安全红线（真实代码里反复出现"固件审查 P1/P2"注释，逐字保留这些约定）

| 红线 | 实现位置（真实） | 要求 |
|------|----------------|------|
| SEC-005 OOM 防护 | `config.h` `DLC_API_MAX_RESPONSE_BYTES (128*1024)` | 外部响应必须有字节上限 |
| SEC-007 token 不入固件 | `board.cc` `GetDlcApiToken()` | 从 NVS 读，绝不编译进固件；`nvs_get_str` 返回值必查，禁静默截断 |
| 强制 HTTPS | `board.cc` `if (base_url.rfind("https://",0)!=0)` | `DLC_API_BASE_URL` 必须 `https://`（默认 `https://chat.donglicao.com`） |
| 超时禁 0 | `board.cc` `CreateHttp(timeout_seconds)` 15s | 防 half-open 连接挂死 MCP 线程（0=无限阻塞，禁） |
| 响应无界增长 | `u1_protocol_client.h` `kU1MaxResponseBytes = 8*1024` | U1 响应字符串必须有上限 |
| 控制面未配 token | `board.cc` control_ws_token 未配 → `ESP_LOGE` + 拒绝 Start | 本地控制 WS 未配 token 禁启动（非静默降级） |
| NVS 加密 | `sdkconfig.defaults` `CONFIG_NVS_ENCRYPTION=y` | 凭证落 NVS 必开加密 |
| OTA | `ota.{h,cc}` + `test_u8_ota_allowlist.cpp` | sha256 + 签名验签 + A/B 分区 + rollback，allowlist 守护 |

## 代码示例（逐字取自 `u1_protocol_client.h` / `config.h`）

可选值区分缺失与 0（固件审查 P1）：

```cpp
// 固件审查 P1：返回 std::optional 以区分"字段缺失"与"显式传 0"。
// move_abs 用它判断是否下发 z：缺失 z 时不下压 Z 轴（防 2D 移动落笔/撞机）。
static std::optional<int> MotionParamsGetOptionalInt(cJSON* params, const char* key);
```

UART 交叉接线（config.h，强校验项，不可回归）：

```cpp
// U8 的 TX 必须接到 U1 的 RX。按硬件文档：
//   U8.IO11 = M_U1TXD (U8 发给 U1) → U1.IO11 = M_U1RXD
//   U8.IO10 = M_U1RXD (U8 收自 U1) ← U1.IO10 = M_U1TXD
// 之前此处 TX/RX 对调，导致 UART 双向哑通道。
#define U1_UART_TXD       GPIO_NUM_11
#define U1_UART_RXD       GPIO_NUM_10
```

> `tools/check_gpio.py` 对此有硬校验：`U8 GPIO11 = M_U1TXD → U1 RXD`，`u8_uart_tx.gpio != 11` 直接报错。改 U1 UART 引脚是高危项，曾因 TX/RX 对调导致哑通道。

## SoftAP DLC device_secret（tracked patch）

上游 `78/esp-wifi-connect` 在 `managed_components/`（gitignore）。DLC 需要 SoftAP `/submit` 写入 NVS `device_secret` / `server_host`，因此维护 **tracked patch**（例外于「禁止改上游」铁律，仅限该组件）：

- Patch：`firmware/u8-xiaozhi/patches/esp-wifi-connect-softap-dlc.patch`（`wifi_configuration_ap.cc` + `assets/wifi_configuration.html`）
- 门禁：`python scripts/ensure_softap_dlc_patch.py`（CC marker `SaveDlcProvisioningFields` + HTML `id="device_secret"`）；`release.py` 在 set-target 后强制调用
- 门户：主 Connect 表单可选字段；空字符串不覆盖已有 NVS
- 组件升级后若 patch 冲突：ensure 失败即停，勿静默跳过

## 已知未落地项（document reality，勿写成已支持）

- **舵机 / 抬笔**：架构 v2 §10bis.7 要求 pause/cancel 自动抬笔；协议层 `pen_mode` 存在但 U1 侧未实现（U8 侧 `motion_executor` 也不发抬笔命令）。
- **独立急停按钮**：架构 v2 §10bis.12 —— 无独立急停按钮，靠 U1 BOOT 按键（<10ms 响应）+ U8 `SendU1PreemptiveCommand`（STOP/ESTOP 绕过 UART 锁）。
- **龙门矫正**：架构 v2 §10bis.9 暂缓（关 squaring 差分、保留双 Y 同步归零），与机型文件当前 `DEFAULT_HOMING_SQUARED_AXES` 设置不同，§16.5 列独立实施项。

写新能力时若涉及这些，标注"TODO/未落地"，不要假设闭环。
