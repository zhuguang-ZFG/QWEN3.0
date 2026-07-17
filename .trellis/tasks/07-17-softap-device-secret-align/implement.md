# Implement — SoftAP device_secret 门户 + 门禁

## Checklist

1. [ ] 在 `managed_components/78__esp-wifi-connect` 确认 CC patch 已 apply（或先跑 ensure）
2. [ ] 编辑 `assets/wifi_configuration.html`：主表单密码下增加可选 `device_secret` / `server_host`；`submitForm` payload 带上字段；zh/en `data-lang` 文案
3. [ ] 从 component 根重生/更新 `patches/esp-wifi-connect-softap-dlc.patch`（含 `.cc` + `.html`）
4. [ ] 扩展 `ensure_softap_dlc_patch.py`：HTML 关键检测；缺则 apply；双 marker 失败则 exit 1
5. [ ] 核对 `release.py` / `apply_patches.ps1` / `idf_with_softap_patch.ps1` 仍调用 ensure
6. [ ] 更新 `firmware/u8-xiaozhi/README.md` SoftAP 节：字段可选语义 + 构建前 ensure
7. [ ] 本地：`python scripts/ensure_softap_dlc_patch.py` 幂等两次均 OK；故意去掉 HTML 字段后 ensure 应失败（再 restore）
8. [ ] 子模块如有提交：在 `esp32S_XYZ` 提交；主仓更新 submodule 指针（用户要求时再 commit）

## Validation

```powershell
cd esp32S_XYZ/firmware/u8-xiaozhi
python scripts/ensure_softap_dlc_patch.py
python scripts/ensure_softap_dlc_patch.py   # idempotent
# optional negative: strip device_secret from html → ensure must fail
```

不要求：idf 全量编译、真机 SoftAP、agent_gate（无 G-code 变更）。

## Review gates

- PRD R1–R3 / AC 全勾
- patch 可 `git apply` 于干净 component
- 无密钥入库

## Rollback

- 还原 patch 与 ensure 检测字符串；README 回退

## Notes for implementer

- Active task: `.trellis/tasks/07-17-softap-device-secret-align`
- 先读 `design.md`；HTML 经 EMBED_TXTFILES，改源文件即可
- Ponytail：最少 diff；勿重写整个多语言 translations 表（只加 zh/en 键或固定中英 label）
