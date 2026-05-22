# 编程模型塔 V3：上下文工程+容错+自愈+学习

> 更新: 2026-05-22
> 状态: 全部完成，生产运行中
> 目标: 用 10 个 70 分模型协作，产出 95 分结果（接近 Opus 4.7）
> 核心: 上下文工程(Cursor级) + 强模型智慧常驻 + 多维验证 + 惩罚机制

---

## V1 已完成（基础 pipeline）

- [x] Step 1: 编程规范注入 (skills/code/guide.md)
- [x] Step 2: 意图模板库 (intent_templates.py, 20+ 模板)
- [x] Step 3: 基础质量门 (quality_gate.py)
- [x] Step 4: 修复路径 (_repair)
- [x] Step 5: code_orchestrator.py 主模块
- [x] Step 6: 接入 routing_engine.py + 生产部署

## V2 已完成（容错+自愈+学习）

- [x] Step 7: 后端信誉分系统 (backend_reputation.py)
- [x] Step 8: 5维质量门 (安全/现代性/完整性/遵从/基础, 0-100评分)
- [x] Step 9: 修复熔断 (2次上限 + 策略切换: 定向修复->从零重写)
- [x] Step 10: 延迟预算 (simple 5s / standard 12s / complex 30s)
- [x] Step 11: 强模型也验证 (Strong 输出过质量门)
- [x] Step 12: 反馈闭环 (质量门->信誉分自动更新)

## V3 已完成（上下文工程，来自 Cursor 逆向）

- [x] Step 13: 语言自动检测 (Python/JS/Rust/Go, 正则信号>=2)
- [x] Step 14: 按语言精准注入规范 (800->200 tokens, 节省75%)
- [x] Step 15: 错误上下文自动提取 (Traceback/error[E]/TypeError)
- [x] Step 16: 对比分析文档 (docs/CONTEXT_ENGINEERING.md)

---

## 架构总览

用户编程请求
    |
    v
Phase 0: 上下文工程 (V3)
  - 语言检测 -> 精准规范注入 (200 tokens vs 800)
  - 错误上下文提取 -> 增强 debug 能力
  - 意图模板匹配 -> 零成本 prompt 增强
    |
    v
Phase 1: 分层执行 (V1)
  - Simple: Fast 池直出 (70% 请求)
  - Standard: Coder 池 + 质量门 (20%)
  - Complex: Strong 池优先 (10%)
  - 后端按信誉分排序 (V2)
  - 延迟预算硬性时间墙 (V2)
    |
    v
Phase 2: 多维质量门 (V2)
  - 5维评分: 基础/遵从/安全/现代性/正确性
  - Hard fail: 拒绝回答/思维链泄露
  - >=70分通过, <70分进入修复
    |
    v
Phase 3: 修复熔断 (V2)
  - 策略1: 定向修复 (告诉 Strong 哪错)
  - 策略2: 从零重写 (换模型)
  - 2次失败->返回最优尝试
    |
    v
反馈闭环: 更新后端信誉分

---

## 后端角色分配

| 角色 | 后端 | 调用时机 |
|------|------|---------|
| Fast | groq_gptoss, cerebras_gptoss, groq_llama4, longcat_lite | Simple 层直出 |
| Coder | cf_qwen_coder, mistral_codestral, nvidia_qwen_coder, groq_llama70b | Standard 层 |
| Strong | cf_deepseek_r1, github_gpt4o, sambanova_ds_v3 | 修复 + Complex |

## 文件清单

| 文件 | 功能 |
|------|------|
| code_orchestrator.py | 主 pipeline (V1+V2+V3) |
| quality_gate.py | 5维质量门 (0-100评分) |
| backend_reputation.py | 信誉分系统 |
| intent_templates.py | 20+ 意图增强模板 |
| skills/code/guide.md | 通用编程规范 |
| skills/code/python.md | Python 专用规范 |
| skills/code/javascript.md | JS/TS 专用规范 |
| skills/code/rust.md | Rust 专用规范 |
| docs/CONTEXT_ENGINEERING.md | 三大工具对比分析 |

## 测试与部署

- 全量测试: 103/103 通过
- 生产部署: 在线运行 (https://chat.donglicao.com)
