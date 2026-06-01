> ⚠️ 2026-06-01 起已过时。WeChat 已停用。当前状态见 STATUS.md

# LiMa 改善方案：从路由层到编码助手

> 2026-05-27 | 基于项目全量审计

## 核心问题

**LiMa 当前是 90% 路由基础设施 + 10% 编码能力。**

作者意图（`PERSONAL_CODING_ASSISTANT_PLAN.md`）：
> "Turn LiMa into a private coding assistant backend for the owner."

实际状态：
- 100+ LLM 后端 ✅（但只是转发，没有利用它们做编码辅助）
- 多层路由 ✅（但路由到哪里？只是把请求原样转发给后端）
- Telegram/WeChat/Webhook ✅（但只是聊天通道，不是编码工具）
- Agent 运行时 ✅（但 real_executor 今天才从空壳改为可用）
- 代码上下文 ✅（但之前只有 Python AST + 内存索引）

**本质矛盾**：路由系统很精密，但被路由的"内容"很薄——用户发"重构这个函数"，LiMa 只是转发给后端，返回结果，没有理解、没有执行、没有记忆。

## 作者真正需要的

| 需求 | 当前状态 | 差距 |
|------|----------|------|
| IDE 发请求 → LiMa 选最佳后端 → 返回有用回答 | ✅ 路由可用 | 回答质量取决于后端，LiMa 没有增强 |
| 代码理解：知道项目结构、依赖关系、历史变更 | ❌ 几乎没有 | code_context 只是扫描符号，不理解语义 |
| 代码执行：能跑测试、git 操作、文件修改 | ✅ M1 刚完成 | 需要接入实际工作流 |
| 项目记忆：跨会话记住架构决策、代码模式 | ⚠️ 有框架但未串联 | session_memory 有数据但未注入路由 |
| 开发工作流：investigate/review/ship | ✅ M4 刚完成 | 需要接入 Telegram 和 IDE |
| 质量保证：自动检查代码质量 | ⚠️ 有 quality_gate 但只评分 | 需要闭环：发现问题 → 修复 → 验证 |

## 改善方案（3 个阶段）

### Phase A: 打通核心路径（1-2 天）

**目标**：让 IDE 发的请求真正受益于 LiMa 的基础设施。

**A1: 路由 + 代码上下文注入**
- 当 IDE 发送 coding 请求时，自动扫描请求中提到的文件
- 用 M2 的 tree-sitter 提取符号，构建相关代码上下文
- 将上下文注入到转发给后端的 system prompt 中
- 后端收到的不再是裸请求，而是"带项目理解的请求"

**A2: 路由 + 学习闭环**
- 每次请求的延迟/成功/失败自动记录到 L1 性能层
- 下次相同场景的请求自动选择历史最优后端
- 用户通过 Telegram `/learn` 手动注入偏好

**A3: Telegram 接入开发者技能**
- `/investigate <file>` → 调用 M4 的 investigate 模块
- `/review <file>` → 调用 M4 的 review 模块  
- `/ship` → 调用 M4 的 ship 模块
- `/learn <obs>` → 调用 M4 的 learn 模块

### Phase B: 厚化编码能力（3-5 天）

**目标**：从"转发后端回答"变为"增强后端回答"。

**B1: 代码变更感知**
- 用 file_watcher 监控项目文件变更
- 变更时自动更新 SQLite 图索引和 ChromaDB 向量索引
- IDE 发请求时自动注入相关变更的上下文

**B2: 响应后处理**
- 后端返回代码时，自动检查语法（ast.parse）
- 检查安全问题（硬编码密钥、SQL 注入）
- 自动格式化（如果配置了 ruff/black）
- 质量不达标时自动重试其他后端

**B3: 会话记忆增强**
- 每次 coding 会话结束后，自动提取关键决策存入 L3
- 下次相同项目/文件的请求自动注入历史决策
- 用户通过 `/learn` 手动补充偏好

### Phase C: 精简与整合（2-3 天）

**目标**：减少服务数量，提高单个服务的深度。

**C1: 停用低价值服务**
- `openobserve`（187MB 内存）→ 已有 Prometheus + 事件系统
- `netdata`（98MB 内存）→ 已有 health_tracker + metrics
- `mission-server`（3 容器，日志为空）→ 确认是否废弃
- `duckai`（unhealthy）→ 修复或移除

**C2: 合并重复能力**
- `smart_router.py` + `router_v3.py` + `router_classifier.py` → 统一为一个路由模块
- `channel_gateway/` 的多个 public_apis 文件 → 合并为一个 facade
- 44 个 deploy 脚本 → 合并为 3-5 个参数化脚本

**C3: 文档清理**
- `STATUS.md`、`progress.md`、`findings.md` → 合并为一个项目状态文件
- `docs/` 下的过期计划文档 → 归档或删除
- `scripts/archive/` → 删除已退役的脚本

## 优先级排序

```
Phase A (立即)  ─── 打通核心路径，让路由真正服务于编码
Phase B (短期)  ─── 厚化能力，从转发变为增强
Phase C (中期)  ─── 精简服务，提高维护效率
```

## 成功标准

Phase A 完成后：
- IDE 发送 coding 请求时，后端收到带代码上下文的增强请求
- 相同场景的请求自动选择历史最优后端
- Telegram 可执行 /investigate /review /ship /learn

Phase B 完成后：
- 后端返回的代码自动经过语法+安全检查
- 项目文件变更自动更新索引
- 跨会话记住代码决策

Phase C 完成后：
- VPS 内存从 1.3GB 降到 <800MB
- 服务数量从 10+ 降到 5-6 个核心服务
- 部署脚本从 44 个降到 <10 个
