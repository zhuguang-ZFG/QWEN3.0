# Routing Model Edge Cases

## 1. Kiro vs Cursor (both VS Code forks)
- Kiro: LangChain tool wrappers (createReadFileTool, createExecuteBashTool)
- Cursor: raw tool names (read_file, run_terminal_cmd)
- Kiro: spec workflow agents, langgraph references
- Cursor: ApplyPatch, todo_write, read_lints, Anysphere

## 2. Cursor vs Claude Code (similar tool concepts)
- Both use <user_query> tags
- Claude Code: EnterPlanMode, CLAUDE.md, Glob/Grep, Edit/Write
- Cursor: run_terminal_cmd, todo_write, ApplyPatch
- Claude Code: Anthropic, settings.local.json, hooks

## 3. Codex vs Claude Code (both CLI tools)
- Codex: rg/multi_tool_use.parallel, snake_case tools, GPT-5
- Claude Code: Glob/Grep/PascalCase, Anthropic, CLAUDE.md

## 4. Minimal prompts (short, generic)
- "You are a helpful assistant" without tool info -> Kiro or generic
- Need at least tool names or directory references to distinguish

## 5. Multi-model scenarios
- Same tool may use different models (Cursor with GPT-4 vs Claude-Sonnet)
- Model name alone is NOT a reliable signal
