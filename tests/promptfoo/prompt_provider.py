"""Custom promptfoo provider for LiMa system-prompt regression.

The incoming ``prompt`` is expected to contain ``scenario=...`` and ``ide=...``
lines. The provider renders the full system prompt via
``prompt_engineering.layers.compose_system_prompt`` and returns it as the LLM
output, allowing promptfoo assertions to run against the rendered prompt text.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Make project root importable when promptfoo invokes this script.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

os.environ.setdefault("LIMA_DATA_DIR", str(_PROJECT_ROOT / "data"))

from prompt_engineering.layers import compose_system_prompt


def _extract_value(text: str, key: str) -> str:
    for line in text.strip().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def call_api(prompt: str, options: dict, context: dict) -> dict:
    scenario = _extract_value(prompt, "scenario") or "chat"
    ide = _extract_value(prompt, "ide")
    output = compose_system_prompt(ide=ide, scenario=scenario)
    return {"output": output}


if __name__ == "__main__":
    # Allow ad-hoc execution: echo '{"prompt": "scenario=chat\nide="}' | python prompt_provider.py
    data = json.loads(sys.stdin.read())
    result = call_api(data.get("prompt", ""), data.get("options", {}), data.get("context", {}))
    print(json.dumps(result, ensure_ascii=False))
