# 战略规划文档归档（2026-06）

本目录归档了 2026-06 期间产生的 5 份重叠战略规划文档。它们覆盖相同的「缺陷/审计/改进/路线图」领域，共 3,255 行，造成多权威源、信息分散。

## 归档原因

2026-07-02 的四维度过度设计审查（见 [`../../superpowers/specs/2026-07-02-system-slimdown-design.md`](../../superpowers/specs/2026-07-02-system-slimdown-design.md)）发现：

- 5 份文档内容高度重叠，互相对基准（测试数 3730 vs 实际 4285、LOC 数也过期）
- `LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 验收项未勾选，已是遗弃状态
- 多份「权威」规划并存导致执行时不知遵循哪份

审查的诊断/改进部分已合并进上述瘦身设计文档，作为单一活动规划。本目录仅作历史归档。

## 归档文件清单

| 文件 | 原行数 | 性质 |
|------|--------|------|
| `PROJECT_DEFECTS_AND_IMPROVEMENT_PLAN_CN.md` | 1,257 | 缺陷+改进计划（基准 179,647 LOC / 2402 tests，已过期） |
| `LIMA_IMPROVEMENT_PLAN_20260625_V2.md` | 910 | 详细版 v2，含 95 个产品功能未勾选（docs站/定价页/FAQ/OpenAPI 等） |
| `PROJECT_OPTIMIZATION_ROADMAP_CN.md` | 223 | 优化路线图（M9-M12 已关闭） |
| `DEEP_QUALITY_AUDIT_CN.md` | 207 | 全栈深度质量审计 |
| `OPTIMIZATION_ANALYSIS_2026-06-23.md` | 181 | 优化分析 |

## 注意：产品功能规划仍在

`LIMA_IMPROVEMENT_PLAN_20260625_V2.md` 的 95 个未勾选项是**产品功能规划**（官网文档站、定价页、FAQ 扩展、OpenAPI 参考页等），与「过度设计瘦身」是不同轨道。若要推进这些产品功能，请从本归档取出该文档，作为需求来源另起 spec。

**不要**把这些产品功能需求混入瘦身文档 —— 瘦身只做减法。
