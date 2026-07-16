# 修复前门禁基线

| 门禁 | 命令/环境 | 结果 | 证据摘要 |
| --- | --- | --- | --- |
| Python | `.venv310` Python 3.10.20 | PASS | 系统 Python 3.13 不作为权威解释器 |
| pytest | `.venv310/Scripts/python.exe -m pytest tests/ -v -q` | PASS | 1736 passed, 3 skipped, 0 failed；约 80s |
| collect-only | `.venv310/Scripts/python.exe -m pytest --collect-only -q` | PASS | 生产测试可完整收集 |
| Ruff | `ruff check .` | PASS | 0 error |
| Ruff format | `ruff format --check` | PASS | 572 files already formatted |
| Pyright | `.venv310/Scripts/pyright.exe` | WARN | 0 errors；`DeviceTaskStore.ping/close` 缺失 2 warnings |
| code size | `python scripts/check_code_size.py` | FAIL | 错扫 `.venv`；1755 个第三方超限 |
| code size tracked | `... check_code_size.py --git-tracked` | FAIL | 错扫 `.trellis`；产品侧 2 个文件、9 个函数超限 |
| Bandit CI 口径 | CI 同款命令 | PASS/WARN | 0 High；命令静默包含不存在的 `lima_mcp_stdio` |
| Bandit 活跃生产树 | 扩大到所有活跃路径 | REVIEW | 14 Medium 候选，需逐项回溯；已排除 URL/IP 校验等误报 |
| pip-audit | `PYTHONUTF8=1 pip-audit -r requirements_server.txt` | PASS | No known vulnerabilities found |
| CodeGraph | `codegraph sync .` | PASS | 索引同步；330 个变化；未使用 GitNexus |
| 小程序 type | `pnpm type-check` | PASS | 0 error |
| 小程序 i18n | `pnpm check:i18n` | PASS | 794 keys 一致 |
| 小程序 build | `pnpm build:mp-weixin` | PASS | 构建成功 |
| 小程序 lint | `pnpm lint` | FAIL | 54 errors, 27 warnings；含格式与未使用导入 |
| U1 build | `pio run -e release_esp32s3` | PASS | Flash 45.4%，RAM 15.7% |
| U1 native | `pio test -e native` | FAIL | `[env:native]` 继承 `board=esp32dev`，0 tests executed |
| U8 静态契约 | `firmware_hardware_gate.py` 静态部分 | PASS | LiMa WSS/协议字符串契约通过 |
| U8 build | `firmware_hardware_gate.py --build` | BLOCKED | 当前无有效 `IDF_PATH/IDF_TOOLS_PATH`，`idf.py` 不可用 |
| fz standard | `agent_gate.py --profile standard` | FAIL | protocol 43/43、integrity/allowlist 绿；hardware 14/19 |

## fz 分层诊断

- MPos 对 `move_x_10`、`move_xy_delta` 正确，但运行中 `step_window` 读取为 0。
- `run_hw_sim.py` 仅在仿真进程退出后明确保证 step log flush，却在进程运行中以 50-150ms sleep 读取同一日志。
- 后续 `check_mode` 窗口一次读入多个动作的累计步数，符合缓冲延迟，而非 check mode 真实运动。
- 当前定性：fz harness 缓冲/观测窗口缺陷强证据；不是 QWEN 产品运动契约失败证据。修复只能落在 fz。

## 环境限制

- 无 ESP-IDF 工具链，不能声称 U8 编译通过。
- 无真机、纸路、蓝牙/OTA/HIL 证据。
- 未执行生产 strict voice E2E、部署和公网写操作；修复后仅在已有无副作用凭据时运行。
