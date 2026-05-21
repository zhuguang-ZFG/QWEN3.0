# 编程模型塔 V2：容错+自愈+学习 — 完整闭环方案

> 更新: 2026-05-22
> 目标: 用 10 个 70 分模型协作，产出 95 分结果（接近 Opus 4.7）
> 核心: 强模型智慧常驻 + 多维验证 + 惩罚机制 + 修复熔断 + 延迟预算

---

## V1 已完成（基础 pipeline）

- [x] Step 1: 编程规范注入 (skills/code/guide.md)
- [x] Step 2: 意图模板库 (intent_templates.py, 20+ 模板)
- [x] Step 3: 基础质量门 (quality_gate.py)
- [x] Step 4: 修复路径 (_repair)
- [x] Step 5: code_orchestrator.py 主模块
- [x] Step 6: 接入 routing_engine.py + 生产部署

---

## V2 升级项（容错+自愈+学习）

### Step 7: 后端信誉分系统 (backend_reputation.py)
- 每个后端维护 0-100 信誉分
- 质量门通过 → +2 分，失败 → -10 分
- 连续 3 次失败 → 冷却 30 分钟
- 选后端时按信誉分排序（不是固定顺序）
- 闭环标准: 低质量后端自动被降级

### Step 8: 多维质量门升级 (quality_gate.py 扩展)
- Dim 1: 基础质量（已有）
- Dim 2: 指令遵从（类型注解/测试/完整性）
- Dim 3: 安全检测（SQL注入/XSS/硬编码密钥）
- Dim 4: 现代性检查（废弃API/旧语法）
- Dim 5: 完整性（import完整/无TODO占位）
- 输出: 0-100 评分（≥70 通过）
- 闭环标准: 能拦截安全漏洞和不完整代码

### Step 9: 修复熔断 + 策略切换
- 最多 2 次修复尝试
- 第 1 次: 定向修复（告诉 Strong 哪里错）
- 第 2 次: 换模型从零重写（不基于 bad_answer）
- 2 次都失败 → 返回所有尝试中最优的
- 每次修复换不同 Strong 后端
- 闭环标准: 不会无限循环

### Step 10: 延迟预算机制
- simple: 5s, standard: 12s, complex: 30s
- 超时前必须返回（宁可有瑕疵不可空）
- 各阶段按比例分配预算
- 闭环标准: 用户永远不会等超过 30s

### Step 11: 强模型也验证
- Strong 输出同样过质量门
- Strong 失败 → 换另一个 Strong
- 所有 Strong 都失败 → 降级到 Coder 最优结果
- 闭环标准: 不盲信任何模型

### Step 12: 反馈闭环接入
- quality_gate 结果 → 更新 backend_reputation
- 记录 (backend, task_type, score) 三元组
- 按 task_type 维度选最优后端
- 闭环标准: 系统越用越准

---

## 执行顺序

Step 7 → 8 → 9 → 10 → 11 → 12 → 全量测试 → 部署
