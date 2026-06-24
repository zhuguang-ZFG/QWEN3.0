# OTA 升级

LiMa 提供云端 OTA 发布门、金丝雀和灰度发布能力，用于管理 ESP32 固件升级。

## 接口前缀

```text
https://chat.donglicao.com/device/v1/ota
```

所有 OTA 管理接口需要私有 API Key。

## 发布门

发布门确保所有准入条件通过后才允许部署：

```http
GET /device/v1/ota/release/status
```

响应：

```json
{
  "ready": false,
  "criteria": {
    "smoke_passed": true,
    "signing_verified": false
  }
}
```

标记条件通过：

```http
POST /device/v1/ota/release/criteria?name=signing_verified&passed=true
```

## 部署新版本

```http
POST /device/v1/ota/deploy/2.1.0
Content-Type: application/json

{
  "hash": "abcd1234...",
  "url": "https://ota.example.com/firmware-2.1.0.bin"
}
```

## 金丝雀

```http
POST /device/v1/ota/canary/devices/dev-001
POST /device/v1/ota/canary/record-success/dev-001
POST /device/v1/ota/canary/record-failure/dev-001
GET /device/v1/ota/canary/status
```

## v1 → v2 分区表迁移警告

已在 v1 分区表上量产的设备 **不能** 通过 OTA 直接升级到 v2，必须 USB 串口全量烧录。详见 `docs/FIRMWARE_V1_V2_OTA_MIGRATION_CN.md`。

## 安全建议

- 所有固件包必须使用签名私钥签名，设备端用公钥校验
- 部署前先在金丝雀设备上验证 24 小时
- 保留回滚用旧版本完整 bin
