# 文档深度精简计划 - 2026-06-10

**目标**: 将文档从 109 个减少到 ~60 个（-45%）
**原则**: 保留活跃文档，归档/删除重复和过期内容

## 第二轮清理策略

### 1. 删除 - 已完成的执行报告（6个）

**superpowers/plans/ 中的执行报告**:
- `2026-06-09-phase0-day2-report.md` (4.9K) - Day 2 执行报告
- `2026-06-09-lima-code-retirement.md` (6.8K) - LiMa Code 退役
- `2026-06-09-telegram-retirement.md` (4.9K) - Telegram 退役
- `2026-06-09-ci-hygiene-after-retirement.md` (4.0K) - CI 卫生
- `2026-06-09-pre-commit-hook-hygiene.md` (2.6K) - pre-commit 卫生
- `2026-06-09-capacity-aware-vps-jdcloud-utilization.md` (4.5K) - 容量感知

**理由**: 这些是已完成任务的执行报告，内容已体现在代码库中。

### 2. 合并 - 重复主题的战略文档（7 → 2）

**LiMa 机器人集成相关**（保留 1 个最新的）:
- ❌ `2026-06-09-lima-replace-xiaozhi-feasibility.md` (16K) - 可行性分析
- ❌ `2026-06-09-lima-xiaozhi-integration-v2.md` (19K) - 集成 v2
- ❌ `2026-06-09-lima-robot-integration-final.md` (19K) - 最终集成
- ❌ `2026-06-09-lima-robot-ultimate.md` (20K) - 终极方案
- ❌ `2026-06-09-lima-xiaozhi-replacement-final-analysis.md` (14K) - 最终分析
- ✅ **保留**: `2026-06-09-ai-drawing-writing-robot.md` (27K) - 最全面的设计
- ✅ **保留**: `2026-06-09-writing-robot-lightweight-backend.md` (14K) - 轻量级后端

**理由**: 7 个文档描述同一个主题的不同迭代，保留最终版本即可。

### 3. 合并 - 顶层重复文档（3 → 1）

**部署相关**:
- `DEPLOYMENT.md` (5.1K) - 旧版部署文档
- `DEPLOY_AND_RELEASE_CONVENTION.md` (5.4K) - 部署和发布约定
- **操作**: 合并到 `DEPLOY_AND_RELEASE_CONVENTION.md`，删除 `DEPLOYMENT.md`

**架构相关**:
- `TECHNICAL_ARCHITECTURE.md` (10.4K) - 技术架构（2026-06-08）
- `ARCHITECTURE.md` (7.4K) - 架构文档（2026-06-10，新）
- **操作**: 合并到 `ARCHITECTURE.md`，删除 `TECHNICAL_ARCHITECTURE.md`

### 4. 归档 - 已完成的里程碑文档（2个）

**Phase 0 相关**（已完成，保留归档）:
- `2026-06-09-phase0-strategic-confirmation.md` (16K) → 归档
- `2026-06-09-code-simplification-verification.md` (4.6K) → 归档

**归档到**: `docs/archive/phase0-2026-06/`

### 5. 保留 - 活跃战略文档（5个）

**当前活跃的战略计划**:
- ✅ `2026-06-09-lima-strategic-pivot-to-smart-devices.md` (15K) - 战略转型总纲
- ✅ `2026-06-09-lima-hardware-ai-capability-redesign.md` (65K) - 硬件 AI 能力重设计
- ✅ `2026-06-09-lima-hardware-ai-phase1-execution-plan.md` (15K) - Phase 1 执行计划
- ✅ `2026-06-09-ai-drawing-writing-robot.md` (27K) - AI 绘图写字机
- ✅ `2026-06-09-writing-robot-lightweight-backend.md` (14K) - 轻量级后端
- ✅ `2026-06-09-prometheus-metrics-hardening.md` (6.2K) - 监控加固
- ✅ `2026-06-09-code-simplification-plan.md` (5.6K) - 代码精简计划（参考）

### 6. 更新 - 过时的参考文档

**需要更新标注的文档**:
- `FREE_MODEL_ROUTING_STATUS.md` → 添加"⚠️ 编码助手已退役，仅保留设备场景"
- `MODEL_CATALOG.md` → 更新模型列表，标注设备场景专用
- `README.md` → 更新日期到 2026-06-10，移除 `IMPROVEMENT_PLAN_2026-05-27.md` 引用

**删除引用**:
- `LIMACODE_MANAGEMENT.md` - 不存在的文档

## 执行步骤

### Step 1: 删除执行报告（6个）

```bash
cd docs/superpowers/plans
rm 2026-06-09-phase0-day2-report.md \
   2026-06-09-lima-code-retirement.md \
   2026-06-09-telegram-retirement.md \
   2026-06-09-ci-hygiene-after-retirement.md \
   2026-06-09-pre-commit-hook-hygiene.md \
   2026-06-09-capacity-aware-vps-jdcloud-utilization.md
```

### Step 2: 删除重复的机器人集成文档（5个）

```bash
cd docs/superpowers/plans
rm 2026-06-09-lima-replace-xiaozhi-feasibility.md \
   2026-06-09-lima-xiaozhi-integration-v2.md \
   2026-06-09-lima-robot-integration-final.md \
   2026-06-09-lima-robot-ultimate.md \
   2026-06-09-lima-xiaozhi-replacement-final-analysis.md
```

### Step 3: 归档 Phase 0 文档（2个）

```bash
mkdir -p docs/archive/phase0-2026-06
mv docs/superpowers/plans/2026-06-09-phase0-strategic-confirmation.md \
   docs/superpowers/plans/2026-06-09-code-simplification-verification.md \
   docs/archive/phase0-2026-06/
```

### Step 4: 删除顶层重复文档（2个）

```bash
# 先手动合并内容
rm docs/DEPLOYMENT.md
rm docs/TECHNICAL_ARCHITECTURE.md
```

### Step 5: 更新 README.md

更新文档索引，移除不存在的引用。

## 预期结果

| 类型 | 当前 | 清理后 | 减少 |
|------|------|--------|------|
| 总文档数 | 109 | ~60 | -45% |
| superpowers/plans/ | 20 | 7 | -65% |
| 顶层文档 | 19 | 17 | -11% |

## 清理后的文档结构

```
docs/
├── *.md (17个核心文档)
│   ├── LIMA_MEMORY.md (长期记忆)
│   ├── ARCHITECTURE.md (架构)
│   ├── ROUTING_ENGINE_DESIGN.md (路由)
│   ├── DEPLOY_AND_RELEASE_CONVENTION.md (部署)
│   ├── MODEL_CATALOG.md (模型)
│   ├── README.md (索引)
│   └── ...
├── archive/
│   ├── phase0-2026-06/ (Phase 0 归档)
│   ├── jdcloud-2026-06/ (京东云归档)
│   └── superpowers-2026-05/ (历史计划)
├── reference/ (参考资料)
└── superpowers/plans/ (7个活跃计划)
    ├── 2026-06-09-lima-strategic-pivot-to-smart-devices.md
    ├── 2026-06-09-lima-hardware-ai-capability-redesign.md
    ├── 2026-06-09-lima-hardware-ai-phase1-execution-plan.md
    ├── 2026-06-09-ai-drawing-writing-robot.md
    ├── 2026-06-09-writing-robot-lightweight-backend.md
    ├── 2026-06-09-prometheus-metrics-hardening.md
    └── 2026-06-09-code-simplification-plan.md (参考)
```

## 清理原则（强化）

✅ **删除**: 已完成的执行报告（内容已在代码/Git 历史）
✅ **删除**: 同主题的早期迭代（保留最终版本）
✅ **归档**: 已完成的里程碑（Phase 0）
✅ **合并**: 重复主题的顶层文档
✅ **保留**: 活跃战略计划和核心参考文档

## 文档命名规范（新）

### 战略计划文档命名

```
{日期}-{项目}-{阶段/类型}.md

示例:
- 2026-06-09-lima-strategic-pivot-to-smart-devices.md (战略)
- 2026-06-09-lima-hardware-ai-phase1-execution-plan.md (执行计划)
- 2026-06-09-ai-drawing-writing-robot.md (设计)
```

### 执行报告命名（临时）

```
{日期}-{主题}-report.md

执行后立即删除或合并到 progress.md
```

### 归档目录命名

```
docs/archive/{项目/阶段}-{年}-{月}/

示例:
- phase0-2026-06/
- jdcloud-2026-06/
- superpowers-2026-05/
```

## 执行后验证

- [ ] 总文档数减少 45%
- [ ] superpowers/plans/ 只有活跃计划
- [ ] 顶层 docs/ 无重复文档
- [ ] README.md 引用全部有效
- [ ] 每个归档目录有 README

## 风险评估

**低风险操作**:
- 删除执行报告（已完成任务）
- 删除早期迭代（保留最终版本）

**中风险操作**:
- 归档 Phase 0 文档（可能未来需要参考）
- 合并顶层文档（需要仔细合并内容）

**缓解措施**:
- 所有删除都有 Git 历史可恢复
- 归档文件保留完整内容
- 合并前备份原文件内容
