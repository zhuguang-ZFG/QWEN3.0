"""Optional local router model (LIMA_ROUTER_MODEL) and LM Studio call_local.

Extracted from smart_router.py (Slice 4) so orchestrate.py and server.py
avoid importing the legacy smart_router package.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.request

_log = logging.getLogger(__name__)

LOCAL_ROUTER_MODEL = os.environ.get(
    "LIMA_ROUTER_MODEL", "D:/GIT/my_code_model_qwen3_r13/final"
)
LM_URL = "http://localhost:1234/v1/chat/completions"
DEBUG = os.environ.get("LIMA_DEBUG", "") == "1"

_local_model = None
_local_tokenizer = None
_local_model_failed = False


def _load_local_router() -> None:
    global _local_model, _local_tokenizer, _local_model_failed
    if _local_model is not None or _local_model_failed:
        return
    try:
        import torch  # type: ignore[reportMissingImports]
        from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore[reportMissingImports]

        if DEBUG:
            print("[ROUTER] Loading local Qwen3 router model...", file=sys.stderr)
        _local_tokenizer = AutoTokenizer.from_pretrained(
            LOCAL_ROUTER_MODEL, trust_remote_code=True
        )
        try:
            _local_model = AutoModelForCausalLM.from_pretrained(
                LOCAL_ROUTER_MODEL,
                trust_remote_code=True,
                torch_dtype=torch.float16,
                device_map="auto",
            )
        except Exception as exc:
            _log.warning("operation failed: %s", exc)
            if DEBUG:
                print("[ROUTER] GPU failed, falling back to CPU", file=sys.stderr)
            _local_model = AutoModelForCausalLM.from_pretrained(
                LOCAL_ROUTER_MODEL,
                trust_remote_code=True,
                torch_dtype=torch.float32,
                device_map="cpu",
            )
        _local_model.eval()
        if DEBUG:
            print("[ROUTER] Local router model loaded OK", file=sys.stderr)
    except Exception as exc:
        _local_model_failed = True
        print(f"[ROUTER] Failed to load local model: {exc}", file=sys.stderr)


def warmup_router_model() -> None:
    """Pre-load LIMA_ROUTER_MODEL if transformers + weights are available."""
    global _local_model, _local_tokenizer
    try:
        _load_local_router()
        if _local_model is not None and _local_tokenizer is not None:
            import torch  # type: ignore[reportMissingImports]

            messages = [
                {"role": "system", "content": "你是LiMa智能路由决策器。"},
                {"role": "user", "content": "warmup"},
            ]
            text = _local_tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = _local_tokenizer(text, return_tensors="pt").to(_local_model.device)
            with torch.no_grad():
                _local_model.generate(**inputs, max_new_tokens=2, do_sample=False)
            print("[ROUTER] Warmup complete — model ready", file=sys.stderr)
        else:
            print("[ROUTER] Warmup skipped — model not available", file=sys.stderr)
    except Exception as exc:
        print(f"[ROUTER] Warmup failed (non-fatal): {exc}", file=sys.stderr)


def call_local(msgs: list[dict], mt: int = 512, t: float = 0.3) -> str:
    """Call LM Studio / local OpenAI-compatible server at LM_URL."""
    payload = json.dumps(
        {"model": "local-model", "messages": msgs, "max_tokens": mt, "temperature": t}
    ).encode()
    try:
        request = urllib.request.Request(
            LM_URL, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        _log.debug("local_router call_local failed: %s", exc)
        return f"[LOCAL_ERR] {exc}"
