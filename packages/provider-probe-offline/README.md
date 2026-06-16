# provider-probe-offline

> 版本：2026-06-16（CP-5 归档）
> 关联：[`docs/provider_probe_offline_CN.md`](../../docs/provider_probe_offline_CN.md)

JDCloud 离线运维包：新 AI 提供商发现、浏览器逆向、连通性验证、后端常量**草稿**生成。

## 布局

```
packages/provider-probe-offline/
  provider_probe/          # Python 包（Cold）
    browser_service.py     # Playwright 浏览器辅助（:8092 loopback）
    discovery/             # 定时发现调度
    verify/                # 连通性 / coding eval
    reverse/               # API/定价逆向
    integrate/             # 后端草稿生成
```

主仓根目录 [`provider_probe/README.md`](../../provider_probe/README.md) 仅为指针。

## 不变量

1. **`server.py` / `server_lifespan` / `routes/*` 不得** import 本包。
2. 与运行时 **`probe_loop.py`**（后端健康探活）无关。
3. 产出须经人工 review 后合入 `backends_registry.py`；catalog 存在 ≠ 可路由。

## 运行（JDCloud `117.72.118.95`）

```bash
# 全平台部署
bash deploy/jdcloud/deploy_probe_platform.sh

# 浏览器服务健康
curl http://127.0.0.1:8092/health

# 手动跑一次发现
systemctl start lima-probe.service
```

部署脚本从 `packages/provider-probe-offline/provider_probe/` 复制到 `/opt/lima-probe/provider_probe/`。

## 本地开发 / 测试

`pytest.ini` 已将 `packages/provider-probe-offline` 加入 `pythonpath`：

```powershell
python -m pytest tests/test_browser_service.py -q
python -m py_compile packages/provider-probe-offline/provider_probe/browser_service.py
```

## 权威分层

[`docs/CODEBASE_SUBSYSTEM_TIER_CN.md`](../../docs/CODEBASE_SUBSYSTEM_TIER_CN.md) §6
