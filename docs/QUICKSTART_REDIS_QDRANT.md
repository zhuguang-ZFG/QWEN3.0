# 京东云增强部署 - 快速开始指南

> **状态**: 就绪部署  
> **日期**: 2026-06-08  
> **原则**: Superpowers（文档先行 ✓、本地验证、可回滚、渐进式）

---

## 📋 部署检查清单

### ✅ 已完成（文档先行）
- [x] 创建部署计划文档
- [x] 创建 Redis 缓存增强代码
- [x] 创建部署脚本（5个）
- [x] 创建测试脚本
- [x] 设计回滚方案

### ⏳ 待执行（本地验证 → VPS 部署）
- [ ] Phase 1.1-1.3: 京东云安装 Redis
- [ ] Phase 1.4: 阿里云测试连接
- [ ] Phase 1.5: 集成到 LiMa
- [ ] Phase 1.6: 验证缓存命中
- [ ] Phase 1.7: 监控 24 小时
- [ ] Phase 2: Qdrant 部署（Phase 1 成功后）

---

## 🚀 快速开始

### 方式 A: 自动化部署（推荐）

```powershell
# 在本地 D:\QWEN3.0 执行
python scripts\deploy_redis_qdrant_jdcloud.py
```

脚本会自动：
1. 连接京东云
2. 上传安装脚本
3. 安装 Redis
4. 配置安全参数
5. 配置防火墙
6. 生成并显示密码

### 方式 B: 手动部署（逐步验证）

#### Step 1: 连接京东云

```powershell
# 使用密码登录
ssh root@117.72.118.95
# 密码: XINdandan521!
```

#### Step 2: 上传脚本

```powershell
# 在本地执行
scp deploy/jdcloud/install_redis.sh root@117.72.118.95:/tmp/
scp deploy/jdcloud/configure_redis.sh root@117.72.118.95:/tmp/
scp deploy/jdcloud/configure_firewall.sh root@117.72.118.95:/tmp/
```

#### Step 3: 执行安装（京东云）

```bash
# 在京东云 SSH 会话中执行
bash /tmp/install_redis.sh
bash /tmp/configure_redis.sh
bash /tmp/configure_firewall.sh
```

#### Step 4: 保存密码

`configure_redis.sh` 执行时会生成并显示密码，**务必保存**！

格式：`REDIS_PASSWORD=<32位随机字符串>`

#### Step 5: 测试连接（阿里云）

```bash
# SSH 登录阿里云 VPS
ssh root@47.112.162.80

# 设置密码（替换为实际密码）
export REDIS_PASSWORD='<京东云生成的密码>'

# 测试连接
bash scripts/test_redis_connection.sh
```

---

## 📁 已创建的文件

### 文档
```
docs/superpowers/plans/
  └─ 2026-06-08-redis-qdrant-deployment-plan.md  # 完整部署计划
```

### 代码
```
semantic_cache_enhanced.py                        # Redis 缓存增强模块
```

### 部署脚本
```
deploy/jdcloud/
  ├─ install_redis.sh                             # Redis 安装
  ├─ configure_redis.sh                           # Redis 配置（生成密码）
  └─ configure_firewall.sh                        # 防火墙配置

scripts/
  ├─ deploy_redis_qdrant_jdcloud.py               # 自动化部署脚本
  └─ test_redis_connection.sh                     # 连接测试脚本
```

---

## 🎯 执行顺序

### Phase 1: Redis 缓存层（预计 30-60 分钟）

1. **京东云部署**（15-20 分钟）
   - 安装 Redis
   - 配置安全参数
   - 配置防火墙

2. **阿里云验证**（5-10 分钟）
   - 测试连接
   - 验证读写

3. **LiMa 集成**（15-30 分钟）
   - 部署 `semantic_cache_enhanced.py`
   - 配置环境变量
   - 重启服务
   - 验证缓存

4. **监控验证**（24 小时）
   - 观察缓存命中率
   - 检查性能指标
   - 确认稳定性

### Phase 2: Qdrant 向量检索（Phase 1 成功后）

待 Phase 1 验证通过后执行。

---

## ⚠️ 重要注意事项

### 1. 密码安全
- `configure_redis.sh` 会生成 32 位随机密码
- **务必立即保存**，脚本只显示一次
- 建议保存位置：
  - 本地：`C:\Users\zhugu\Downloads\redis_password.txt`
  - 密码管理器（1Password/LastPass）
  - 阿里云 VPS：`/opt/lima-router/.env`

### 2. 防火墙规则
- Redis 端口 6379 **仅允许阿里云 VPS (47.112.162.80)** 访问
- 其他 IP 无法连接
- SSH 端口 22 保持开放（避免锁死）

### 3. 回滚方案
如果部署失败或出现问题：

```bash
# 京东云执行
systemctl stop redis-server
systemctl disable redis-server
apt remove -y redis-server
```

不影响现有 LiMa 服务（独立部署）。

---

## 📊 预期效果

### Phase 1 成功标准

| 指标 | 目标 | 验证方法 |
|------|------|---------|
| Redis 可用性 | 99%+ | `curl http://47.112.162.80:8080/api/cache/health` |
| 缓存命中率 | >20% | `curl http://47.112.162.80:8080/api/cache/stats` |
| 命中延迟 | <100ms | 日志分析 |
| API 调用减少 | >15% | 对比部署前后 |

### 收益估算

```
场景: 每天 100 次请求，30% 重复

之前:
  - 100 次 API 调用
  - 平均延迟 3 秒
  - 总耗时 300 秒

之后:
  - 70 次 API 调用（30 次缓存命中）
  - 平均延迟 2.1 秒（70*3s + 30*0.05s）
  - 总耗时 211.5 秒

节省:
  - API 调用 -30%
  - 延迟 -29.5%
  - 成本 -30%
```

---

## 🔧 故障排查

### 问题 1: 京东云 SSH 连接失败

```powershell
# 检查密码
cat C:\Users\zhugu\Downloads\VPS.txt

# 检查网络
ping 117.72.118.95
```

### 问题 2: Redis 安装失败

```bash
# 查看详细错误
journalctl -u redis-server -n 50

# 检查端口占用
netstat -tlnp | grep 6379
```

### 问题 3: 阿里云无法连接 Redis

```bash
# 测试网络连通性
telnet 117.72.118.95 6379

# 检查防火墙规则（京东云）
ufw status numbered
```

### 问题 4: 缓存未命中

```bash
# 检查环境变量（阿里云）
env | grep REDIS

# 检查 LiMa 日志
journalctl -u lima-router -f | grep -i cache
```

---

## 📞 下一步行动

### 现在就可以做：

**选项 1: 自动化部署（最快）**
```powershell
cd D:\QWEN3.0
python scripts\deploy_redis_qdrant_jdcloud.py
```

**选项 2: 手动部署（逐步验证）**
```powershell
# Step 1: 连接京东云
ssh root@117.72.118.95

# Step 2: 手动执行安装脚本（见上文）
```

**选项 3: 先本地测试脚本（最稳妥）**
```powershell
# 检查脚本语法
bash -n deploy\jdcloud\install_redis.sh
bash -n deploy\jdcloud\configure_redis.sh
bash -n deploy\jdcloud\configure_firewall.sh
```

---

## ✅ 准备就绪

所有文件已创建，可以开始部署！

**推荐执行顺序**：
1. 阅读本文档（你正在做）✓
2. 选择部署方式（自动化 or 手动）
3. 执行 Phase 1.1-1.3（京东云安装）
4. 保存 Redis 密码（重要！）
5. 执行 Phase 1.4（阿里云测试）
6. 我来实现 Phase 1.5（代码集成）

需要我继续执行哪一步？
