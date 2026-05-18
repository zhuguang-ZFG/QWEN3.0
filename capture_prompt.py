"""实时系统提示词捕获脚本 - 供各工具的 hook 系统调用"""
import json, os, sys, time, argparse
from datetime import datetime

CAPTURE_DIR = "C:/Users/zhugu/Desktop/prompt_captures"
os.makedirs(CAPTURE_DIR, exist_ok=True)

def capture(tool, event="tool_call", session_id="", extra=None):
    timestamp = datetime.now().isoformat()
    record = {
        "tool": tool,
        "event": event,
        "session_id": session_id,
        "timestamp": timestamp,
        "extra": extra or {},
    }

    try:
        stdin_data = sys.stdin.read()
        if stdin_data:
            record["hook_input"] = stdin_data[:10000]
    except:
        pass

    for env_var in ["SYSTEM_PROMPT", "MODEL_NAME", "TOOL_NAME", "SESSION_ID"]:
        val = os.environ.get(env_var)
        if val:
            record[env_var.lower()] = val

    filename = f"{CAPTURE_DIR}/{tool}_{timestamp.replace(':', '-')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    log_file = f"{CAPTURE_DIR}/all_captures.jsonl"
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')

    print(f"[capture] {tool}/{event} -> {filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool", required=True, choices=["cursor", "codex", "claude", "kiro"])
    parser.add_argument("--event", default="tool_call")
    parser.add_argument("--session", default="")
    args = parser.parse_args()
    capture(args.tool, args.event, args.session)
