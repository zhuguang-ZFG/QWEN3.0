# Plan: 实现微信小程序真实登录（jscode2session）

## 背景

`manager-mobile` 小程序一键登录调用 `uni.login` 获取微信 code，再调用后端 `/device/v1/app/auth/login`。

当前后端 `routes/device_app_auth.py` 的 `_wechat_openid_from_code` 仅在 `wechat_dev_login_enabled()` 为 true 时返回 `wx:{code}`，否则返回空并返回 **503 WeChat login is not configured**。生产环境没有真实调用微信 `jscode2session`，导致登录不可用。

## 目标

让生产环境的后端能够用小程序 AppID + Secret 调用微信 `https://api.weixin.qq.com/sns/jscode2session`，换取真实 openid（及 unionid），完成登录；同时保留 dev mock 模式用于本地/CI 测试。

## 参考文档

- 微信官方文档（搜索总结）
  - 接口：`GET https://api.weixin.qq.com/sns/jscode2session`
  - 参数：`appid`, `secret`, `js_code`, `grant_type=authorization_code`
  - 返回：`openid`, `session_key`, `unionid`（可选）, `errcode`, `errmsg`
- 现有代码
  - `routes/device_app_auth.py`：登录入口、WeChat/phone 分支、账户查找/创建
  - `config/settings_core.py`：环境变量/flags 定义
  - `config/env.py`：`wechat_dev_login_enabled()` 读取 flag
  - `tests/test_device_app_auth.py`：现有设备 app 登录测试
  - `device_logic/http.py`：已有的请求工具（`read_body`, `err` 等）

## 阶段 1：配置与网关抽象

**做什么**
- 在 `config/settings_core.py` 新增：
  - `wechat_miniapp_appid: str = os.environ.get("LIMA_WECHAT_MINIAPP_APPID", "")`
  - `wechat_miniapp_secret: str = os.environ.get("LIMA_WECHAT_MINIAPP_SECRET", "")`
- 在 `config/env.py` 新增读取函数 `wechat_miniapp_appid()` / `wechat_miniapp_secret()`（或直接复用 settings_core FLAGS）。
- 在 `device_logic/wechat_gateway.py` 新建模块：
  - `class WechatMiniappGateway`
  - `jscode2session(code: str) -> dict` 调用微信接口，返回 `{openid, session_key, unionid}`
  - 处理 `errcode`/`errmsg`，对 40029 等返回明确错误
  - 使用 `httpx`（项目已有依赖）并设置超时 10s
  - **不暴露 `session_key` 给上层/前端**

**验证**
- `ruff` / `pyright` / `scripts/check_code_size.py` 通过
- 新增单元测试：`WechatMiniappGateway` 对成功/失败响应的解析

## 阶段 2：接入登录流程

**做什么**
- 修改 `routes/device_app_auth.py`：
  - 保留 `_wechat_openid_from_code` 作为兼容性包装
  - 当 `wechat_miniapp_appid` 与 `secret` 均配置时，使用 gateway 换取真实 openid
  - 当未配置但 `wechat_dev_login_enabled()` 为 true 时，继续 dev mock（`wx:{code}`）
  - 当两者都不满足时，返回 503 并提示未配置
- 错误返回给前端时保持现有 `err()` 格式，不泄露 `session_key`

**验证**
- 新增/更新 pytest：
  - 配置真实 appid/secret 时，mock 微信接口返回成功/失败
  - 未配置且 dev flag 关闭时返回 503
  - dev flag 开启时仍可 mock 登录
- 运行 `pytest tests/test_device_app_auth.py tests/test_routes_device_app_auth.py -v`

## 阶段 3：环境变量与文档

**做什么**
- 更新 `.env.example`：
  - 新增 `LIMA_WECHAT_MINIAPP_APPID=`
  - 新增 `LIMA_WECHAT_MINIAPP_SECRET=`
  - 保留 `LIMA_XIAOZHI_WECHAT_DEV_LOGIN=0` 说明
- 在 `docs/` 或 `findings.md` 记录：
  - 微信小程序登录需要配置 AppID + Secret
  - 配置前登录返回 503
  - dev mock 模式仅用于本地测试

**验证**
- `.env.example` 无语法错误
- `ruff check .` 通过

## 阶段 4：部署与线上验证

**做什么**
- 部署 core 切片到 VPS
- 在 VPS `/opt/lima-router/.env` 追加：
  - `LIMA_WECHAT_MINIAPP_APPID=wx095c2365e9138c2f`
  - `LIMA_WECHAT_MINIAPP_SECRET=<用户提供的 Secret>`
  - 必须 **追加而非覆盖** `.env`
- 重启服务
- 用小程序体验版/开发者工具预览测试一键登录

**验证**
- VPS `/health/ready` 200
- 小程序一键登录成功并进入首页

## 反模式/安全注意

- **不要把 AppSecret 写进代码仓库**；只通过环境变量注入
- **不要向前端返回 `session_key`**
- **不要删除 `wechat_dev_login_enabled()` 的 mock 分支**，保留本地开发路径
- 频率限制：微信限制每个用户每分钟 100 次；已有 `allow_device_auth` 做登录限流
