# 固件与真机门禁 TDD 证据

来源：本轮继续关闭“小智服务器退役”剩余边界中的固件编译、刷机和真实硬件烟测证据缺口。

## 用户旅程

1. 作为 LiMa 维护者，我要在没有真机和 ESP-IDF 的开发机上也能确认 U8 固件默认指向 LiMa 原生 `/device/v1/ws`，避免误连回小智服务。
2. 作为发布操作者，我要在请求固件构建时看到清晰的 ESP-IDF 缺失阻塞原因，而不是把未构建误报为通过。
3. 作为硬件回归操作者，我要在请求真机烟测时强制提供真实 `device_id` 和 token，避免用假凭据声明真机闭环。

## 任务报告

- RED：先新增 `tests/test_firmware_hardware_gate.py`，运行 `.venv310\Scripts\python.exe -m pytest tests\test_firmware_hardware_gate.py -q`，失败原因为 `ImportError: cannot import name 'firmware_hardware_gate' from 'scripts'`。
- GREEN：新增 `scripts/firmware_hardware_gate.py`，提供静态固件契约检查、ESP-IDF build/flash opt-in 门禁、真实 `/device/v1/ws` hello smoke opt-in。
- 环境修正：本机 pytest 默认临时目录 `C:\Users\zhugu\AppData\Local\Temp\pytest-of-zhugu` 与 `D:\tmp\pytest-firmware-gate` 均被 ACL 拒绝；测试改用仓库内 `.test-tmp/` 临时目录，并在 fixture teardown 清理。

## 验证命令

- RED：`.venv310\Scripts\python.exe -m pytest tests\test_firmware_hardware_gate.py -q` -> 预期失败，缺少脚本模块。
- GREEN：`.venv310\Scripts\python.exe -m pytest tests\test_firmware_hardware_gate.py -q` -> `8 passed`。
- 静态门禁：`.venv310\Scripts\python.exe scripts\firmware_hardware_gate.py` -> LiMa WSS/协议检查 `PASS`，ESP-IDF build 与 hardware smoke 为未请求 `SKIP`。
- 构建门禁：`.venv310\Scripts\python.exe scripts\firmware_hardware_gate.py --build` -> 静态检查 `PASS`，`BLOCKED esp_idf_build - ESP-IDF idf.py not found on PATH`，退出码非 0。
- 静态检查：`.venv310\Scripts\python.exe -m ruff check scripts\firmware_hardware_gate.py tests\test_firmware_hardware_gate.py` -> `All checks passed!`。

## 保证

| # | 保证 | 测试或命令 | 结果 |
|---|---|---|---|
| 1 | 固件默认 LiMa WSS 地址、`lima-device-v1` hello、`hello_ack`/语音回复解析存在 | `test_static_contract_checks_accept_lima_only_firmware` | PASS |
| 2 | 固件文件出现非 TLS URL、`CONFIG_LIMA_DIRECT_MODE` 或原小智协议说明会失败 | `test_static_contract_checks_reject_insecure_or_legacy_firmware` | PASS |
| 3 | `idf.py` 不在 PATH 时构建门禁返回 `blocked`，不伪装通过 | `test_build_gate_blocks_when_esp_idf_is_missing` | PASS |
| 4 | ESP-IDF 命令使用参数列表构造，不通过 shell 拼接 | `test_build_idf_commands_are_explicit_and_shell_free` | PASS |
| 5 | CLI 默认只跑静态契约，不声明 build 或真机已跑 | `test_cli_defaults_to_static_checks_without_claiming_hardware` | PASS |
| 6 | CLI `--build` 使用注入的 PATH 检查 ESP-IDF，不绕到真实机器环境 | `test_cli_build_uses_injected_env_path` | PASS |
| 7 | `--hardware-smoke` 缺少真机凭据时阻塞，并提示所需环境变量 | `test_cli_hardware_smoke_requires_real_credentials` | PASS |

## 已知缺口

- 当前机器没有 `idf.py`，因此未执行真实 ESP-IDF 编译、刷机或串口监控。
- 当前会话没有真实设备 `LIMA_HARDWARE_DEVICE_ID` / `LIMA_HARDWARE_DEVICE_TOKEN`，因此未执行真实 U8 硬件 `hello -> hello_ack -> task_dispatch -> motion_event` 闭环。
- 下一次有 ESP-IDF 与真机时应运行：`.venv310\Scripts\python.exe scripts\firmware_hardware_gate.py --build --flash --port <COMx> --hardware-smoke --device-id <id> --device-token <token>`，并把输出补录到 `findings.md`。
