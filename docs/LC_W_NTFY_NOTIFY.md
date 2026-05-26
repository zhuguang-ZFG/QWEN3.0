# LiMa ntfy 通知 smoke（雷达 §八）

> **Default off:** `LIMA_NTFY_SMOKE=0`

[ntfy](https://ntfy.sh) 为自建/公有推送通道；LiMa 已有 `telegram_notify`，ntfy 作可选 Operator 旁路。

```powershell
$env:LIMA_NTFY_SMOKE=1
$env:LIMA_NTFY_TOPIC="your-secret-topic"
# 或自托管：
# $env:LIMA_NTFY_URL="https://ntfy.example.com/lima-ops"
python scripts/smoke_ntfy.py
```

MVP 不默认打开；仅 smoke 验证 POST 可达。
