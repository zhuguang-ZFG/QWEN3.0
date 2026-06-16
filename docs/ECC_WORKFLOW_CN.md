# LiMa × ECC 开发流程指南

> 本文件把 ECC（Everything Claude Code）的跨 harness 工程流程与 LiMa 现有实践对齐，作为 `AGENTS.md` 中 ECC 章节的展开说明。

## 1. 流程总览

```
Plan → TDD (RED/GREEN/REFACTOR) → Code Review → Commit → Deploy → Document
```

## 2. Plan First

### 触发条件

以下任一情况必须先进入 Plan mode：
- 改动涉及 >2-3 个文件
- 新架构决策或接口变更
- 用户意图不明确或存在多种实现路径
- 安全敏感改动
- 可能影响生产部署的改动

### 计划内容

计划文件必须包含：
1. **目标**：一句话说明要做什么
2. **验收标准**：如何验证完成
3. **关键文件**：会修改哪些文件
4. **风险与回滚**：最坏情况如何处理
5. **验证命令**：pytest / ruff / pyright / smoke 命令

## 3. TDD（测试驱动开发）

### RED → GREEN → REFACTOR

1. **RED**：先写测试，运行并确认失败
   ```powershell
   python -m pytest tests/test_xxx.py -v
   ```
2. **GREEN**：写最小实现让测试通过
3. **REFACTOR**：优化代码结构，保持测试通过
4. **验证覆盖率**：
   ```powershell
   python -m pytest tests/test_xxx.py --cov=模块名 --cov-report=term-missing
   ```

### 测试层级

| 类型 | 范围 | 示例 |
|---|---|---|
| 单元测试 | 单个函数/类 | `tests/test_device_gateway_model_routing.py` |
| 集成测试 | API/数据库/Redis | `tests/test_device_gateway_routes.py` |
| E2E | 端到端闭环 | `tests/test_fake_u1_cloud_loop.py` |

### 覆盖率目标

- 新模块：≥80%
- 现有模块：逐步提升，每次改动不降低
- 安全敏感路径（auth、输入验证、路径安全）：优先覆盖

## 4. 代码审查清单

### 安全（Security First）

- [ ] 无硬编码 secret
- [ ] 所有用户输入已验证
- [ ] SQL 注入防护（参数化查询）
- [ ] XSS/CSRF 已考虑（如适用）
- [ ] 错误消息不泄露敏感数据
- [ ] 认证/授权已验证
- [ ] 速率限制已配置（如适用）

### 质量

- [ ] 函数 ≤50 行
- [ ] 文件 ≤300 行（新模块/拆分）
- [ ] 错误处理无静默吞掉
- [ ] 输入在系统边界验证
- [ ] 优先不可变：返回新对象而非原地修改
- [ ] 命名清晰，注释必要

### 测试

- [ ] 新增/修改功能有对应测试
- [ ] 测试失败时先修复实现而非削测试
- [ ] 通过 focused tests 和 full tests
- [ ] 覆盖率不下降

## 5. 提交规范

### Conventional Commits

```
<type>: <description>

[optional body]
```

常用 type：
- `feat`：新功能
- `fix`：修复
- `refactor`：重构
- `docs`：文档
- `test`：测试
- `chore`：杂项
- `perf`：性能
- `ci`：CI

### Git 纪律

- 不使用 `git add .`
- 仅 stage 本次改动相关文件
- 不提交 `.env`、密钥、临时调试脚本
- 不 force-push
- 推送前运行 `git diff --check`

## 6. 安全响应协议

若发现安全漏洞：
1. **STOP** 立即停止当前工作。
2. 修复 CRITICAL 问题。
3. 轮换任何可能暴露的 secret。
4. 检查代码库中是否存在类似问题。
5. 更新 `findings.md` 记录事件与修复。

## 7. 与 LiMa 原生规则的优先级

| 优先级 | 规则来源 |
|---|---|
| 最高 | 用户直接指令 |
| 高 | `AGENTS.md` Hard Rules（4 条） |
| 中 | 本 ECC 流程指南 |
| 低 | 通用编程建议 |

当 ECC 建议与 LiMa Hard Rules 冲突时，以 Hard Rules 为准，并向用户说明。

## 8. 工具链

| 工具 | 用途 | 命令 |
|---|---|---|
| ruff | lint + format | `ruff check .` / `ruff format .` |
| pyright | 类型检查 | `pyright <file>` |
| pytest | 测试 | `python -m pytest ...` |
| pytest-cov | 覆盖率 | `python -m pytest --cov=...` |
| scripts/check_code_size.py | 代码尺寸检查 | `python scripts/check_code_size.py` |
| scripts/run_pre_commit_check.py | 预提交门禁 | `python scripts/run_pre_commit_check.py` |
