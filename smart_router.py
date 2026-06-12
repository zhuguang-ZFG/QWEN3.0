#!/usr/bin/env python3
"""LiMa Smart Router — **LEGACY FACADE** (V3 uses routing_engine + http_caller).

⚠️  This module is a backward-compatibility shim.
    New code should import directly from the underlying modules:

    | Need                        | Import from                    |
    |-----------------------------|---------------------------------|
    | Backend config              | `from backends import BACKENDS` |
    | Thinking intent detection   | `from router_intent import detect_thinking_intent` |
    | Image intent detection      | `from router_image import detect_image_intent` |
    | HTTP call                   | `from http_caller import call_api` |
    | Response cleaning           | `from response_cleaner import clean_response` |
    | Prompt assembly             | `from router_prompt import assemble_prompt` |
    | Circuit breaker             | `from router_circuit_breaker import cb_allow, cb_record` |

    Extracted modules (CQ-014):
      routing_engine.py      V3 five-layer routing (authoritative entry)
      router_circuit_breaker.py  cb_allow / cb_record / cb_status
      router_intent.py       detect_thinking_intent / get_thinking_backend
      router_classifier.py   analyze / rule_classify / signal_classify
      router_prompt.py       assemble_prompt / SYS
      router_http.py         call_api / call_api_stream (legacy urllib)
      router_image.py        detect_image_intent
      vision_handler.py      detect_vision_request / convert_openai_vision_to_anthropic
      response_cleaner.py    clean_response
"""
import json
import os
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[reportAttributeAccessIssue]
from dotenv import load_dotenv

load_dotenv()

LOCAL_ROUTER_MODEL = os.environ.get("LIMA_ROUTER_MODEL", "D:/GIT/my_code_model_qwen3_r13/final")
_local_model = None
_local_tokenizer = None
_local_model_failed = False

DEBUG = os.environ.get("LIMA_DEBUG", "") == "1"
LM_URL = "http://localhost:1234/v1/chat/completions"

from backends import BACKENDS, GFW_BACKENDS, THINKING_BACKENDS, VISION_BACKENDS

PUBLIC_MODEL_NAME = os.environ.get("PUBLIC_MODEL_NAME", "LiMa")

ROUTE = {
    "trivial": "nvidia_phi4",
    "cnc_trouble": "longcat_thinking",
    "grbl_config": "local",
    "gcode_help": "local",
    "embedded_dev": "nvidia_nemotron",
    "code_generation": "nvidia_qwen_coder",
    "architecture": "longcat",
    "general_cnc": "longcat_lite",
    "tool_task": "llm7",
    "image_gen": "pollinations",
    "complex_theory": "longcat_thinking",
    "thinking": "or_deepseek_r1",
    "unknown": "longcat_chat",
}

from router_circuit_breaker import cb_allow, cb_record, cb_status
from router_intent import detect_thinking_intent, get_thinking_backend
from router_classifier import RULES, analyze, rule_classify, signal_classify
from router_prompt import FRAGMENT_DIR, SYS, assemble_prompt
from router_http import (
    GFW_PROXY_URL,
    _build_request_body,
    _call_cf_vision,
    _get_opener,
    call_api,
    call_api_stream,
)
from router_local import call_local
from router_image import detect_image_intent
from response_cleaner import clean_response
from vision_handler import (
    VISION_SYSTEM_PROMPT,
    convert_openai_vision_to_anthropic,
    detect_vision_request,
)


def _has_vision_content(messages: list) -> bool:
    return detect_vision_request(messages)


def _load_local_router():
    global _local_model, _local_tokenizer, _local_model_failed
    if _local_model is not None or _local_model_failed:
        return
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore[reportMissingImports]
        import torch  # type: ignore[reportMissingImports]

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
        except Exception:
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


def warmup_router_model():
    global _local_model, _local_tokenizer, _local_model_failed
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


DISTILL_QUEUE_DIR = os.path.join(os.path.dirname(__file__), "data", "distill_queue", "pending")


def _quick_score(query: str, answer: str) -> float:
    if not answer:
        return 0.0

    length = len(answer)
    if 100 <= length <= 2000:
        len_score = 1.0
    elif length < 50:
        len_score = 0.0
    elif length < 100:
        len_score = (length - 50) / 50
    else:
        len_score = max(0.7, 1.0 - (length - 2000) / 5000)

    fmt_score = 0.0
    if "```" in answer and answer.count("```") % 2 == 0:
        fmt_score += 0.4
    if any(char.isdigit() for char in answer):
        fmt_score += 0.3
    if any(marker in answer for marker in ["1.", "2.", "- ", "* ", "步骤"]):
        fmt_score += 0.3

    comp_score = 1.0
    if any(marker in answer for marker in ["抱歉", "无法", "不确定", "我不能", "暂时不可用"]):
        comp_score = 0.3

    query_words = set(query.lower().replace("?", "").replace("？", "").split())
    answer_lower = answer.lower()
    if query_words:
        overlap = sum(1 for word in query_words if word in answer_lower and len(word) > 1)
        rel_score = min(1.0, overlap / max(len(query_words) * 0.3, 1))
    else:
        rel_score = 0.5

    return round(len_score * 0.3 + fmt_score * 0.3 + comp_score * 0.2 + rel_score * 0.2, 3)


def _log_to_distill_queue(query: str, answer: str, intent: dict, backend: str) -> None:
    if os.environ.get("DISTILL_LOG", "0") != "1":
        return
    if backend == "local":
        return
    if not answer or "暂时不可用" in answer:
        return

    try:
        os.makedirs(DISTILL_QUEUE_DIR, exist_ok=True)
        import datetime
        import hashlib

        score = _quick_score(query, answer)
        entry = {
            "query": query,
            "answer": answer,
            "intent": intent.get("intent", "unknown"),
            "complexity": intent.get("complexity", 0.5),
            "source_backend": backend,
            "quality_score": score,
            "routing_correct": score >= 0.7,
            "logged_at": datetime.datetime.now().isoformat(),
        }
        qhash = hashlib.md5(query.encode()).hexdigest()[:8]
        ts = time.strftime("%Y%m%d_%H%M%S")
        fname = os.path.join(DISTILL_QUEUE_DIR, f"{ts}_{qhash}.json")
        with open(fname, "w", encoding="utf-8") as handle:
            json.dump(entry, handle, ensure_ascii=False, indent=2)
        if DEBUG:
            print(f"[DISTILL] logged: {query[:30]}... -> {backend}", file=sys.stderr)
    except Exception as exc:
        if DEBUG:
            print(f"[DISTILL] log failed: {exc}", file=sys.stderr)
