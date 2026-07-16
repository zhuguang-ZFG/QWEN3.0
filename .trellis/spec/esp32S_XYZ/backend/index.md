# esp32S_XYZ 固件开发规范（backend）

> 面向 `trellis-implement` / `trellis-check` 子代理的固件约定。本文是入口；细节拆到同目录 `u1-grbl.md` / `u8-xiaozhi.md` / `edge-d-contract.md`。
> 子模块路径：`D:\QWEN3.0\esp32S_XYZ`。本规范**只覆盖固件（C/C++）**；小程序见包级 `index.md`，根目录 Python 服务规范不适用。

## 双 MCU 架构

```
┌─────────────┐  UART(@{json}\n, Edge-D)  ┌──────────────┐
│  U1 / MOTOR │ ◄──────────────────────► │   U8 / AI    │
│ Grbl_Esp32  │   步进/激光/限位/归零      │ xiaozhi-esp32│
│  运动控制    │                           │ 语音/摄像头/ │
│ PlatformIO  │                           │ 配网/LCD/OTA │
│  arduino    │                           │  ESP-IDF     │
└─────────────┘                           └──────┬───────┘
      J2 Type-C 烧录                              │ WSS
   (CH340C, BOOT 手动)                       上行 motion_event /
                                              DLC API(https)
```

U1 是纯串口运动 MCU（`-DDISABLE_BLUETOOTH -DDISABLE_WIFI`，不带无线）；U8 是带无线的能力 MCU，对外走 WSS、对 U1 走 UART。U1 不直接联网。

## 技术栈版本（锁版本，勿随手升级）

| 项 | U1 | U8 |
|----|----|----|
| 框架 | PlatformIO + arduino | ESP-IDF **`>=5.5.2`** |
| 平台 | `espressif32@6.8.1` | `esp32s3` |
| 板 | `esp32-s3-devkitc-1` | N16R8（`sdkconfig.defaults`） |
| 关键依赖 | `TMCStepper@>=0.7.3,<0.8.0`、SSD1306 OLED `^4.2.0` | esp-sr `~2.3.0`、esp_codec_dev `~1.5.6`、esp32-camera `^2.1.6`、lvgl `~9.5.0`（锁在 `dependencies.lock`） |
| 配置 | `firmware/u1-grbl/platformio.ini` | `firmware/u8-xiaozhi/main/idf_component.yml` + `sdkconfig.defaults*` |
| 安装 | `pio` core | `make setup-idf-u8`（装 IDF v5.5.2） |

> `getting-started.md` 写 IDF "v5.4+"，**已过时**；以 `idf_component.yml` 末尾 `idf: '>=5.5.2'` 为准。

## 改动边界铁律（最重要）

**本项目自定义代码面积极小**——上游代码不得改动，自定义只落在「机型层 / 板级层」：

| MCU | 自定义落点（**唯一可改**） | 上游代码（**禁止改**） |
|-----|---------------------------|----------------------|
| U1 | `firmware/u1-grbl/Grbl_Esp32/src/Machines/dlc_motor_control_p1.h`（机型定义） | `Grbl_Esp32/src/` 其余 ~50 个上游 .cpp/.h（Stepper/MotionControl/Protocol/Planner/GCode/Spindles/...） |
| U8 | `firmware/u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/`（整目录：`config.h`/`config.json`/`*_board.cc`/`u1_protocol_client.*`/`motion_executor.*`/`motion_event_emitter.*`） | `main/` 其余上游组件（`application.*`/`audio/`/`display/`/`protocols/`/`boards/common/`...） |

落地步骤（改任何引脚/能力前必读）：

1. 改机型/板级文件 → 2. 改 Edge-D schema（若动协议，见 `edge-d-contract.md`）→ 3. 改对应 fake → 4. `make test` 全绿 → 5. 跑固件静态契约测试 `tests/ci/test_edge_d_firmware_static.py`。

**禁止**：直接 patch 上游 `Stepper.cpp`/`application.cc` 等核心；如确需上游行为差异，在机型/板级层用配置或子类覆盖，保持可随上游升级。

## 上游约定权威来源

- **U1 编码风格**：`firmware/u1-grbl/CodingStyle.md` + `.clang-format`（强制，ColumnLimit 140）。详见 `u1-grbl.md`。
- **U8 风格**：从代码推断（xiaozhi-esp32 上游无独立 style 文档），见 `u8-xiaozhi.md`。
- **通信契约**：`docs/schemas/edge_d/`（Edge-A/B/C 已历史归档，固件只认 Edge-D），见 `edge-d-contract.md`。

## 命令速查（在子模块根目录 `esp32S_XYZ/` 下执行）

```bash
make build-u1            # 编 U1（PlatformIO，默认 release_esp32s3）
make build-u8            # 编 U8（ESP-IDF）
make flash-u1 PORT=COM3  # 烧 U1；不传 PORT 自动探测
make flash-u8 PORT=COM4  # 烧 U8
make monitor-u1          # 串口监视 U1（115200）
make monitor-u8          # 串口监视 U8
make test                # = test-schema + test-gpio + test-python + test-fake
make test-schema         # 校验 26 个 schema + examples（预期 validated=62 passed=62）
make test-gpio           # GPIO 静态检查（strapping/复用/N16R8 未引出）
make test-python         # tests/ci/ pytest
make test-fake           # 无硬件端到端（fake_ai→fake_device_server→fake_u1）
make lint                # ruff check+format（仅 tools/ tests/）
```

> **U1/U8 固件不在 CI 编译**（`.github/workflows/ci.yml` 只跑 schema/gpio/python/fake/移动端类型/Markdown 链接），因需 PlatformIO/ESP-IDF 环境。固件编译是本地动作。

## 改固件前必做

按 `esp32S_XYZ/docs/AGENTS_PONYTAIL.md`：先加载对应 skill（`esp32` / `esp-idf-handling` / `esp-pio-handling`），再动代码。
