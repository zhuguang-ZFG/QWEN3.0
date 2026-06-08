# 京东云部署最终方案 - Hermes Agent Gateway

> **日期**: 2026-06-08  
> **服务器**: 117.72.118.95 (2核3.8G 入门型)  
> **方案**: Hermes Agent Gateway  
> **状态**: 就绪部署

---

## 配置确认

```
CPU:  2核 Intel Xeon E5-2683 v4 @ 2.10GHz
内存: 3.8 GB
硬盘: 59 GB SSD (使用 26%)
系统: Ubuntu 24.04.2 LTS
档位: 入门型
```

**结论**: ✅ **适合部署 Hermes Agent Gateway**

---

## 方案总览

### 部署内容

```
京东云 (117.72.118.95)
  ├─ Hermes API (8699)            # OpenAI 兼容代理
  │   └─ 调用 → 阿里云 LiMa (8080)
  │
  ├─ Nginx (80)                    # 反向代理
  │   ├─ /hermes/health            # 公开健康检查
  │   └─ /hermes/v1/*              # 仅限阿里云访问
  │
  └─ systemd 服务                  # 自动重启
      └─ 资源限制: 1GB 内存, 50% CPU
```

### 能力增强

| 之前 | 之后 |
|------|------|
| 单轮问答 | 多步骤任务执行 |
| 无工具调用 | 文件/Shell/浏览器工具 |
| 无任务追踪 | 完整执行日志 |

---

## 快速部署（3 个步骤）

### 步骤 1: 上传文件

```powershell
# 在本地 D:\QWEN3.0 目录执行
python scripts/deploy_hermes_jdcloud.py
```

**脚本会自动**:
1. 连接京东云服务器
2. 安装系统依赖（Python, Nginx）
3. 创建虚拟环境
4. 上传应用文件
5. 配置 systemd 服务
6. 启动并验证

### 步骤 2: 配置 API Key

```bash
# SSH 登录京东云
ssh root@117.72.118.95

# 编辑配置文件
nano /opt/hermes-gateway/.env

# 修改以下行:
LIMA_API_KEY=<你的 LiMa API Key>

# 重启服务
systemctl restart hermes-gateway
```

### 步骤 3: 在阿里云注册后端

在阿里云 VPS 上，修改 `backends_registry.py`:

```python
BACKENDS = {
    # ... 现有后端 ...
    
    'hermes-agent': {
        'url': 'http://117.72.118.95/hermes/v1/chat/completions',
        'key': os.environ.get('LIMA_API_KEY', ''),
        'model': 'hermes-agent',
        'fmt': 'openai',
        'timeout': 120,
        'caps': ['tool_calls', 'multi_step', 'autonomous'],
        'admission': 'experimental',
    },
}
```

部署到阿里云:
```bash
python scripts/deploy_unified.py --files backends_registry.py
systemctl restart lima-router
```

---

## 验证部署

### 1. 健康检查

```bash
# 京东云本地
curl http://127.0.0.1:8699/health

# 从阿里云访问
curl http://117.72.118.95/hermes/health
```

预期响应:
```json
{"status":"ok","model":"hermes-agent","port":8699}
```

### 2. 端到端测试

```bash
# 阿里云 VPS 执行
curl -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_KEY" \
  -d '{
    "model": "hermes-agent",
    "messages": [
      {"role": "user", "content": "自主完成：查找当前目录下所有 Python 文件"}
    ]
  }'
```

### 3. 监控日志

```bash
# 实时日志
journalctl -u hermes-gateway -f

# 最近 100 行
journalctl -u hermes-gateway -n 100

# 错误日志
journalctl -u hermes-gateway -p err
```

---

## 资源监控

### 内存使用

```bash
# 查看 Hermes 进程内存
ps aux | grep hermes_api

# 系统内存
free -h
```

**预期**:
- 空闲时: 100-200 MB
- 处理任务: 300-500 MB
- **警戒线**: > 800 MB

### CPU 使用

```bash
# 实时监控
top -p $(pgrep -f hermes_api)
```

**预期**:
- 空闲时: < 5%
- 处理任务: 20-50%
- **警戒线**: > 80% 持续超过 1 分钟

---

## 安全配置

### 网络隔离

Nginx 配置已限制：
- ✅ 仅允许阿里云 VPS (47.112.162.80) 访问 API
- ✅ 健康检查端点公开
- ❌ 其他 IP 访问返回 403

### 资源限制

systemd 服务已配置：
- 内存上限: 1GB（防止 OOM）
- CPU 配额: 50%（保留系统资源）
- 自动重启: 失败后 10 秒重启

### 日志安全

```bash
# 检查日志中是否有敏感信息
journalctl -u hermes-gateway | grep -i "api.*key\|password\|token"
```

应该没有输出，如果有，需要修改日志配置。

---

## 故障排查

### 问题 1: 服务启动失败

```bash
# 查看详细错误
systemctl status hermes-gateway -l

# 手动启动查看错误
cd /opt/hermes-gateway
source venv/bin/activate
python hermes_api.py
```

常见原因:
- API Key 未配置
- 端口被占用
- 依赖缺失

### 问题 2: 内存溢出 (OOM)

```bash
# 检查系统日志
dmesg | grep -i "killed process"

# 检查内存使用
free -h
```

解决方案:
- 降低并发限制
- 增加 swap 空间
- 考虑升级到 4GB 内存

### 问题 3: 无法连接阿里云

```bash
# 测试网络连通性
curl http://47.112.162.80:8080/health

# 检查防火墙
iptables -L -n
```

---

## 回滚方案

如果部署出现问题：

```bash
# 停止服务
systemctl stop hermes-gateway
systemctl disable hermes-gateway

# 删除文件
rm -rf /opt/hermes-gateway
rm /etc/systemd/system/hermes-gateway.service

# 在阿里云移除后端注册
# 编辑 backends_registry.py，删除 hermes-agent 条目
# 重新部署
```

---

## 性能优化（可选）

### 1. 启用 swap（增加虚拟内存）

```bash
# 创建 2GB swap
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# 永久生效
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### 2. 优化 systemd 服务

编辑 `/etc/systemd/system/hermes-gateway.service`:

```ini
# 增加内存限制到 1.5GB（如果空闲内存足够）
MemoryMax=1.5G

# 增加 CPU 配额到 80%
CPUQuota=80%

# OOM 优先级（不优先杀掉）
OOMScoreAdjust=-100
```

### 3. Nginx 缓存（降低后端压力）

编辑 Nginx 配置:

```nginx
# 缓存相同请求的响应
proxy_cache_path /var/cache/nginx/hermes levels=1:2 keys_zone=hermes_cache:10m max_size=100m;

location /hermes/v1/ {
    proxy_cache hermes_cache;
    proxy_cache_valid 200 5m;
    proxy_cache_key "$request_method$request_uri$request_body";
    # ... 其他配置 ...
}
```

---

## 成本与收益

### 投入

| 项目 | 时间/成本 |
|------|----------|
| 部署时间 | 30-60 分钟 |
| 学习成本 | 1-2 小时 |
| 维护成本 | 5 分钟/周 |
| 额外费用 | 0 元（已有服务器）|

### 产出

| 能力 | 价值 |
|------|------|
| 多步骤任务 | ⭐⭐⭐ 增加自主性 |
| 工具调用 | ⭐⭐⭐ 文件/Shell/浏览器 |
| 风险隔离 | ⭐⭐⭐⭐ Shell 在独立环境 |
| 学习价值 | ⭐⭐⭐⭐ Agent 工作流实践 |

**ROI**: 中等偏上（性价比好，但不如本地推理直接）

---

## 下一步演进

如果京东云服务器升级到 **4核8G** 或以上，可以考虑：

### 方案升级: 本地模型推理

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 下载模型
ollama pull qwen2.5-coder:7b

# 在 LiMa 注册本地后端
# backends_registry.py
'ollama-qwen-coder': {
    'url': 'http://117.72.118.95:11434/v1/chat/completions',
    'model': 'qwen2.5-coder:7b',
    'tier': 'code_floor_first',
}
```

**价值提升**: ⭐⭐⭐⭐⭐
- 延迟降低 60%
- 成本节省 80%
- 隐私增强 100%

---

## 总结

### ✅ 当前方案（入门型配置）

- **部署**: Hermes Agent Gateway
- **可行性**: 完全可行
- **价值**: 中等（增加 Agent 能力）
- **风险**: 低（资源充足，易回滚）

### 🎯 最佳方案（如果升级配置）

- **升级到**: 4核8G 标准型（约 +100元/月）
- **部署**: Ollama 本地推理
- **价值**: 极高（真正增强核心能力）
- **ROI**: ⭐⭐⭐⭐⭐

### 📝 建议

1. **现在**: 部署 Hermes Gateway，验证效果
2. **1个月后**: 评估使用频率和价值
3. **如果有价值**: 考虑升级服务器配置，部署 Ollama
4. **如果价值有限**: 保持现状或回滚，节省成本

---

## 附录：文件清单

### 本地文件（D:\QWEN3.0）

```
deploy/jdcloud/
  ├─ install_hermes.sh              # 环境安装脚本
  └─ nginx_hermes.conf              # Nginx 配置

scripts/
  ├─ check_jdcloud_config.py        # 配置查询脚本 ✓
  └─ deploy_hermes_jdcloud.py       # 一键部署脚本

docs/superpowers/plans/
  ├─ 2026-06-08-jdcloud-deployment-plan.md      # 初步方案
  ├─ 2026-06-08-jdcloud-resource-analysis.md    # 资源分析
  └─ 2026-06-08-jdcloud-deployment-final.md     # 最终方案 ✓
```

### 京东云文件（117.72.118.95）

```
/opt/hermes-gateway/
  ├─ venv/                          # Python 虚拟环境
  ├─ hermes_api.py                  # 应用主文件
  ├─ hermes_bridge.py               # 集成层
  ├─ hermes_gateway.py              # Gateway 客户端
  ├─ requirements.txt               # 依赖清单
  └─ .env                           # 配置文件（含密钥）

/etc/systemd/system/
  └─ hermes-gateway.service         # systemd 服务

/etc/nginx/sites-available/
  └─ hermes-gateway.conf            # Nginx 配置
```

---

**准备就绪，可以开始部署！**

执行命令:
```powershell
cd D:\QWEN3.0
python scripts/deploy_hermes_jdcloud.py
```
