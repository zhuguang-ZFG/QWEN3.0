# LiMa 业务错误码表（AUDIT-6-A3）

> 本文档定义 LiMa Device App API 的业务错误码语义。
> 业务码（4xxx）与 HTTP 状态码解耦：`err(code, message, http_status)`。
> 同一业务码全局唯一语义。

## HTTP 标准码（直接复用）

| code | HTTP | 语义 | 示例 |
|------|------|------|------|
| 400 | 400 | 请求参数缺失/格式错误 | `deviceSn is required` |
| 401 | 401 | 未认证 / 凭证无效 | `Invalid verification code` |
| 403 | 403 | 已认证但无权限 | `only the device owner can unbind` |
| 404 | 404 | 资源不存在 | `device not found` |

## 业务码（4xxx，Device App 专用）

| code | HTTP | 语义 | 文件 | 说明 |
|------|------|------|------|------|
| 4001 | 400 | **不支持的能力（capability）** | `device_app_tasks.py` | `run_path`/`write_text` 等能力不在白名单 |
| 4002 | 400 | **任务参数校验失败** | `device_app_tasks.py` | 缺 path/feed 或格式非法 |
| 4003 | 400 | **任务构建失败** | `device_app_tasks.py` / `device_app_assets.py` | 路径生成/资产处理失败 |
| 4004 | 400 | **激活码无效** | `device_app_api.py` | 设备激活码错误或已用 |

## 历史冲突说明（已记录，待治理）

> AUDIT-6 审查发现以下业务码在不同端点曾复用同一数字但语义不同。
> 新代码请避免复用，未来迁移时统一为唯一语义。

| code | 冲突文件 | 冲突语义 | 处理 |
|------|----------|----------|------|
| 4002 | `device_app_tasks.py`（参数校验失败） vs `device_app_auth.py`（密码未设置） | 两端点共用 4002 | 待治理：auth 改用新码 4101 |
| 4003 | `device_app_tasks.py`（任务构建失败） vs `device_app_auth.py`（旧密码错误） | 两端点共用 4003 | 待治理：auth 改用新码 4102 |

## 错误响应格式

```json
{
  "code": 4002,
  "message": "validation failed: path is required"
}
```

- OpenAI 兼容层（`/v1/chat/completions`）使用 `{"error": {"message": "...", "type": "..."}}`（OpenAI 标准）。
- Device App 层使用 `{"code": <int>, "message": "<str>"}`（本文档定义）。
- 图片生成层使用 `{"error": {"message": "...", "type": "..."}}`（与 OpenAI 兼容层一致）。
