# LiMa 部署指南

## 部署流程

### 方法一：本地验证 + 全量同步（推荐）

这是最安全的部署方式，避免版本不匹配导致的生产环境故障。

#### 1. 本地验证

```bash
# 启动本地服务
.venv310\Scripts\python.exe server.py

# 验证健康检查
curl http://localhost:8080/health

# 验证管理页面
curl http://localhost:8080/admin

# 验证聊天 API（可选）
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test" \
  -d '{"model":"gpt-4","messages":[{"role":"user","content":"hi"}],"stream":false}'
```

#### 2. 全量同步到 VPS

```bash
# 使用 tar + ssh 管道同步
tar --exclude='.git' \
    --exclude='.venv*' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='.env' \
    --exclude='*.log' \
    --exclude='*.db' \
    --exclude='*.db-journal' \
    --exclude='test_*.html' \
    --exclude='test_*.py' \
    -czf - . | \
ssh -i ~/.ssh/id_ed25519 root@47.112.162.80 \
  'cd /opt/lima-router && tar -xzf -'
```

#### 3. 重启服务

```bash
ssh -i ~/.ssh/id_ed25519 root@47.112.162.80 'systemctl restart lima-router'
```

#### 4. 验证部署

```bash
bash scripts/verify_deployment.sh
```

预期输出：
```
=== 验证 VPS 部署 ===

1. 健康检查
✓ 健康检查通过

2. 管理页面
✓ 管理页面可访问

3. 后端 API（未认证）
✓ 后端 API 正常（需要认证）

=== 所有验证通过 ===
```

---

### 方法二：单文件部署（快速修复）

仅用于紧急修复单个文件，不推荐用于大规模更新。

```bash
# 部署单个文件
python scripts/deploy_unified.py --files server.py

# 部署多个文件
python scripts/deploy_unified.py --files routing_engine.py routing_classifier.py

# 部署 routes 目录下的文件
python scripts/deploy_unified.py --files routes/admin.py routes/admin_api.py
```

---

## 环境变量

生产环境必需的环境变量（配置在 VPS 的 `/opt/lima-router/.env`）：

```bash
# 基础配置
LIMA_ENV=production
SENTRY_DSN=your_sentry_dsn

# 后端配置
LONGCAT_KEY=your_key
DEEPSEEK_KEY=your_key
OPENROUTER_KEY=your_key

# 管理员配置
ADMIN_TOKEN=your_admin_token
```

---

## 故障排查

### 服务启动失败

```bash
# 查看服务状态
ssh root@47.112.162.80 'systemctl status lima-router'

# 查看最近日志
ssh root@47.112.162.80 'journalctl -u lima-router --since "10 minutes ago" --no-pager | tail -50'

# 检查端口占用
ssh root@47.112.162.80 'lsof -i :8080'
```

### 健康检查失败

```bash
# 直接访问健康端点
curl https://chat.donglicao.com/health

# 检查 Nginx 配置
ssh root@47.112.162.80 'nginx -t'
```

### 版本不匹配

如果出现 `AttributeError` 或 `TypeError` 等版本不匹配错误：

1. **立即回滚**：使用方法一（全量同步）部署已知良好版本
2. **检查依赖**：确保 VPS 上的所有 Python 依赖与本地一致
3. **重启服务**：`systemctl restart lima-router`

---

## 监控和日志

### 实时日志

```bash
# 跟踪服务日志
ssh root@47.112.162.80 'journalctl -u lima-router -f'

# 查看最近错误
ssh root@47.112.162.80 'journalctl -u lima-router --since "1 hour ago" | grep ERROR'
```

### 健康检查

生产环境提供以下监控端点：

- **健康检查**：`GET /health`
- **管理后台**：`GET /admin`（需要认证）
- **后端状态**：`GET /admin/api/backends`（需要认证）
- **统计信息**：`GET /admin/api/stats`（需要认证）

---

## 生产环境信息

- **VPS 地址**：47.112.162.80
- **服务路径**：`/opt/lima-router/`
- **服务名称**：`lima-router.service`
- **监听端口**：8080（内网），443（Nginx 反向代理）
- **访问地址**：https://chat.donglicao.com

---

## 最佳实践

### ✅ 推荐做法

1. **本地测试优先**：所有改动先在本地验证
2. **全量同步**：使用方法一进行部署，保持版本一致
3. **监控日志**：部署后观察 2-3 分钟日志
4. **验证功能**：运行自动化验证脚本
5. **保留回滚点**：部署前记录当前 git commit

### ❌ 避免做法

1. ❌ 直接在 VPS 上修改代码
2. ❌ 只部署部分文件导致版本不匹配
3. ❌ 不经测试直接部署到生产
4. ❌ 跳过验证步骤
5. ❌ 在高峰期部署（除非紧急修复）

---

## 应急流程

### 生产故障快速恢复

1. **立即回滚到上一个工作版本**
   ```bash
   # 切换到已知良好的 commit
   git checkout <last-good-commit>
   
   # 全量同步
   bash scripts/full_sync.sh
   ```

2. **重启服务**
   ```bash
   ssh root@47.112.162.80 'systemctl restart lima-router'
   ```

3. **验证恢复**
   ```bash
   bash scripts/verify_deployment.sh
   ```

4. **调查原因**
   - 在本地复现问题
   - 修复后再次部署

---

## 相关脚本

- `scripts/deploy_unified.py` - 单文件/多文件部署
- `scripts/full_sync.py` - 全量同步脚本（rsync，需 Linux/WSL）
- `scripts/verify_deployment.sh` - 部署验证脚本
- `scripts/repo_stats.py` - 代码统计

---

最后更新：2026-06-09
