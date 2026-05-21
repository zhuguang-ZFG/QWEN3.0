# 编程模型塔：强模型带动弱模型 — 闭环实现方案

> 创建: 2026-05-22
> 目标: 让用户编程体验接近 Opus 4.7，实际 90% 由免费模型执行
> 原则: 强模型的智慧常驻（规范注入+模板匹配），仅在质量不达标时实时调用

---

## 执行步骤（每步闭环）

### Step 1: 编程规范注入 (skills/code_guide.md)
- 强模型预生成的编程规范，注入每个 coding 请求的 system prompt
- 覆盖: 代码风格、安全、边界处理、测试、命名
- 闭环标准: 注入后弱模型输出质量可观测提升

### Step 2: 意图模板库 (intent_templates.py)
- 50+ 常见编程意图的增强模板
- 匹配到模板 → 零成本增强 prompt
- 未匹配 → 调强模型实时增强
- 闭环标准: 模板命中率 >60%

### Step 3: 质量门 (quality_gate.py)
- 纯规则验证，不调模型:
  - 代码语法检查 (AST)
  - 长度合理性
  - 拒绝回答检测
  - 重复/空洞检测
  - 代码/文字比例
- 闭环标准: 能拦截 80% 的低质量回复

### Step 4: 修复路径 (repair)
- Quality Gate 不通过时调强模型修复
- 输入: 原始意图 + 弱模型尝试 + 失败原因
- 强模型只修补，不重写
- 闭环标准: 修复后通过 Quality Gate

### Step 5: code_orchestrator.py 主模块
- 串联 Step 1-4 的完整 pipeline
- 分层: simple(直出) / standard(生成+验证) / complex(规划+执行+审查)
- 闭环标准: 87+ 测试通过，端到端可用

### Step 6: 接入 routing_engine.py
- classify_scenario()="coding" 时走 orchestrator
- 闭环标准: 生产部署，API 测试通过

---

## 后端角色分配

| 角色 | 后端 | 调用时机 |
|------|------|---------|
| Fast | groq_gptoss, cerebras_gptoss, longcat_lite | Simple 层直出 |
| Coder | cf_qwen_coder, mistral_codestral, groq_llama70b | Standard 层执行 |
| Strong | cf_deepseek_r1, github_gpt4o, sambanova_ds_v3 | 意图增强 + 修复 |
