# External Repositories (Decoupled)

> Updated: 2026-06-05

LiMa 主仓库不再通过 git submodule 跟踪以下项目。在本地需要时单独 clone 到任意路径（也可放在仓库内对应目录，已被 `.gitignore` 忽略）。

| Project | Remote | Typical local path |
|---------|--------|-------------------|
| LiMa CLI (legacy worker) | https://github.com/zhuguang-ZFG/deepcode-cli.git | `D:\QWEN3.0\deepcode-cli\` or `D:\LIMA-external\deepcode-cli\` |
| ESP32 / U8 firmware | https://github.com/zhuguang-ZFG/esp32S_XYZ.git | `D:\LIMA-external\esp32S_XYZ\` |
| OpenCode upstream (reference) | https://github.com/anomalyco/opencode.git | `D:\QWEN3.0\opencode-source\` |

## Clone examples (PowerShell)

```powershell
# OpenCode reference (for transform.ts parity checks)
git clone https://github.com/anomalyco/opencode.git D:\QWEN3.0\opencode-source

# LiMa CLI — maintenance mode; OpenCode is the primary IDE client
git clone https://github.com/zhuguang-ZFG/deepcode-cli.git D:\QWEN3.0\deepcode-cli

# Hardware firmware (optional, P3)
git clone https://github.com/zhuguang-ZFG/esp32S_XYZ.git D:\LIMA-external\esp32S_XYZ
```

## Integration boundary

- **LiMa Server** (`D:\QWEN3.0`): routing, memory, APIs, VPS deploy — this repo.
- **deepcode-cli**: optional terminal worker; task contract smoke may use `LIMA_TEST_CLI_REPO` env pointing at your clone path.
- **esp32S_XYZ**: device firmware; pairs with `device_gateway/` on the server when hardware work resumes.

Historical submodule workflow: see archived `docs/LIMA_MANAGEMENT.md`.
