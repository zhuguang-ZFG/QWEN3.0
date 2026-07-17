# U8 SoftAP device_secret 社区对齐与烧录门禁

## Goal

对照小智官方组件 `78/esp-wifi-connect` SoftAP `/submit` 路径，让 DLC `device_secret`（及可选 `server_host`）能可靠写入 NVS，并保证烧录/release 前 patch 不会静默丢失。本任务**不含**真机 HIL / 纸路运动验收。

## Background（已核实）

- 现有 CC patch：`/submit` 可读并写入 NVS；空字符串跳过
- 官方门户 `assets/wifi_configuration.html` 经 `EMBED_TXTFILES` 编进固件；`submitForm` 目前只 POST `{ssid, password}`
- `ensure_softap_dlc_patch.py` + `release.py` 已挂钩；`managed_components` 不入库

## Decisions

| # | 决定 | 选择 |
|---|------|------|
| D1 | SoftAP 门户是否增加 DLC 输入框 | **要加** |
| D2 | `device_secret` HTML required | **可选**（空不覆盖 NVS） |
| D3 | 字段位置 | **主 Connect 表单**（密码下方） |

## Requirements

### R1 — SoftAP 门户提交 DLC 字段

- 主 Connect 表单（密码下方）增加可选：`device_secret`、`server_host`
- `submitForm` JSON 携带上述字段；空则固件跳过写入
- 不破坏 SSID/密码与 Advanced 流程
- 文案：至少中/英可辨（`data-lang` + zh/en；其它语言可回退英文）

### R2 — 烧录/release 硬门禁

- 单一（或一组）tracked patch 覆盖：
  - `wifi_configuration_ap.cc`（已有）
  - `assets/wifi_configuration.html`（新增）
- `ensure_softap_dlc_patch.py` 检测 C++ marker **与** HTML `device_secret`；缺则 apply / 失败
- `release.py` 路径不可跳过；README 列出人肉构建命令

### R3 — 无真机可回归

- ensure 幂等自检
- 真机 SoftAP E2E / HIL：Out of Scope

## Out of Scope

- 真机烧录与手机连 SoftAP 实机验收
- 小智云对话链路、fork 整份组件

## Acceptance Criteria

- [x] 主表单可选字段进入 `/submit` JSON
- [x] 空字段不覆盖已有 NVS；Wi‑Fi 流程不回归
- [x] ensure/release 对 HTML+CC 双门禁
- [x] 文档说明构建前必跑 ensure
- [x] 无真机 HIL 即可 archive
