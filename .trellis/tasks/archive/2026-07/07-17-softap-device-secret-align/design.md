# Design — SoftAP device_secret 门户 + 门禁

## Boundaries

| 层 | 改动 | 不改 |
|----|------|------|
| `78__esp-wifi-connect`（managed） | 经 **tracked patch** 改 HTML + 已有 CC | 不上游 PR（可后续）；不 fork 整库 |
| U8 `scripts/` | 扩展 ensure 检测 HTML 关键字符串 | 不改 IDF 工具链本身 |
| 云端 / 小程序 | 无 | — |

## Contracts

### `/submit` JSON（已有 CC + 门户对齐）

```json
{
  "ssid": "...",
  "password": "...",
  "device_secret": "...",   // optional; omit or "" → 不写 NVS
  "server_host": "..."      // optional; same
}
```

NVS：`wifi` 命名空间键 `device_secret` / `server_host`（现有 `SaveDlcProvisioningFields`）。

### SoftAP HTML

- 位置：主表单 `#password` 下方两个 `<input>`（非 required）
- `submitForm` payload 增加两字段
- 嵌入方式：组件 `EMBED_TXTFILES` → 改 `assets/wifi_configuration.html` 后需重新 apply patch + 编译

## Patch 策略

1. 在已 apply 的 tree 上改 HTML（或临时 apply CC patch → 改 HTML → `git diff` 重生完整 patch）
2. 更新 `patches/esp-wifi-connect-softap-dlc.patch` 包含 **两个文件** 的 diff（相对 component 根，`git apply` 于 `78__esp-wifi-connect/`）
3. `ensure_softap_dlc_patch.py`：
   - 已有：`SaveDlcProvisioningFields` in `.cc`
   - 新增：`device_secret` 出现在 `assets/wifi_configuration.html`（且 ideally 在 `submitForm`/`JSON.stringify` 路径附近）
   - 缺任一 → apply 整包 patch；仍缺 → exit 1

## Tradeoffs

| 方案 | 取舍 |
|------|------|
| Patch HTML（选用） | 与现有 CC patch 一致；组件升级可能冲突，ensure 会失败并提示 |
| 运行时注入 HTML | 改动 CC 更多，偏离官方嵌入模型 |
| Fork 组件 | 过重（ponytail 否决） |

## Compatibility / Rollback

- 旧固件：无门户字段，行为不变
- 回滚：移除 HTML hunk 或整文件 patch，ensure marker 同步回退
- 不碰 Advanced `/advanced/submit`

## Rollout

- 仅固件源码 + 子模块指针；无云端发版依赖
- 验证：ensure 脚本 +（有板后再）人工 SoftAP（本任务不阻塞）
