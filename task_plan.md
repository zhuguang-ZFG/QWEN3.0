# 逆向代理 Cookie 自动化 — 任务计划

## 目标
将 SCNet 和 Kimi 的 Cookie 管理集成到 `reverse_proxy_keepalive.py` 监控框架中，
补全三步落地：监控接入 → Cookie 部署 → 刷新机制分析。

## 基准数据

| 项目 | Cookie 文件 | 关键 Token | 过期 | 风险 |
|------|-----------|-----------|------|------|
| SCNet | `cpk.json` | `Token` (UUID, session) + `jsessionid` (session) | 浏览器会话结束 | ⚠️ 高危：无固定过期，session 类型随时可能失效 |
| Kimi | `kimi.txt` | `kimi-auth` (JWT access) | 2027-06-01 (364天) | ✅ 低危：JWT 有效期近一年 |

VPS: `47.112.162.80` (凭据通过 SSH key 管理)

## 步骤

### Step-1: 创建 Kimi Cookie 部署脚本
- 仿照 `scripts/provision_scnet_cookies.py` 创建 `scripts/provision_kimi_cookies.py`
- 输入: 浏览器导出 JSON → 输出: `/opt/lima-router/reverse_gateway_state/kimi_cookies.json`
- 与 SCNet 共用同样的 Cookie 加载逻辑 (`scnet_cookie.py` 重命名为通用后复用)

### Step-2: 更新 `reverse_proxy_keepalive.py`
- 添加 SCNet (port 4505) 监控条目，`auto_refresh=False`
- 修复 Kimi 条目：补上 `cookie_file` 路径，`auto_refresh=False`
- 修复 `check_backend_health` 中 SCNet 后端名 (`scnet-large-ds-flash`)
- 确保 `refresh_longcat_cookie` 不影响 SCNet/Kimi

### Step-3: 刷新机制分析 + 落地
- SCNet: Token=UUID session cookie，**无可用的 refresh token** → 结论：只能全量重新登录
- Kimi: `kimi-auth` JWT 1年有效 → 结论：**当前不需要刷新**，过期前一个月再处理
- 写入 findings.md 作为后续参考

### Step-4: VPS 部署指令
- 写入 `deploy/reverse/README.md` 补全 Kimi 部署步骤

## 产物
- `scripts/provision_kimi_cookies.py` (新建)
- `scripts/reverse_proxy_keepalive.py` (修改)
- `findings.md` (更新刷新分析)
- `deploy/reverse/README.md` (补 Kimi 部署步骤)
