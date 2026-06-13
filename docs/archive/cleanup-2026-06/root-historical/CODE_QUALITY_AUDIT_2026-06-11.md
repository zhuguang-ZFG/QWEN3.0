# LiMa 代码质量审查报告（Superpowers 全面审查）

**日期:** 2026-06-11
**分支:** feat/code-simplification
**审查依据:** Superpowers 开发原则（AGENTS.md + .qoder/skills/superpowers/SKILL.md）

---

## 执行摘要

**总体评估:** 🟡 中等 — 核心原则部分违反，需分阶段修复

| 维度 | 评级 | 说明 |
|------|------|------|
| 代码规模 | 🔴 严重超标 | 193 万行 vs 目标 11 万行（包含 esp32/qoder 子项目） |
| Lint 清洁度 | 🟢 良好 | ruff check 通过 |
| 测试通过率 | 🟢 良好 | 1886 passed, 24 skipped |
| 文件大小 | 🟡 部分违规 | 23 个核心文件超 300 行（最大 1184 行） |
| 降级保护 | 🔴 违规 | 发现 2+ 裸 `except` + `pass` |
| 部署安全 | 🟢 良好 | `.env` 保护、备份机制已到位 |

---

## 一、Principle 0: No Silent Degradation — 🔴 发现违规

### 🔴 CRITICAL: 裸 except + pass（2处）

#### C-QA-1: budget_manager.py
```python
except ImportError:
    pass  # ❌ 违反 Principle 0 — 无日志
```
**影响:** 预算管理模块可选依赖失败时静默跳过，排查困难。
**修复:** 改为 `logger.debug("budget manager import failed: optional dep missing")`

#### C-QA-2: channel_gateway/integrations.py
```python
except ImportError:
    return (...)  # ⚠️ 有返回但无日志
```
**影响:** 集成模块降级时无观测性。
**修复:** 添加 `logger.warning("channel integration degraded: ImportError")`

### 统计

```bash
grep -r "except.*pass$" --include="*.py" | wc -l
# 发现约 40+ 处 except + pass 组合（需逐一审查）
```

**优先级:** P0 — 违反全局硬规则

---

## 二、Principle 2: Small, Focused Files — 🟡 部分违规

### 超过 300 行的核心文件（Top 15）

| 文件 | 行数 | 状态 | 优先级 |
|------|-----:|------|--------|
| routes/xiaozhi_v1_compat.py | 1184 | 🔴 待拆分 | P1 |
| tests/test_provider_automation.py | 850 | ⚠️ 测试可豁免 | P2 |
| tests/test_ops_metrics.py | 752 | ⚠️ 测试可豁免 | P2 |
| routes/ops_metrics.py | 635 | 🔴 待拆分 | P1 |
| eval_loop.py | 612 | 🟡 暂缓 | P3 |
| distill_scheduler.py | 578 | 🟡 暂缓 | P3 |
| auto_trainer.py | 577 | 🟡 暂缓 | P3 |
| channel_gateway/service.py | 567 | 🟡 待评估 | P2 |
| tests/test_routing_engine.py | 547 | ⚠️ 测试可豁免 | P2 |
| tests/test_device_gateway_routes.py | 486 | ⚠️ 测试可豁免 | P2 |
| routes/admin_ui.py | 482 | 🟡 待拆分 | P2 |
| routes/admin_api_extra.py | 479 | 🟡 待拆分 | P2 |
| auto_distill_main.py | 443 | 🟡 暂缓 | P3 |
| channel_gateway/store.py | 429 | 🟡 待拆分 | P2 |
| auto_retrain.py | 408 | 🟡 暂缓 | P3 |

### 🔴 P1 立即拆分（2个）

1. **routes/xiaozhi_v1_compat.py (1184 行)** — 违规 4x
   - 建议：按端点组拆分（device/user/admin/message 子模块）
   - 参考：`routes/chat_endpoints.py` 拆分模式

2. **routes/ops_metrics.py (635 行)** — 违规 2x
   - 建议：分离 Prometheus 导出器、内存统计、HTTP 端点

### 🟡 P2 评估后拆分（5个）

- `channel_gateway/service.py` (567)
- `routes/admin_ui.py` (482)
- `routes/admin_api_extra.py` (479)
- `channel_gateway/store.py` (429)
- `lima_mcp/tool_defs.py` (394)

---

## 三、Principle 1: Documentation First — 🟢 基本合格

### ✅ 已完成

- `CLAUDE.md` 项目规范 ✅
- `AGENTS.md` Superpowers 原则 ✅
- `docs/superpowers/plans/` 13 个设计文档 ✅
- `STATUS.md` / `progress.md` / `findings.md` 三件套 ✅

### ⚠️ 待改进

- 部分战略文档有 UTF-8 乱码（`2026-06-09-ai-drawing-writing-robot.md`）
- `STATUS.md` 分支名过时（`feat/kilo-provider-probe` → 实际 `feat/code-simplification`）
- 缺少 `docs/README.md` 导航入口

---

## 四、Principle 3/4: Deploy Safety — 🟢 良好

### ✅ 已到位

- `scripts/deploy_unified.py` 部署前备份 ✅
- `.env` 不可覆盖保护 ✅
- VPS 容量检查（disk/mem preflight）✅
- 部署后 health 验证 ✅
- `.gitignore` 正确排除 `.env` ✅

### 🟡 改进建议

- JDCloud 节点 SSH key 未配（CAP-JD-7）
- VPS 内存紧张（488 MB 可用，接近阈值）

---

## 五、Git Hygiene — 🟢 良好

```bash
git status --short
# 已正确 ignore: .venv/, .lima-data/, .codegraph/, credentials
```

**无违规凭据泄漏。**

---

## 六、Architecture Debt（参考 2026-06-10 诊断）

### P0 — 生产回归

| ID | 问题 | 状态 |
|----|------|------|
| R-01 | 工具调用路径断裂（`anthropic_native_*` = None） | 🔴 待修复 |
| R-02 | OpenCode 优化未在当前分支 | 🟡 待合并 |
| R-03 | 精简与生产用法冲突（删 tool_forward 但 Chat 仍用） | 🔴 待修复 |

### P1 — 战略债务

| ID | 问题 | 状态 |
|----|------|------|
| A-01 | 双轨未收敛（Chat 栈仍全量运行） | 🟡 战略调整中 |
| A-02 | 绘图引擎未独立 | 🟡 Phase1 Week3-5 |
| A-05 | 临时 stub 技术债（3 个文件） | 🟡 Phase2 移除 |

---

## 七、修复路线图（优先级排序）

### 🔴 P0 立即修复（1-2 天）

1. **C-QA-1/2: 裸 except + pass 审查**
   - 扫描全部 40+ 处，添加 `logger.debug/warning`
   - 验收：`grep -r "except.*pass$" --include="*.py"` 返回 0

2. **R-01: 工具调用路径修复**
   - 恢复 `tool_forward` 简化版，或走 OpenAI 原生 tools
   - 验收：OpenCode Build 不再 500

### 🟡 P1 近期优化（1-2 周）

3. **文件拆分（2个）**
   - `routes/xiaozhi_v1_compat.py` → 4 子模块
   - `routes/ops_metrics.py` → 3 子模块
   - 验收：无文件超 300 行（测试除外）

4. **R-02/03: 分支合并**
   - Cherry-pick OpenCode 修复到 `feat/code-simplification`
   - 统一 `STATUS.md` 分支名
   - 验收：单分支可部署

### 🟢 P2 持续改进（2-4 周）

5. **文档完善**
   - 修复 UTF-8 乱码
   - 创建 `docs/README.md` 导航
   - 更新 `STATUS.md` 当前分支

6. **剩余 5 个超标文件拆分**
   - 按需评估 vs 业务价值

---

## 八、测试与验证状态

### ✅ 当前通过

```
pytest tests/ -q --tb=line (simplified)
1886 passed, 24 skipped, 1 deselected
```

### ⚠️ 待修复

- `test_token_health.py::test_check_all_tokens_no_import` 被跳过
- `conftest.py` ignore 列表包含 3 个 hypothesis 测试

---

## 九、总结与建议

### 核心问题

1. **代码规模仍超标** — 193 万行（含子项目）vs 目标
2. **2 处裸 except 违反 Principle 0** — 静默降级风险
3. **2 个核心文件严重超标** — xiaozhi_v1_compat (1184), ops_metrics (635)
4. **生产工具调用断裂** — anthropic_native_* 回调为 None

### 优先修复顺序

```
P0: 裸 except 审查 + 工具调用修复（1-2 天）
 ↓
P1: xiaozhi/ops_metrics 拆分 + 分支合并（1-2 周）
 ↓
P2: 文档完善 + 剩余文件拆分（2-4 周）
```

### 下一步行动

**立即执行（需用户确认）:**

1. 扫描并修复全部裸 except + pass
2. 拆分 `routes/xiaozhi_v1_compat.py` (1184 → 4x ~300)
3. 修复 R-01 工具调用断裂

**是否开始执行 P0 修复？**
