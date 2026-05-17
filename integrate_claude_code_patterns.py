#!/usr/bin/env python3
"""
Integrate Claude Code internal agent patterns into red V1-Flash router.
Extracted from Piebald-AI/claude-code-system-prompts.
"""

import json

OUTPUT = r"D:\GIT\claude_code_patterns.json"

# Pattern 1: Explore Agent → Optimize our RAG search
EXPLORE_PATTERN = """
<codebase_exploration>
# From Claude Code Explore Agent (v2.1.118)
- READ-ONLY mode: search and analyze only, never modify files
- Use glob for file patterns, grep for content, read for specific files
- Spawn parallel tool calls wherever possible for efficiency
- Adapt search thoroughness: quick/medium/very thorough
- Return results directly as a message, don't create files
</codebase_exploration>
"""

# Pattern 2: Memory Synthesis → Optimize conversation memory
MEMORY_PATTERN = """
<memory_rules>
# From Claude Code Memory Synthesis Agent (v2.1.111)
- For each query, extract at most 7 relevant facts from conversation history
- Each fact is 1-2 sentences, actionable, stands alone
- A fact is useful if it: avoids re-asking, applies user preferences, maintains continuity, avoids known pitfalls
- Cite the source message/file for each fact
- Do NOT answer the query yourself - just retrieve relevant context
- If nothing is relevant, return empty
</memory_rules>
"""

# Pattern 3: Conversation Summarization → Optimize long conversations
SUMMARIZATION_PATTERN = """
<summarization_rules>
# From Claude Code Summarization Agent (v2.1.139)
When compressing conversation history:
1. Capture all user explicit requests and intents
2. Preserve security instructions and constraints verbatim
3. List all files examined, modified, or created with reasons
4. Record all errors and how they were fixed
5. Track pending tasks and current work
6. Include the next step with verbatim quotes from the user

After compression, the compressed history should be self-contained - a new assistant reading it should understand exactly what's happening.
</summarization_rules>
"""

# Training pairs demonstrating Claude Code patterns
TRAINING_PAIRS = [
    # Pattern: Explore agent style - efficient parallel search
    {"messages": [
        {"role": "user", "content": "帮我找代码库里所有和步进电机控制相关的文件"},
        {"role": "assistant", "content": "并行搜索...\n\n**grep**: `stepper|step_motor|Stepper` → 找到 12 个文件\n\n**关键文件**:\n- `Grbl_Esp32/grbl/stepper.c` — 步进脉冲生成核心\n- `Grbl_Esp32/grbl/planner.c` — 运动规划中的步进控制\n- `Grbl_Esp32/grbl/config.h:45` — `STEP_PULSE_DELAY` 宏定义\n\n已排除无关文件。需要打开哪个？"}
    ]},

    # Pattern: Memory synthesis - precise context retrieval
    {"messages": [
        {"role": "user", "content": "上个月我们聊过的那个 Grbl 归零问题，现在又出现了"},
        {"role": "assistant", "content": "回溯到相关记忆：\n\n1. 上次问题: Grbl 归零时 X 轴不动，Y/Z 正常 → 原因: X 轴限位开关未触发，$21=1 但开关接线在常开触点\n2. 解决方案: 改接线到常闭触点，或 `$5=1` 反转限位逻辑\n3. 涉及的代码: `limits.c:128` `limits_get_state()` 函数\n\n这次是同样的症状吗？X 轴不动？"}
    ]},

    # Pattern: Conversation summarization style
    {"messages": [
        {"role": "user", "content": "/summarize 总结一下我们最近的对话"},
        {"role": "assistant", "content": "**当前项目**: red V1-Flash 模型训练与路由系统搭建\n\n**已完成**:\n- Round 3 训练 (208K 数据, 含反幻觉+无审查+逆向)\n- Qwen3-8B 基座模型下载\n- 三路蒸馏运行中 (771 对)\n- CC-switch 配置 4 个供应商\n- rtk token 压缩集成\n- Claude Code 内部提示词学习\n\n**当前进行中**:\n- Round 3 训练 (checkpoint 700/1000)\n- 三路蒸馏 (771/1900+)\n\n**下一步**: Round 3 完成后启动 Round 4 (Qwen3-8B 基座 + 蒸馏数据)"}
    ]},

    # Pattern: Explore agent without access to Edit/Write - just search
    {"messages": [
        {"role": "user", "content": "这个项目里用了哪些 ESP32 外设"},
        {"role": "assistant", "content": "遍历代码库...\n\n**GPIO**: `gpio.c:45-120` — 输入/输出/中断配置\n**I2C**: `i2c_master.c:30-200` — MPU6050 和 OLED 驱动\n**SPI**: `spi_slave.c:全文件` — 与 FPGA 通信\n**UART**: `uart.c:15-300` — GCode 串口接收\n**WiFi**: `wifi.c:50-180` — Web 界面和 OTA\n**PWM**: `ledc.c:25-100` — 主轴和激光功率控制\n**ADC**: `adc.c:10-80` — 限位开关电压检测\n\n跨文件引用：`board_init()` 在 `main.c:200` 统一初始化所有外设。"}
    ]},
]

# Claude Code tool descriptions we should mirror
TOOL_PATTERNS = {
    "search_codebase": {
        "description": "Fast codebase exploration using glob patterns and regex",
        "when_to_use": "Find files by pattern (eg. 'src/**/*.c'), search code for keywords",
        "when_not_to_use": "When you already know the exact file path (use read_file instead)",
        "thoroughness_levels": ["quick", "medium", "very thorough"],
        "parallel_capable": True,
    },
    "read_file": {
        "description": "Read a specific file by path",
        "when_to_use": "When you know the exact file path",
        "when_not_to_use": "When you need to search for files (use search_codebase)",
    },
    "summarize_context": {
        "description": "Compress conversation history for memory management",
        "when_to_use": "When conversation exceeds 10 turns",
        "what_to_preserve": ["user intent", "security constraints", "file changes", "error fixes", "pending tasks"],
    },
}


def main():
    patterns = {
        "explore_pattern": EXPLORE_PATTERN.strip(),
        "memory_pattern": MEMORY_PATTERN.strip(),
        "summarization_pattern": SUMMARIZATION_PATTERN.strip(),
        "training_pairs": TRAINING_PAIRS,
        "tool_patterns": TOOL_PATTERNS,
        "source": "Piebald-AI/claude-code-system-prompts (v2.1.139)",
        "extracted_agents": [
            "Explore Agent (codebase exploration)",
            "Memory Synthesis Agent (context retrieval)",
            "Conversation Summarization Agent (history compression)",
            "CLAUDE.md Creation Agent (project documentation)",
        ],
    }

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(patterns, f, ensure_ascii=False, indent=2)

    print(f"Extracted Claude Code patterns saved to {OUTPUT}")
    print(f"Training pairs: {len(TRAINING_PAIRS)}")
    print(f"Tool patterns: {len(TOOL_PATTERNS)}")
    print(f"Agents modeled: {len(patterns['extracted_agents'])}")


if __name__ == '__main__':
    main()
