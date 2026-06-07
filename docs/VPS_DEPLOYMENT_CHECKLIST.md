# VPS 部署验证清单

**部署目标**: 将 OpenCode 深度适配优化部署到生产环境  
**部署日期**: 2026-06-07  
**部署人员**: 待定

---

## 📋 部署前检查

### 1. 代码准备 ✅
- [x] 所有代码已提交到 Git
- [x] 分支: `codex/free-web-ai-probe`
- [x] Commits: `a766870`, `d04ee9e`, `a55589b`
- [x] 推送到 GitHub: 完成

### 2. 测试验证 ✅
- [x] 单元测试: 68/68 通过
- [x] 端到端测试: 4/4 通过
- [x] 性能基准: 10.29% 延迟改善
- [x] 本地服务验证: 正常

### 3. 文档准备 ✅
- [x] 集成文档: `docs/OPENCODE_DEEP_INTEGRATION.md`
- [x] 部署指南: 本文档
- [x] 验证报告: `docs/OPENCODE_E2E_VERIFICATION.md`
- [x] 基准报告: `docs/OPENCODE_BENCHMARK_REPORT.md`

---

## 🚀 部署步骤

### Step 1: 备份当前生产环境
```bash
# 在 VPS 上执行
cd /path/to/QWEN3.0
git branch backup-$(date +%Y%m%d-%H%M%S)
git stash  # 如果有未提交的更改
```

### Step 2: 拉取最新代码
```bash
# 拉取新分支
git fetch origin
git checkout codex/free-web-ai-probe
git pull origin codex/free-web-ai-probe

# 或者合并到 main
# git checkout main
# git merge codex/free-web-ai-probe
```

### Step 3: 更新环境变量
编辑 `.env` 文件，添加新模块配置：

```bash
# OpenCode 核心优化（已有）
LIMA_OPENCODE_TOOL_MODE=direct
LIMA_OPENCODE_DIRECT_STREAM=1
LIMA_OPENCODE_SKIP_SPECULATIVE_TOOLS=1

# 新增优化模块（推荐启用）
LIMA_OPENCODE_SESSION_CACHE=1        # 会话缓存
LIMA_OPENCODE_SKILL_SIMPLIFY=1       # Skill 优化
LIMA_OPENCODE_TOOL_SIMPLIFY=1        # Tool Schema 简化
LIMA_OPENCODE_REASONING_BUDGET=1     # Reasoning Budget

# 预测性上下文（实验性，可选）
# LIMA_OPENCODE_PREDICTIVE_CONTEXT=1

# 确保端口配置正确
PORT=8080  # 或您的生产端口
```

### Step 4: 重启服务
```bash
# 停止当前服务
# 方法 1: systemctl (推荐)
sudo systemctl stop lima

# 方法 2: 手动 kill
pkill -f "python.*server.py"

# 启动新服务
# 方法 1: systemctl
sudo systemctl start lima
sudo systemctl status lima

# 方法 2: 手动启动
nohup python server.py > /var/log/lima/server.log 2>&1 &
```

### Step 5: 健康检查
```bash
# 等待服务启动
sleep 5

# 检查进程
ps aux | grep "python.*server.py"

# 检查健康接口
curl http://localhost:8080/health

# 检查日志
tail -50 /var/log/lima/server.log | grep -i "opencode\|error\|warning"
```

---

## ✅ 部署后验证

### 1. 服务状态检查
```bash
# 健康检查
curl http://localhost:8080/health | jq

# 预期输出:
# {
#   "status": "ok",
#   "version": "2.0",
#   ...
# }
```

### 2. OpenCode 配置验证
检查日志中的 OpenCode 配置：

```bash
grep "opencode-config" /var/log/lima/server.log | tail -1
```

预期输出应包含：
- `tool_mode=direct`
- `direct_stream=True`
- `skip_spec_tools=True`
- `session_options=True`

### 3. 新模块加载验证
检查新模块是否正确加载：

```bash
grep -i "session.*cache\|skill.*optim\|tool.*simpli\|reasoning.*budget" \
  /var/log/lima/server.log | tail -20
```

如果启用环境变量，应该看到相关日志。

### 4. 端到端测试
在 VPS 上运行测试脚本：

```bash
python scripts/test_opencode_simple.py
```

预期：4/4 测试通过

### 5. 性能监控
观察前 10 分钟的性能指标：

```bash
# 响应时间
tail -f /var/log/lima/server.log | grep -i "route-ms"

# 后端选择
tail -f /var/log/lima/server.log | grep -i "backend="

# 错误率
tail -f /var/log/lima/server.log | grep -i "error\|exception" | wc -l
```

---

## 🔍 故障排查

### 问题 1: 服务启动失败
**检查**:
```bash
# 查看完整错误
tail -100 /var/log/lima/server.log

# 常见原因:
# - 端口被占用: netstat -tulpn | grep 8080
# - 缺少依赖: pip list | grep -i opencode
# - 环境变量错误: cat .env | grep LIMA_OPENCODE
```

### 问题 2: OpenCode 优化未生效
**检查**:
```bash
# 确认环境变量已加载
grep LIMA_OPENCODE .env

# 检查模块导入
python -c "import opencode_session_cache; print('OK')"
python -c "import opencode_skill_optimizer; print('OK')"
```

### 问题 3: 性能下降
**回滚步骤**:
```bash
# 方法 1: 禁用新模块（推荐）
# 编辑 .env，设置所有新模块为 0
LIMA_OPENCODE_SESSION_CACHE=0
LIMA_OPENCODE_SKILL_SIMPLIFY=0
LIMA_OPENCODE_TOOL_SIMPLIFY=0
LIMA_OPENCODE_REASONING_BUDGET=0

# 重启服务
sudo systemctl restart lima

# 方法 2: 回滚代码（如果问题严重）
git checkout backup-YYYYMMDD-HHMMSS
sudo systemctl restart lima
```

---

## 📊 监控指标

### 关键指标
1. **响应延迟**: 预期改善 10-15%
2. **错误率**: 应保持 < 1%
3. **后端稳定性**: 同一会话使用同一后端
4. **内存使用**: 监控是否有内存泄漏

### 监控命令
```bash
# 实时响应时间（每分钟平均）
tail -f /var/log/lima/server.log | \
  grep -oP 'route-ms:\s*\K\d+' | \
  awk '{sum+=$1; count++} NR%60==0 {print sum/count; sum=0; count=0}'

# 错误统计（每小时）
watch -n 3600 'grep -c "ERROR\|Exception" /var/log/lima/server.log | tail -1'

# 内存使用
watch -n 60 'ps aux | grep "python.*server.py" | grep -v grep | awk "{print \$6}"'
```

---

## 🎯 成功标准

部署被认为成功，当满足以下条件：

1. ✅ 服务健康检查通过
2. ✅ OpenCode 配置正确加载
3. ✅ 端到端测试 4/4 通过
4. ✅ 无新增错误或异常
5. ✅ 响应延迟保持或改善
6. ✅ 运行 2 小时无故障

---

## 📞 联系信息

**技术支持**:
- 项目文档: `docs/OPENCODE_*.md`
- Git 分支: `codex/free-web-ai-probe`
- Commits: `a766870`, `d04ee9e`, `a55589b`

**回滚决策**:
- 如果错误率 > 5%: 立即回滚
- 如果延迟增加 > 20%: 禁用新模块
- 如果出现崩溃: 回滚代码

---

## ✅ 部署检查表

部署完成后，逐项检查：

- [ ] 代码已拉取到最新版本
- [ ] 环境变量已更新
- [ ] 服务已重启
- [ ] 健康检查通过
- [ ] OpenCode 配置已加载
- [ ] 端到端测试通过
- [ ] 日志无明显错误
- [ ] 性能指标正常
- [ ] 监控已启用
- [ ] 文档已归档

---

**创建时间**: 2026-06-07  
**版本**: 1.0  
**状态**: 待部署
