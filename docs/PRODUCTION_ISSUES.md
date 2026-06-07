# LiMa 生产环境问题收敛清单

> 生成时间: 2026-06-07  
> VPS: 47.112.162.80 (chat.donglicao.com)  
> 腾讯服务器: 100.125.105.117

---

## 1. OpenCode 真实验证问题 🔴 关键阻塞

### 问题描述
OpenCode 客户端无法通过 Cloudflare 调用 LiMa 服务，所有测试被 403 拦截。

### 测试结果
| 测试项 | 状态 | 问题 |
|--------|------|------|
| VPS Health Check | ✅ PASS | - |
| Simple Query | ❌ FAIL | Cloudflare WAF 403 |
| IDE Detection | ❌ FAIL | Cloudflare WAF 403 |
| Tool Call | ❌ FAIL | Cloudflare WAF 403 |
| Streaming | ❌ FAIL | Cloudflare WAF 403 |
| Skill Injection | ❌ FAIL | Cloudflare WAF 403 |

### 根本原因分析
1. **Cloudflare WAF 过于严格**: OpenCode User-Agent 被拦截
2. **Nginx 配置不完整**: `/etc/nginx/conf.d/chat.donglicao.com.conf` 缺少 `/v1/` 路由规则
3. **认证机制问题**: Bearer token 未正确传递到后端

### 解决方案
1. 添加 Cloudflare WAF 白名单规则（允许 OpenCode User-Agent）
2. 完善 Nginx `/v1/` location 配置
3. 验证 API Key 传递链路（OpenCode → Cloudflare → Nginx → LiMa）

### 验证方法
```bash
# 绕过 Cloudflare 直接测试 8080 端口
curl -H 'User-Agent: OpenCode/1.0.0' \
  -H 'Authorization: Bearer xHzP3Uk9EA...' \
  http://47.112.162.80:8080/v1/chat/completions
```

---

## 2. VPS 资源压力 🟡 优化建议

### 当前状态
| 指标 | 数值 | 状态 |
|------|------|------|
| 内存使用 | 1.4G / 1.8G (77%) | ⚠️ 高负载 |
| 可用内存 | 414M | ⚠️ 边界 |
| 磁盘使用 | 24G / 40G (63%) | ✅ 正常 |
| LiMa 进程内存 | 297.6M | ✅ 正常 |
| Hermes API 内存 | 18.1M | ✅ 正常 |

### 问题分析
1. **内存接近临界点**: 414M 可用内存可能不足以处理并发请求
2. **无内存保护机制**: 缺少 OOM 告警和自动清理策略

### 优化建议
1. 添加内存监控告警（< 300M 可用时告警）
2. 实现 session 定期清理机制
3. 考虑迁移到 2G+ 内存规格

---

## 3. Telegram API 失败 🟡 非关键

### 问题
```
WARNING:telegram_bot:Telegram API sendMessage failed:
```

### 影响范围
- 通知功能失效（GitHub webhook 告警）
- 日志统计：失败 7 次记录

### 解决方案
1. 检查 Telegram Bot Token 有效性
2. 验证 Cloudflare 对 `api.telegram.org` 的访问策略
3. 降级为邮件告警（如 Telegram 持续失败）

---

## 4. GitHub Webhook 503 错误 🟡 非关键

### 问题
```
POST /github/webhook HTTP/1.1" 503 Service Unavailable
```

### 影响范围
- 5 次 webhook 调用失败
- 自动化流程中断

### 解决方案
1. 增加 webhook 处理超时时间
2. 添加 webhook 队列和重试机制
3. 实现 webhook 幂等性处理

---

## 5. 未提交文件收敛 🟡 待处理

### 修改未提交 (M)
- `context_pipeline/evolution.py`
- `context_pipeline/signal_extraction.py`
- `routes/admin_api.py`
- `routes/ops_metrics.py`

### 新增未追踪 (??)
- `streaming_failover_metrics.py`
- `tests/test_quality_dashboard.py`
- `tests/test_quality_feedback.py`
- `tests/test_quality_integration.py`
- `tests/test_streaming_failover_metrics.py`
- `tests/test_streaming_fault_tolerance_integration.py`

### 处理方案
1. 代码审查（质量检查）
2. 提交有意义的功能文件
3. 清理临时测试文件

---

## 6. 代码质量审查计划

### 审查范围
1. **流式容错模块**
   - `streaming_state.py` (127 行)
   - `streaming_retry.py` (169 行)
   - `streaming_failover_metrics.py` (新增)

2. **质量评估模块**
   - `quality_history.py` (154 行)
   - `semantic_eval.py` (233 行)

3. **OpenViking 集成**
   - `context_pipeline/openviking_processor.py` (64 行)
   - `openviking_client.py` (116 行)

4. **FastMCP 服务器**
   - `lima_mcp/fastmcp_server.py` (381 行)

### 审查要点
- ✅ 类型注解完整性
- ✅ 错误处理覆盖率
- ✅ 日志记录规范性
- ✅ 测试覆盖度
- ⚠️ 文档完整性（部分缺失）

---

## 7. 生产环境监控缺失 🔴 关键

### 缺失监控项
1. **内存使用趋势** - 无历史数据
2. **请求成功率** - 无统计
3. **后端响应时间** - 无分布图
4. **错误率** - 无告警
5. **并发数** - 无监控

### 建议方案
1. 部署 Prometheus + Grafana
2. 配置关键指标告警
3. 实现健康检查端点 `/health/metrics`
4. 添加 `/v1/ops/metrics` 增强

---

## 8. LiMa 真实生产力验证

### 当前生产力状态
| 维度 | 状态 | 证据 |
|------|------|------|
| 服务可用性 | ✅ 100% | lima-router + hermes-api 均运行 |
| OpenCode 集成 | ❌ 0% | WAF 403 拦截，无法使用 |
| 错误恢复 | 🟡 部分 | 有 retry 机制，但无监控 |
| 可扩展性 | 🟡 部分 | 支持 289 后端，但资源受限 |

### 真实生产力定义
**LiMa 拥有真实生产力** 需要：
1. ✅ OpenCode 可以直接调用并稳定响应
2. ✅ 工具调用可靠（文件读写、shell 执行）
3. ✅ 流式输出无中断
4. ✅ 多会话并发稳定
5. ✅ 错误自动恢复（用户无感知）

### 当前差距
- **OpenCode 无法使用** → 无法通过 IDE 直接调用
- **无监控告警** → 运维盲区
- **资源临界** → 可能 OOM

---

## 优先级收敛计划

### P0 - 必须解决（1-2 天）
1. **OpenCode WAF 白名单** → 恢复 IDE 集成
2. **Nginx `/v1/` 配置修复** → API 路由修复

### P1 - 高优先级（3-5 天）
3. **内存监控告警** → 防止 OOM
4. **提交未追踪文件** → 代码收敛

### P2 - 中优先级（1-2 周）
5. **Telegram Bot 修复** → 告警恢复
6. **GitHub Webhook 重试** → CI/CD 稳定
7. **Prometheus 监控** → 可观测性

### P3 - 低优先级（按需）
8. **迁移到 2G 内存** → 资源扩容
9. **代码质量审查** → 长期质量

---

## 结论

**LiMa 当前状态**: 服务运行正常，但 **OpenCode 无法使用**（WAF 拦截）。

**真实生产力状态**: ❌ **未达到**  
- OpenCode 调用成功率: 0/6  
- 监控覆盖: 0%  
- 告警机制: 部分失效

**下一步行动**: 
1. 解决 Cloudflare WAF 白名单问题（P0）
2. 修复 Nginx 配置（P0）
3. 重新进行 OpenCode E2E 测试验证