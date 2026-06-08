# 京东云 VPS 部署增强方案

> **日期**: 2026-06-08  
> **目标**: 利用新增京东云服务器增强 LiMa 系统能力  
> **原则**: Superpowers — 文档先行、本地验证、可回滚、渐进式

---

## 京东云服务器信息

| 项目 | 值 |
|------|-----|
| **IP** | 117.72.118.95 |
| **提供商** | 京东云 |
| **访问凭证** | 见 VPS.txt (不提交到仓库) |
| **代号** | `jdcloud-1` |
| **用途** | Hermes Agent Gateway + 独立计算节点 |

---

## 架构现状分析

### 当前架构
```
阿里云 VPS (47.112.162.80)
  ├─ LiMa Router (8080)           # 主路由，180+ 后端
  ├─ Nginx (80/443)               # 反向代理 + SSL
  ├─ SearXNG (8081)               # 本地搜索引擎
  └─ SQLite 数据库                # 会话记忆、健康状态
```

### 已有的 Agent 能力

**Hermes 组件** (本地，未部署到 VPS)：
- `hermes_api.py` — OpenAI 兼容微服务 (端口 8699)
- `hermes_bridge.py` — LiMa ↔ Hermes 集成层
- `hermes_gateway.py` — Agent Gateway 客户端 (端口 18790)

**OpenClaw** — 已退役组件 (见 `docs/LIMA_MEMORY.md:174`)：
- 曾用于 GitHub 定时任务
- 清理脚本: `scripts/cleanup_openclaw_vps.py`
- **不建议复活**，功能已被更现代的方案替代

---

## 京东云部署策略

### 方案 A: Hermes Agent Gateway 独立节点 (推荐)

**目标**: 将 Hermes Agent 部署到京东云，提供自主任务执行能力

```
京东云 (117.72.118.95)
  ├─ Hermes Gateway (18790)       # 自主任务执行
  │   ├─ 文件操作工具
  │   ├─ Shell 执行工具
  │   ├─ 浏览器工具
  │   └─ 搜索工具
  │
  └─ Hermes API (8699)            # OpenAI 兼容代理
      └─ 调用阿里云 LiMa Router
```

**优势**:
1. **隔离风险**: Shell/文件操作在独立环境，不影响主路由
2. **增强能力**: 提供多步骤自主任务执行
3. **可回滚**: 独立部署，失败不影响现有服务
4. **符合 Superpowers**: 新模块独立验证

**通信方式**:
```
用户请求 → 阿里云 LiMa Router (8080)
              ↓
         路由决策: 需要 Agent 能力?
              ↓
         HTTP → 京东云 Hermes Gateway (18790)
              ↓
         自主执行 → 返回结果
```

---

### 方案 B: 备用路由节点 (备选)

**目标**: 京东云作为 LiMa 的灾备/负载均衡节点

```
京东云 (117.72.118.95)
  └─ LiMa Router Clone (8080)     # 完整副本
      ├─ 相同后端注册表
      ├─ 独立 SQLite 会话库
      └─ 共享 Nginx 配置
```

**优势**:
- 高可用: 主节点故障时自动切换
- 负载均衡: DNS 轮询分流

**劣势**:
- 重复部署: 维护成本 2 倍
- 数据不同步: 会话记忆无法共享
- **不推荐**: 个人项目暂不需要此级别高可用

---

### 方案 C: 专用计算节点 (未来扩展)

**目标**: 资源密集型任务独立执行

潜在用途:
- **本地模型推理**: Ollama / vLLM
- **向量数据库**: Chroma / Qdrant
- **长时任务队列**: Celery + Redis
- **搜索引擎**: SearXNG 独立实例

**当前评估**: **暂不部署**
- LiMa 是轻量路由系统，现有架构足够
- 云端后端已有 180+ 提供商，无需本地推理
- 等有明确瓶颈再引入

---

## 推荐实施方案: Hermes Agent Gateway

### Phase 1: 环境准备

**1.1 连接测试**
```powershell
# 测试 SSH 连接
ssh root@117.72.118.95

# 检查系统信息
uname -a
python3 --version
systemctl --version
```

**1.2 安装依赖**
```bash
# 京东云 VPS 执行
apt update && apt install -y python3.10 python3-pip git nginx

# 创建目录
mkdir -p /opt/hermes-gateway
cd /opt/hermes-gateway

# 克隆必要文件 (从本地上传)
# hermes_api.py, hermes_bridge.py, hermes_gateway.py
```

---

### Phase 2: Hermes Gateway 部署

**2.1 创建服务配置**

创建 `/etc/systemd/system/hermes-gateway.service`:
```ini
[Unit]
Description=Hermes Agent Gateway
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/hermes-gateway
Environment="LIMA_BASE_URL=http://47.112.162.80:8080/v1"
Environment="LIMA_API_KEY=YOUR_KEY_HERE"
Environment="HERMES_GATEWAY_PORT=18790"
ExecStart=/usr/bin/python3 hermes_api.py
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

**2.2 启动服务**
```bash
systemctl daemon-reload
systemctl enable hermes-gateway
systemctl start hermes-gateway
systemctl status hermes-gateway
```

**2.3 健康检查**
```bash
curl -s http://127.0.0.1:18790/health | jq
curl -s http://127.0.0.1:8699/health | jq
```

---

### Phase 3: Nginx 反向代理

**3.1 配置 Nginx**

创建 `/etc/nginx/sites-available/hermes.conf`:
```nginx
server {
    listen 80;
    server_name hermes.your-domain.com;

    location /health {
        proxy_pass http://127.0.0.1:18790;
        proxy_set_header Host $host;
    }

    location /v1/ {
        proxy_pass http://127.0.0.1:8699;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # 仅允许阿里云 VPS 访问
        allow 47.112.162.80;
        deny all;
    }
}
```

**3.2 启用配置**
```bash
ln -s /etc/nginx/sites-available/hermes.conf /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

---

### Phase 4: LiMa 主路由集成

**4.1 在阿里云 VPS 上注册 Hermes 后端**

修改 `backends_registry.py`:
```python
BACKENDS = {
    # ... 现有后端 ...
    
    'hermes-agent': {
        'url': 'http://117.72.118.95:8699/v1/chat/completions',
        'key': os.environ.get('LIMA_API_KEY', ''),  # 复用主 key
        'model': 'hermes-agent',
        'fmt': 'openai',
        'timeout': 120,
        'caps': ['tool_calls', 'multi_step', 'autonomous'],
        'admission': 'experimental',
    },
}
```

**4.2 路由规则增强**

修改 `routing_classifier.py`:
```python
def should_use_agent_mode(messages: list[dict]) -> bool:
    """判断是否需要 Agent 自主执行"""
    last_msg = messages[-1].get('content', '').lower()
    
    agent_keywords = [
        '自主完成', '多步骤', '调研并实现', 
        '搜索并总结', 'research and implement',
        'autonomous', 'multi-step'
    ]
    
    return any(kw in last_msg for kw in agent_keywords)
```

**4.3 部署到 VPS**
```powershell
# 本地执行
python scripts\deploy_unified.py --files backends_registry.py routing_classifier.py
```

---

### Phase 5: 验证与监控

**5.1 端到端测试**
```bash
# 阿里云 VPS 上测试
curl -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_KEY" \
  -d '{
    "model": "hermes-agent",
    "messages": [
      {"role": "user", "content": "自主完成：搜索 Python 3.12 新特性并总结"}
    ]
  }'
```

**5.2 监控指标**
```bash
# 京东云 VPS 监控
journalctl -u hermes-gateway -f
tail -f /var/log/nginx/access.log

# 检查资源使用
top -p $(pgrep -f hermes_api)
```

**5.3 回滚方案**
```bash
# 如果有问题，立即回滚
systemctl stop hermes-gateway
systemctl disable hermes-gateway

# 阿里云移除后端注册
# 编辑 backends_registry.py，注释掉 hermes-agent 条目
python scripts/deploy_unified.py --files backends_registry.py
```

---

## 不建议部署 OpenClaw

**原因分析**:
1. **已退役**: 根据 `docs/LIMA_MEMORY.md:174`，OpenClaw 已有清理脚本
2. **功能重叠**: GitHub 自动化已有更好的方案:
   - `clawsweeper` (MIT) — 定时关闭过期 issue/PR
   - GitHub Actions — 原生 workflow
3. **维护成本**: 独立服务需要额外监控和更新
4. **Superpowers 违背**: 复活退役组件不符合"参考业界实践"原则

**推荐替代方案**:
- 使用 GitHub Actions + `clawsweeper` 进行仓库清理
- 集成到现有 Agent Autonomy Evolution 计划 (Phase 7)

---

## 成本与收益分析

### 方案 A: Hermes Gateway (推荐)

| 维度 | 评估 |
|------|------|
| **新增能力** | ⭐⭐⭐⭐⭐ 多步骤自主任务执行 |
| **架构一致性** | ⭐⭐⭐⭐ 符合 Agent Autonomy Evolution 路线 |
| **实施成本** | ⭐⭐⭐ 1-2 天，文件少，依赖清晰 |
| **维护成本** | ⭐⭐⭐⭐ 独立服务，故障隔离 |
| **风险** | ⭐⭐⭐⭐ Shell 隔离在独立 VPS |

**ROI 评估**: **高**
- 对齐 `docs/superpowers/plans/2026-05-23-agent-autonomy-evolution.md`
- 为 Phase 4 (Sequential Local Agent Loop) 提供基础设施
- 增强 LiMa 从"路由器"到"自主 Agent"的演进

---

## 文件清单与依赖

**需要上传到京东云的文件**:
```
hermes_api.py           # FastAPI 服务入口
hermes_bridge.py        # LiMa 集成层
hermes_gateway.py       # Gateway 客户端
requirements_hermes.txt # 依赖清单
```

**requirements_hermes.txt** (新建):
```
fastapi==0.115.0
uvicorn==0.32.0
httpx==0.28.1
openai==1.57.4
paramiko==3.5.0
```

**部署脚本** (新建 `scripts/deploy_hermes.py`):
```python
#!/usr/bin/env python3
"""Deploy Hermes Gateway to JD Cloud VPS"""
import paramiko
from pathlib import Path

SERVER = "117.72.118.95"
USER = "root"
KEY = Path.home() / ".ssh" / "id_rsa"  # 或密码认证
REMOTE = "/opt/hermes-gateway"

FILES = [
    "hermes_api.py",
    "hermes_bridge.py", 
    "hermes_gateway.py",
    "requirements_hermes.txt",
]

def deploy():
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(SERVER, username=USER, key_filename=str(KEY))
    
    sftp = ssh.open_sftp()
    for f in FILES:
        sftp.put(f, f"{REMOTE}/{f}")
    sftp.close()
    
    # 重启服务
    stdin, stdout, stderr = ssh.exec_command(
        f"cd {REMOTE} && pip3 install -r requirements_hermes.txt && "
        "systemctl restart hermes-gateway"
    )
    print(stdout.read().decode())
    ssh.close()
    
if __name__ == "__main__":
    deploy()
```

---

## 下一步行动

### 立即执行 (Phase 1-2)
- [ ] SSH 连接京东云，安装基础环境
- [ ] 创建 `/opt/hermes-gateway` 目录
- [ ] 上传 4 个核心文件
- [ ] 创建 systemd 服务
- [ ] 启动并验证健康检查

### 集成测试 (Phase 3-4)
- [ ] 配置 Nginx 反向代理
- [ ] 在阿里云注册 `hermes-agent` 后端
- [ ] 端到端测试 Agent 调用
- [ ] 监控日志和性能

### 生产化 (Phase 5)
- [ ] 配置自动重启策略
- [ ] 添加 Prometheus 指标导出
- [ ] 文档更新: `AGENTS.md`, `STATUS.md`
- [ ] 内存增强: 记录京东云部署信息

---

## 安全考虑

1. **网络隔离**
   - 仅允许阿里云 VPS IP 访问 Hermes API
   - Gateway 端口 18790 不对外暴露

2. **密钥管理**
   - `LIMA_API_KEY` 通过环境变量传递
   - systemd 服务使用 `EnvironmentFile=/opt/secrets/.env`

3. **审计日志**
   - 所有 Agent 任务记录到 `agent_workbench` 数据库
   - Shell 命令执行日志独立存储

4. **沙箱隔离**
   - 考虑使用 Docker 容器运行 Hermes Gateway
   - 限制文件系统访问范围

---

## 参考文档

- `AGENTS.md` — LiMa 架构权威参考
- `docs/superpowers/plans/2026-05-23-agent-autonomy-evolution.md` — Agent 演进路线图
- `docs/LIMA_MEMORY.md` — 历史组件和清理记录
- `docs/reference/EXTERNAL_CAPABILITY_RADAR_2026-05-24.md` — 外部能力雷达

---

## 总结

**推荐方案**: 在京东云部署 Hermes Agent Gateway (方案 A)

**核心价值**:
1. 增强 LiMa 自主任务执行能力
2. 为 Agent Autonomy Evolution 提供基础设施
3. 隔离风险，符合 Superpowers 原则
4. 可回滚，渐进式验证

**不推荐**: 
- ❌ 复活 OpenClaw (已退役，有更好替代)
- ❌ 完整克隆 LiMa Router (维护成本高，个人项目无需)

**实施时间**: 预计 1-2 天完成 Phase 1-4

**成功标志**: 
- 用户可以通过 LiMa Router 调用 Hermes Agent 完成多步骤任务
- 京东云服务独立运行，阿里云主路由保持稳定
- 新增能力有审计日志和监控指标
