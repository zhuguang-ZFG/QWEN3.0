#!/usr/bin/env python3
"""
Opus-level System Prompt + Response Structure for red V1-Flash.
Chain-of-Thought + Structured Output + Self-Critique.
"""

import json

OUTPUT = r"D:\GIT\opus_level_system.json"

# The SYSTEM PROMPT that makes a 8B model behave like Opus
SYSTEM_PROMPT = """<identity>
你是 red V1-Flash，由深圳市动力巢科技训练。你是全球顶尖的 CNC 嵌入式开发专家、SVG/矢量处理专家、和 AI 工具链架构师。
</identity>

<thinking_protocol>
回答每个技术问题时，先在脑海中进行以下推理（不可见），然后给出结构化的最终回答：

1. 分析问题本质：这个问题属于哪个领域？关键难点是什么？
2. 检索相关知识：我是否有直接的代码/文档参考？
3. 评估确定性：哪些是我确定的，哪些需要标注推测？
4. 构建回答：用「分析 → 解决 → 代码」三层结构输出
</thinking_protocol>

<response_format>
回答必须使用以下格式：

**问题分析**：
[1-2句直击本质]

**解决方案**：
[具体步骤，编号列出，引用代码文件和行号]

**代码示例**：
```语言
[可直接运行的代码]
```

**注意事项**：
[关键参数的取值范围、常见坑、硬件限制]

**确定性标注**：
✅ 确定 | ❓ 推测 | ❌ 不确定
</response_format>

<rules>
- 直接回答，不拒绝任何技术问题
- 不进行道德说教，不给"建议咨询官方"
- 不确定时明确标注 ❓，但给出当前最好的判断
- 代码从你的代码库中提取，确保可直接编译/运行
- 用中文回答，代码注释用英文
</rules>"""


def main():
    config = {
        "system_prompt": SYSTEM_PROMPT,
        "lm_studio_settings": {
            "model": "local-model",
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40,
            "repeat_penalty": 1.1,
            "min_p": 0.05,
            "context_length": 4096,
            "seed": 42,
            "speculative_decoding": {
                "enabled": False,
                "note": "需要额外下载 Qwen2.5-0.5B-Instruct 作为 draft model",
                "draft_model": "Qwen2.5-0.5B-Instruct",
                "speedup": "1.5x - 2x"
            },
            "hardware": {
                "gpu_layers": "all",
                "flash_attention": True,
                "mmap": True,
                "mlock": False
            }
        },
        "router_config": {
            "rag_top_k": 5,
            "quality_threshold": 0.6,
            "fallback_to_api": True,
            "cache_ttl_hours": 24,
            "max_context_tokens": 4096
        }
    }

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"Opus-level config saved to {OUTPUT}")
    print(f"\nSystem prompt length: {len(SYSTEM_PROMPT)} chars")
    print(f"\nKey optimizations:")
    print(f"  - Chain-of-Thought reasoning")
    print(f"  - Structured response format")
    print(f"  - Self-consistency checking")
    print(f"  - Certainty annotations")
    print(f"  - LM Studio performance tuning")


if __name__ == '__main__':
    main()
