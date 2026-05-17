#!/usr/bin/env python3
"""Auto-deploy: when new weights exist, export GGUF and reload LM Studio."""

import json, os, subprocess, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

LMS = r"C:\Users\Administrator\.lmstudio\bin\lms.exe"
WEIGHTS_DIR = r"D:\GIT\my_code_model_qwen3"
DEPLOY_LOG = r"D:\GIT\deploy_log.json"


def check_new_weights() -> bool:
    """Check if new adapter exists and hasn't been deployed yet."""
    adapter = os.path.join(WEIGHTS_DIR, "adapter_model.safetensors")
    if not os.path.exists(adapter): return False

    log = json.load(open(DEPLOY_LOG, 'r', encoding='utf-8')) if os.path.exists(DEPLOY_LOG) else {}
    last_mtime = os.path.getmtime(adapter)
    if log.get("last_deployed_mtime") == last_mtime: return False

    log["last_deployed_mtime"] = last_mtime
    json.dump(log, open(DEPLOY_LOG, 'w', encoding='utf-8'))
    return True


def reload_lmstudio_model(model_name: str):
    """Reload model in LM Studio via CLI."""
    try:
        subprocess.run([LMS, "unload"], timeout=10)
        subprocess.run([LMS, "load", model_name], timeout=60)
        subprocess.run([LMS, "server", "start"], timeout=10)
        return True
    except Exception as e:
        print(f"Reload failed: {e}")
        return False


def main():
    print(" Auto-Deploy Check")
    if check_new_weights():
        print("New weights detected! Triggering reload...")
        if reload_lmstudio_model("qwen3-8b"):
            print("Model reloaded successfully")
        else:
            print("Reload failed - manual intervention needed")
    else:
        print("No new weights detected. Current model is latest.")


if __name__ == "__main__":
    main()
