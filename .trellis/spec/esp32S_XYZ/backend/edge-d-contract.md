# Edge-D 通信契约 + 工具链 / 测试

> Edge-D 是 U8↔U1 之间**唯一活跃的固件契约**。本仓库的 Edge-A/B/C 已历史归档（服务端迁到 LiMa `device_gateway`），固件代码只认 Edge-D。

## 四边界现状（只 Edge-D 活跃）

| Edge | 边界 | schema 数 | 状态 |
|------|------|----------|------|
| Edge-A | Client↔BusinessServer WSS | 14 | **历史归档**（README 头部带归档横幅） |
| Edge-B | BusinessServer↔DeviceServer HTTP | 3 | **历史归档** |
| Edge-C | DeviceServer↔U8 WSS | 3 | **历史归档** |
| Edge-D | U8↔U1 UART JSON | 6 | **活跃，固件唯一契约** |

合计 26 schemas + 36 examples，JSON Schema **2020-12**，全部 `additionalProperties: false`，用 `const` 做类型判别。

## Edge-D 物理帧

帧形态：`@{json}\n`（前缀 `@` + JSON 对象 + 换行）。`docs/schemas/edge_d/` 只定义 `{json}` 对象，不含前缀和行尾。对齐 `docs/架构定稿-v2.md` §5.4 / §15.4。

## 6 个 schema（`docs/schemas/edge_d/`）

| schema | 方向 | 关键字段 |
|--------|------|---------|
| `cmd` | U8→U1 | `msg_id`(必,string)、`cmd`(必,enum 11 值)、`task_id`、`x/y/z`、`feed`(>0)、`total_segments`/`segment_index`(≥0)、`segment_cmd`(M/L) |
| `ack` | U1→U8 | 命令收妥确认 |
| `status` | U1→U8 | `msg_id`、`type`(const "status")、`state`(enum)、`homed`、`position{x,y,z}`、`alarm_code` |
| `result` | U1→U8 | 命令执行结果 |
| `device_info` | U1→U8 | 设备/固件信息 |
| `error` | U1→U8 | 独立错误帧（承载错误码） |

**cmd enum（11 值，逐字取自 `cmd.schema.json`）**：`GET_STATUS`、`GET_DEVICE_INFO`、`HOME`、`MOVE`、`PAUSE`、`RESUME`、`STOP`、`ESTOP`、`PATH_BEGIN`、`PATH_SEG`、`PATH_END`。

**status `state` enum（7 值）**：`IDLE`、`HOMING`、`RUNNING`、`PAUSED`、`ALARM`、`ERROR`、`ESTOP`。

**错误码（架构 v2 §14）**：`E001`/`E002`/`E005`/`E006`/`E007`/`E008`/`E009`。
> 注意区分：status 帧的 `alarm_code` 字段是这些错误码（或 null）；status 帧的 `error_code` 字段**恒为 null**——错误码走**独立的 `error` 帧**，不要往 status 帧塞。

## 字段演进规则（铁律）

`docs/schemas/README.md`：**任何字段变更先改契约 artifact（schema + example），再改实现和测试。** 完整顺序：

1. 改 `docs/schemas/edge_d/<x>.schema.json` + 对应 `examples/`
2. 改对应 fake（`tools/fake_u1/` 等）
3. 改固件实现（U8 `u1_protocol_client`/`motion_executor`；U1 Grbl 侧）
4. 跑 `make test`（含 `test_edge_d_firmware_static.py`）

## 固件级契约强约束（最重要的单一测试文件）

`tests/ci/test_edge_d_firmware_static.py`（42KB，全项目最大测试）—— 直接 grep U8/U1 源码 token，把 Edge-D 契约**焊死在固件实现里**。它断言的真实路径（改这些文件必同步改契约/测试）：

- U8：`u1_protocol_client.{h,cc}`、`motion_executor.{h,cc}`、`ota.{h,cc}`、`application.cc`、`sdkconfig.defaults`、`partitions/v2/16m.csv`
- U1：`Protocol.cpp`、`Settings.cpp`、`MotionControl.cpp`、`Config.h`

**含义**：改协议字段而不更新这个测试，CI 会 fail；改这些源码文件而不走契约流程，会触发 token 不匹配。

## 校验工具（`tools/`）

| 工具 | 作用 | 规则要点 |
|------|------|---------|
| `validate_schemas.py` | `make test-schema`；`Draft202012Validator` 校验每个 schema 自身合法 + 每个 example 恰好匹配同 edge 下某 schema | 预期 `validated=62 passed=62 failed=0`（26 schema + 36 example） |
| `check_gpio.py` | `make test-gpio`；GPIO 静态检查 | (1) 同 MCU 重复 OUTPUT 报错；(2) `STRAPPING_PINS={0,3,45,46}` 当 OUTPUT 必须带"已知风险"标记；(3) **U8 TXD 必须 = U1 RXD**（`u8_uart_tx.gpio != 11` 报错）；(4) `UNAVAILABLE_PINS={35,36,37,41,42}`（N16R8 未引出）禁用；(5) 弱证据引脚 |

## Fake 仿真器（无硬件开发的事实对端）

四个 fake，均带 CLI + 单测，是无硬件端到端联调对端（`make fake-u1` / `fake-ai` / `fake-server`）：

- `tools/fake_u1/` — Edge-D U1 仿真，含 `route_policy_validator.py`，可注入错误码 E001/E005/E006/E008。**黄线**：存在两套实现（`app.py` 同步 + `fake_u1.py` 异步），见 `docs/code-quality-audit-2026-05-17.md`，有行为漂移风险。
- `tools/fake_ai/`、`tools/fake_device_server/`、`tools/fake_lima_u8/`

`make test-fake` 跑 `test_fake_integration.py`：fake_ai → fake_device_server → fake_u1 端到端。

## 测试体系

```bash
make test          # = test-schema + test-gpio + test-python + test-fake
make test-schema   # 62 通过
make test-gpio     # GPIO 静态检查
make test-python   # tests/ci/ pytest（含 test_edge_d_firmware_static.py）
make test-fake     # 无硬件端到端
make lint          # ruff check+format tools/ tests/
```

- Python 测试在 `tests/ci/`（10 文件）+ `tools/` 内自测。
- 板内 C++ 测试：`main/test_u8_mqtt_hex_decode.cpp`、`test_u8_ota_allowlist.cpp`、`boards/zhuguang/dlc-motor-control-p1-ai/test_u8_protocol_logic.cpp`。
- 规模：审计报告称 243+/251 测试。
- **U1/U8 固件不在 CI 编译**（需 PlatformIO/ESP-IDF 环境）；CI 只跑 schema/gpio/python/fake/移动端类型/Markdown 链接。

## 禁则（吸收自 `docs/code-quality-audit-2026-05-17.md` 红线/黄线）

- 禁硬编码 API 密钥 / token（`test_vectorize.py` 曾踩）。
- 禁 bare `except`（吞异常）。
- `platformio.ini` lib 版本范围勿过宽（现 `TMCStepper@>=0.7.3,<0.8.0` 是范例）。
- `fake_u1` 双实现（同步/异步）是已知黄线，改之前确认对齐哪套。
