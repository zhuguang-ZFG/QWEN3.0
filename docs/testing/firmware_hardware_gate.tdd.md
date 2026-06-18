# 固件与真机门禁 TDD 证据

来源：本轮继续关闭“小智服务器退役”剩余边界中的固件编译、刷机和真实硬件烟测证据缺口。

## 用户旅程

1. 作为 LiMa 维护者，我要在没有真机和 ESP-IDF 的开发机上也能确认 U8 固件默认指向 LiMa 原生 `/device/v1/ws`，避免误连回小智服务。
2. 作为发布操作者，我要在请求固件构建时看到清晰的 ESP-IDF 缺失阻塞原因，而不是把未构建误报为通过。
3. 作为硬件回归操作者，我要在请求真机烟测时强制提供真实 `device_id` 和 token，避免用假凭据声明真机闭环。
4. 作为固件发布操作者，我要在 ESP-IDF 源码树存在但 Python/export 环境损坏时看到 `esp_idf_python_env` 阻塞，而不是误判为固件源码 build 失败。

## 任务报告

- RED：先新增 `tests/test_firmware_hardware_gate.py`，运行 `.venv310\Scripts\python.exe -m pytest tests\test_firmware_hardware_gate.py -q`，失败原因为 `ImportError: cannot import name 'firmware_hardware_gate' from 'scripts'`。
- GREEN：新增 `scripts/firmware_hardware_gate.py` 与 `scripts/firmware_hardware_smoke.py`，提供静态固件契约检查、ESP-IDF build/flash opt-in 门禁、真实 `/device/v1/ws` hello smoke opt-in。
- 环境修正：本机 pytest 默认临时目录 `C:\Users\zhugu\AppData\Local\Temp\pytest-of-zhugu` 与 `D:\tmp\pytest-firmware-gate` 均被 ACL 拒绝；测试改用仓库内 `.test-tmp/` 临时目录，并在 fixture teardown 清理。
- 二次 GREEN：固件门禁改为识别真实 ESP-IDF 布局 `IDF_PATH\tools\idf.py`，并在真正执行 `set-target/build` 前用 `idf.py --version` 探测 Python 环境；缺少 `esp_idf_monitor` 时返回 `BLOCKED esp_idf_python_env`。

## 验证命令

- RED：`.venv310\Scripts\python.exe -m pytest tests\test_firmware_hardware_gate.py -q` -> 预期失败，缺少脚本模块。
- GREEN：`.venv310\Scripts\python.exe -m pytest tests\test_firmware_hardware_gate.py -q` -> `12 passed`。
- 静态门禁：`.venv310\Scripts\python.exe scripts\firmware_hardware_gate.py` -> LiMa WSS/协议检查 `PASS`，ESP-IDF build 与 hardware smoke 为未请求 `SKIP`。
- 构建门禁：`.venv310\Scripts\python.exe scripts\firmware_hardware_gate.py --build` -> 静态检查 `PASS`，`BLOCKED esp_idf_build - ESP-IDF idf.py not found on PATH`，退出码非 0。
- 本机 ESP-IDF 残留诊断：把 `C:\Users\zhugu\.espressif\tools\idf-exe\1.0.3` 加入 PATH 后运行 `--build` -> 静态检查 `PASS`，`BLOCKED esp_idf_build - IDF_PATH must point to a valid ESP-IDF source tree`，说明工具链 wrapper 存在但 ESP-IDF 源码树缺失。
- 真实源码树诊断：`$env:IDF_PATH='D:\tmp\esp-idf-v5.5.4'; .venv310\Scripts\python.exe scripts\firmware_hardware_gate.py --build` -> 固件契约 `PASS`，源码树识别通过，`BLOCKED esp_idf_python_env - ESP-IDF Python environment is not ready: No module named 'esp_idf_monitor' ...`。
- 静态检查：`.venv310\Scripts\python.exe -m ruff check scripts\firmware_hardware_gate.py scripts\firmware_hardware_smoke.py tests\test_firmware_hardware_gate.py` -> `All checks passed!`。

## 保证

| # | 保证 | 测试或命令 | 结果 |
|---|---|---|---|
| 1 | 固件默认 LiMa WSS 地址、`lima-device-v1` hello、`hello_ack`/语音回复解析存在 | `test_static_contract_checks_accept_lima_only_firmware` | PASS |
| 2 | 固件文件出现非 TLS URL、`CONFIG_LIMA_DIRECT_MODE` 或原小智协议说明会失败 | `test_static_contract_checks_reject_insecure_or_legacy_firmware` | PASS |
| 3 | `idf.py` 不在 PATH 时构建门禁返回 `blocked`，不伪装通过 | `test_build_gate_blocks_when_esp_idf_is_missing` | PASS |
| 4 | ESP-IDF 命令使用参数列表构造，不通过 shell 拼接 | `test_build_idf_commands_are_explicit_and_shell_free` | PASS |
| 5 | `idf.py.exe` wrapper 存在但 `IDF_PATH` 源码树缺失时显式阻塞 | `test_build_gate_blocks_when_idf_path_source_tree_is_missing` | PASS |
| 6 | 合法 `IDF_PATH` 源码树可通过 build preflight | `test_build_gate_accepts_valid_idf_path_source_tree` | PASS |
| 7 | CLI 默认只跑静态契约，不声明 build 或真机已跑 | `test_cli_defaults_to_static_checks_without_claiming_hardware` | PASS |
| 8 | CLI `--build` 使用注入的 PATH 检查 ESP-IDF，不绕到真实机器环境 | `test_cli_build_uses_injected_env_path` | PASS |
| 9 | `--hardware-smoke` 缺少真机凭据时阻塞，并提示所需环境变量 | `test_cli_hardware_smoke_requires_real_credentials` | PASS |
| 10 | `IDF_PATH` 指向真实 `tools/idf.py` 布局时，构建命令使用该入口而不是过期 wrapper | `test_run_idf_build_uses_idf_source_tree_tool_entrypoint` | PASS |
| 11 | ESP-IDF 源码树存在但 Python 环境缺依赖时，门禁返回 `esp_idf_python_env` 阻塞 | `test_run_idf_build_blocks_when_idf_python_env_is_broken` | PASS |

## 已知缺口

- 当前已在 `D:\tmp\esp-idf-v5.5.4` 恢复 ESP-IDF v5.5.4 源码树，门禁可识别 `tools/idf.py`；但本机 ESP-IDF Python/export 环境仍损坏，`idf.py --version` 阶段缺少 `esp_idf_monitor`，且 `export.ps1` 在当前 shell 报 `MSys/Mingw is not supported` 与 `.espressif` 虚拟环境基础 Python 路径失效，因此未执行真实 ESP-IDF 编译、刷机或串口监控。
- 当前会话没有真实设备 `LIMA_HARDWARE_DEVICE_ID` / `LIMA_HARDWARE_DEVICE_TOKEN`，因此未执行真实 U8 硬件 `hello -> hello_ack -> task_dispatch -> motion_event` 闭环。
- 下一次有 ESP-IDF 与真机时应运行：`.venv310\Scripts\python.exe scripts\firmware_hardware_gate.py --build --flash --port <COMx> --hardware-smoke --device-id <id> --device-token <token>`，并把输出补录到 `findings.md`。
