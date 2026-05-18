# 实时系统提示词捕获 Hook 配置指南

## 1. Claude Code Hook (settings.json)

在 `C:\Users\zhugu\.claude\settings.json` 中添加：

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "",
        "command": "python3 C:/Users/zhugu/Desktop/capture_prompt.py --tool claude --session $CLAUDE_SESSION_ID"
      }
    ],
    "Stop": [
      {
        "command": "python3 C:/Users/zhugu/Desktop/capture_prompt.py --tool claude --event stop --session $CLAUDE_SESSION_ID"
      }
    ]
  }
}
```

## 2. Codex Hook (config.toml)

Codex 使用 TOML 配置，在 `C:\Users\zhugu\.codex\config.toml` 中添加：

```toml
[hooks]
post_tool = "python3 C:/Users/zhugu/Desktop/capture_prompt.py --tool codex"
on_stop = "python3 C:/Users/zhugu/Desktop/capture_prompt.py --tool codex --event stop"
```

## 3. 捕获脚本 (Windows 兼容)

创建 `C:\Users\zhugu\Desktop\capture_prompt.py`：
"""

import json, os, sys, time, argparse
from datetime import datetime

CAPTURE_DIR = "C:/Users/zhugu/Desktop/prompt_captures"
os.makedirs(CAPTURE_DIR, exist_ok=True)

def capture(tool, event="tool_call", session_id="", extra=None):
    """Capture system prompt and metadata."""
    timestamp = datetime.now().isoformat()
    record = {
        "tool": tool,
        "event": event,
        "session_id": session_id,
        "timestamp": timestamp,
        "extra": extra or {},
    }

    # Try to read stdin for prompt data (passed by the hook)
    try:
        stdin_data = sys.stdin.read()
        if stdin_data:
            record["hook_input"] = stdin_data[:10000]  # cap
    except:
        pass

    # Try environment variables for prompt fragments
    for env_var in ["SYSTEM_PROMPT", "MODEL_NAME", "TOOL_NAME", "SESSION_ID"]:
        val = os.environ.get(env_var)
        if val:
            record[env_var.lower()] = val

    filename = f"{CAPTURE_DIR}/{tool}_{timestamp.replace(':', '-')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    # Also append to cumulative log
    log_file = f"{CAPTURE_DIR}/all_captures.jsonl"
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')

    print(f"[capture] Saved to {filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", required=True, choices=["cursor", "codex", "claude", "kiro"])
    parser.add_argument("--event", default="tool_call")
    parser.add_argument("--session", default="")
    args = parser.parse_args()
    capture(args.tool, args.event, args.session)
