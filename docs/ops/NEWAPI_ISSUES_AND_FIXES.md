# NewAPI 部署问题与修复方案

**日期**: 2026-06-11
**状态**: 🔴 需立即修复
**相关文档**: `docs/ops/JDCLOUD_NEWAPI_DEPLOY.md`

---

## 一、严重问题汇总

### 🔴 P0 - 安全红线突破（立即修复）

| 问题 | 当前状态 | 风险 | 修复方案 |
|------|---------|------|---------|
| **文档明文凭据** | root 密码、API Key 已写入文档 | 凭据泄露 → 完全接管 | 1. 立即删除文档中所有凭据<br>2. 重置所有已泄露密码/token<br>3. 使用 `{{VAR}}` 占位符 |
| **环境变量明文** | docker-compose.yml 中密码明文 | `docker inspect` 可见 | 使用 Docker secrets 或外部 vault |
| **MySQL 通配符** | `newapi@'%'` 允许任意 IP | 内网渗透风险 | 改为 `newapi@'127.0.0.1'` |

### 🟠 P1 - 架构缺陷（本周修复）

| 问题 | 影响 | 修复方案 |
|------|------|---------|
| **双层 nginx 性能** | 额外延迟 ~50-200ms | 评估迁移到阿里云单节点 |
| **单点故障链** | 3 节点串联，任一故障全服务不可用 | 引入第二节点 + 负载均衡 |
| **自签证书无验证** | `proxy_ssl_verify off` 易受 MITM | 启用 mTLS 或 WireGuard 隧道 |
| **network_mode host** | 容器绕过 Docker 网络隔离 | 改为桥接模式 + host.docker.internal |

### 🟡 P2 - 运维风险（两周内完成）

| 问题 | 影响 | 修复方案 |
|------|------|---------|
| **仅本地备份** | 磁盘故障 → 数据永久丢失 | 推送到阿里云 OSS，保留 30 天 |
| **手动回滚** | 故障恢复时间 > 15 分钟 | 自动化回滚脚本 + 健康检查触发 |
| **监控缺失** | 无日志聚合、无指标监控 | 接入 Loki + Prometheus + Grafana |

---

## 二、待完成任务清单

### 任务 1：立即修复凭据泄露（今天）

```bash
# SSH 到京东云
ssh root@117.72.118.95

# 1. 重置 root 密码
python3 -c "import bcrypt; print(bcrypt.hashpw(b'<新密码-至少16位>', bcrypt.gensalt(prefix=b'2a')).decode())"
mysql -e "UPDATE newapi.users SET password='<新hash>' WHERE username='root';"

# 2. 重置 API access_token
python3 -c "import secrets; print(secrets.token_hex(16))"
mysql -e "UPDATE newapi.users SET access_token='<新token>' WHERE username='root';"

# 3. 限制 MySQL 用户为 localhost
mysql -e "DROP USER 'newapi'@'%';"
mysql -e "CREATE USER 'newapi'@'127.0.0.1' IDENTIFIED BY '<强密码>';"
mysql -e "GRANT ALL PRIVILEGES ON newapi.* TO 'newapi'@'127.0.0.1'; FLUSH PRIVILEGES;"

# 4. 更新 docker-compose.yml 中的 SQL_DSN
sed -i "s/@tcp(127.0.0.1:3306)/@tcp(127.0.0.1:3306)/" /opt/newapi/docker-compose.yml
docker compose -f /opt/newapi/docker-compose.yml restart
```

### 任务 2：Web UI 初始化（今天）

浏览器打开 `https://api.donglicao.com`：

- [x] 用新密码登录
- [ ] 系统设置 → 关闭用户注册（Enable Registration = false）
- [ ] 系统设置 → 修改站点名称（"LiMa AI Gateway"）
- [ ] 添加渠道（见下方"导入优秀模型"）

### 任务 3：导入优秀模型（今天）

**配置文件**: `newapi_models_export.json`（58 个优秀模型）

**分类统计**:
- 旗舰模型 (8): GPT-5, Claude Sonnet 4.6, Gemini 2.5 Pro 等
- 性价比 (9): GPT-4o-mini, Claude Haiku, Gemini Flash 等
- 专用模型 (10): GPT-5 Codex, Qwen Coder, DeepSeek R1 等
- 中国厂商 (11): 阿里云、智谱、Kimi、百度等

**导入方式 A：Web UI 手动**（推荐）

1. 打开 `https://api.donglicao.com/channel`
2. 点击"新增渠道"
3. 根据 `newapi_models_export.json` 填写：
   - 类型：OpenAI
   - 名称：如 "OpenAI GPT-5"
   - Base URL：如 `https://opengateway.ai/v1`
   - 密钥：从 Infisical 获取真实 key
   - 模型：如 `gpt-5,gpt-5.5,gpt-5.4`
   - 优先级：10-400（越小越优先）

**导入方式 B：MySQL 批量**（高级）

```bash
# 上传配置文件
scp newapi_models_export.json root@117.72.118.95:/tmp/

# 生成 SQL
ssh root@117.72.118.95
python3 << 'EOF'
import json
with open('/tmp/newapi_models_export.json') as f:
    data = json.load(f)

for category in ['flagship', 'cost_effective', 'specialized', 'china']:
    for ch in data[category]:
        name_escaped = ch['name'].replace("'", "\\'")
        models_str = ','.join(ch['models'])
        print(f"INSERT INTO newapi.channels (type, name, key, base_url, models, priority) VALUES (")
        print(f"  {ch['type']}, '{name_escaped}', '{{{{KEY}}}}', '{ch['base_url']}',")
        print(f"  '{models_str}', {ch['priority']});")
EOF

# 替换 {{KEY}} 为真实密钥后执行
mysql newapi < /tmp/channels.sql
```

### 任务 4：监控接入（本周）

```bash
# 1. 创建 healthchecks.io check（2个）
# 2. 部署监控脚本
cat > /opt/newapi/healthcheck.sh << 'EOF'
#!/bin/bash
set -euo pipefail
CHECK_UUID=${1:-}
if [ -z "$CHECK_UUID" ]; then echo "Usage: $0 <check_uuid>"; exit 1; fi

if curl -sf https://api.donglicao.com/api/status > /dev/null; then
  curl -fsS -m 10 --retry 3 "https://hc-ping.com/$CHECK_UUID"
else
  curl -fsS -m 10 --retry 3 "https://hc-ping.com/$CHECK_UUID/fail"
fi
EOF
chmod +x /opt/newapi/healthcheck.sh

# 3. 加入 cron
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/newapi/healthcheck.sh <uuid1>") | crontab -
(crontab -l; echo "*/30 * * * * /opt/newapi/healthcheck.sh <uuid2>") | crontab -
```

### 任务 5：异地备份（两周内）

```bash
# 1. 安装阿里云 OSS CLI
wget http://gosspublic.alicdn.com/ossutil/1.7.18/ossutil-v1.7.18-linux-amd64.zip
unzip ossutil-v1.7.18-linux-amd64.zip
sudo mv ossutil64 /usr/local/bin/ossutil
ossutil config  # 配置 AccessKey

# 2. 修改备份脚本
cat > /opt/newapi/backup.sh << 'EOF'
#!/bin/bash
set -euo pipefail
TS=$(date +%Y%m%d_%H%M%S)
DEST=/var/backups/newapi/$TS
mkdir -p "$DEST"

# 导出数据库
mysqldump -u newapi -p"$NEWAPI_MYSQL_PASS" -h 127.0.0.1 newapi > "$DEST/newapi.sql"

# 备份配置
cp /opt/newapi/docker-compose.yml "$DEST/"

# 推送到 OSS
ossutil cp -r "$DEST" oss://lima-backup/newapi/$TS/

# 清理本地 > 7 天（OSS 保留 30 天）
find /var/backups/newapi -mindepth 1 -maxdepth 1 -mtime +7 -exec rm -rf {} \;
EOF

# 3. 测试
NEWAPI_MYSQL_PASS=<密码> /opt/newapi/backup.sh
```

---

## 三、架构改进建议

### 短期（本月）

1. **消除明文凭据**
   - 接入 Infisical 或 HashiCorp Vault
   - 使用 Docker secrets
   - 环境变量占位符：`${INFISICAL_newapi_root_password}`

2. **加固 MySQL**
   - `newapi@'%'` → `newapi@'127.0.0.1'`
   - 定期审计 MySQL 用户权限

3. **异地备份**
   - 推送到阿里云 OSS
   - 保留 30 天版本

### 中期（本季度）

1. **简化架构**（评估）
   - 方案 A：迁移到阿里云单节点（消除 ISP 拦截问题）
   - 方案 B：保留京东云，但用 WireGuard 替代自签证书

2. **高可用**
   - 第二阿里云节点 + 负载均衡器
   - 或使用托管数据库（RDS）

3. **监控升级**
   - Loki 日志聚合
   - Prometheus 指标监控
   - Grafana 仪表盘

### 长期（下半年）

1. **全面安全审计**
   - 渗透测试
   - 依赖漏洞扫描

2. **自动化运维**
   - CI/CD 自动化部署
   - 故障自动恢复

---

## 四、NewAPI 模型配置摘要

**已生成配置**: `newapi_models_export.json`

### 旗舰模型 (8)

| 渠道名称 | 模型 | Base URL | 优先级 |
|---------|------|----------|--------|
| OpenAI GPT-5 系列 | gpt-5, gpt-5.5, gpt-5.4 | https://opengateway.ai/v1 | 10 |
| Anthropic Claude Sonnet 4.6 | claude-sonnet-4.6 | https://api.anthropic.com/v1 | 20 |
| Google Gemini 2.5 Pro | gemini-2.5-pro | https://generativelanguage.googleapis.com/v1beta | 30 |
| DeepSeek V4 Pro | deepseek-v4-pro | https://api.deepseek.com | 40 |
| Mistral Large | mistral-large | https://api.mistral.ai/v1 | 50 |

### 性价比模型 (9)

| 渠道名称 | 模型 | Base URL | 优先级 |
|---------|------|----------|--------|
| OpenAI GPT-4o-mini | gpt-4o-mini | https://api.openai.com/v1 | 100 |
| Anthropic Claude Haiku | claude-haiku-4.5 | https://api.anthropic.com/v1 | 110 |
| Google Gemini 2.5 Flash | gemini-2.5-flash | https://generativelanguage.googleapis.com/v1beta | 120 |
| Meta Llama 3.3 70B | llama-3.3-70b | https://api.groq.com/openai/v1 | 130 |

### 专用模型 (10)

| 类别 | 渠道名称 | 模型 | Base URL |
|-----|---------|------|----------|
| 编码 | OpenAI GPT-5 Codex | gpt-5.3-codex | https://opengateway.ai/v1 |
| 编码 | 阿里云 Qwen Coder | qwen-3-coder-plus | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| 编码 | Mistral Codestral | codestral-latest | https://api.mistral.ai/v1 |
| 推理 | DeepSeek R1 | deepseek-r1 | https://api.deepseek.com |

### 中国厂商 (11)

| 厂商 | 模型 | Base URL | 优先级 |
|-----|------|----------|--------|
| 阿里云 | qwen3-8b, qwen-3-coder-plus | https://dashscope.aliyuncs.com/compatible-mode/v1 | 300 |
| 智谱 AI | glm-4-flash, glm-4.7-flash | https://open.bigmodel.cn/api/paas/v4 | 310 |
| Kimi (月之暗面) | moonshot-v1-8k | https://api.moonshot.cn/v1 | 320 |
| 百度 | ernie-3.5-8k, ernie-speed-8k | https://qianfan.baidubce.com/v2 | 330 |
| 火山引擎 | doubao-1-5-pro-256k | https://ark.cn-beijing.volces.com/api/v3 | 340 |

**完整配置**: 见 `newapi_models_export.json`

---

## 五、验收标准

- [ ] P0 问题全部修复（凭据已重置，文档已清理）
- [ ] Web UI 初始化完成（注册关闭、渠道已添加）
- [ ] 至少 10 个优秀模型可用（测试通过）
- [ ] 监控接入（2 个 healthchecks）
- [ ] 异地备份每日执行
- [ ] Smoke 测试全部通过

---

**负责人**: Claude Opus 4.8
**审核**: zhuguang-ZFG
**下次审查**: 2026-06-18
