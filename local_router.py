"""Local routing model service — Qwen3-1.7B intent classifier."""

import asyncio
import json
import re
import time
from contextlib import asynccontextmanager

import torch
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_PATH = "D:/GIT/my_code_model_qwen3_r13/final/"
PORT = 8090

# Global state
model = None
tokenizer = None
start_time: float = 0.0
_inference_lock = asyncio.Lock()

SYSTEM_PROMPT = """You are an intent router. Given a user query, output ONE JSON object selecting the best backend.

## Backends (pick exactly one):
- longcat_lite: casual chat, greetings, simple Q&A, translations, summaries (<30s tasks)
- longcat_chat: multi-turn Chinese conversations, creative writing, brainstorming
- nvidia_qwen_coder: code generation, debugging, refactoring, algorithms, technical implementation
- deepseek_pro: complex math proofs, multi-step reasoning, research analysis, long-form arguments
- longcat_thinking: step-by-step problem solving, logic puzzles, planning, decision analysis
- longcat_omni: image understanding, visual questions, OCR, diagram analysis
- chinamobile_deepseek: Chinese knowledge, history, culture, education, exam prep

## Output format (strictly follow):
{"intent":"<category>","complexity":<0.0-1.0>,"backend":"<name>","confidence":<0.0-1.0>}

## Examples:
Query: "hello" → {"intent":"chat","complexity":0.1,"backend":"longcat_lite","confidence":0.99}
Query: "implement quicksort in rust" → {"intent":"code","complexity":0.6,"backend":"nvidia_qwen_coder","confidence":0.95}
Query: "prove P≠NP" → {"intent":"reasoning","complexity":0.95,"backend":"deepseek_pro","confidence":0.9}
Query: "这张图片里有什么" → {"intent":"vision","complexity":0.4,"backend":"longcat_omni","confidence":0.95}
Query: "帮我分析一下这个架构的优缺点" → {"intent":"analysis","complexity":0.7,"backend":"longcat_thinking","confidence":0.85}
Query: "唐朝有哪些著名诗人" → {"intent":"knowledge","complexity":0.3,"backend":"chinamobile_deepseek","confidence":0.9}"""

VALID_BACKENDS = [
    "longcat_lite", "longcat_chat", "nvidia_qwen_coder",
    "deepseek_pro", "longcat_thinking", "longcat_omni",
    "chinamobile_deepseek",
]


class RouteRequest(BaseModel):
    query: str
    mode: str = "fast"
    ide: str = "unknown"
    system_prompt: str | None = None


class RouteResponse(BaseModel):
    intent: str
    complexity: float = Field(ge=0.0, le=1.0)
    backend: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = "local_model"


def fallback_route(query: str, mode: str) -> dict:
    """Heuristic fallback when model inference fails."""
    q = query.lower()
    if mode == "vision" or any(w in q for w in ["image", "picture", "photo", "看图", "图片"]):
        return {"intent": "vision", "complexity": 0.5, "backend": "longcat_omni", "confidence": 0.6}
    if any(w in q for w in ["code", "function", "implement", "debug", "代码", "编程", "写一个"]):
        return {"intent": "code_generation", "complexity": 0.7, "backend": "nvidia_qwen_coder", "confidence": 0.7}
    if any(w in q for w in ["prove", "math", "calculate", "reason", "分析", "推理", "数学"]):
        return {"intent": "reasoning", "complexity": 0.8, "backend": "deepseek_pro", "confidence": 0.6}
    if any(w in q for w in ["think", "step by step", "深度", "思考"]):
        return {"intent": "thinking", "complexity": 0.7, "backend": "longcat_thinking", "confidence": 0.6}
    return {"intent": "chat", "complexity": 0.3, "backend": "longcat_lite", "confidence": 0.5}


def build_prompt(query: str, mode: str, ide: str) -> str:
    """Build classification prompt — minimal, let few-shot examples guide the model."""
    return f'Query: "{query[:300]}"'


def parse_model_output(text: str) -> dict | None:
    """Extract JSON from model output."""
    matches = list(re.finditer(r'\{[^{}]*\}', text))
    for m in reversed(matches):
        try:
            data = json.loads(m.group())
            if not all(k in data for k in ("intent", "complexity", "backend", "confidence")):
                continue
            data["complexity"] = max(0.0, min(1.0, float(data["complexity"])))
            data["confidence"] = max(0.0, min(1.0, float(data["confidence"])))
            if data["backend"] not in VALID_BACKENDS:
                data["backend"] = "longcat_lite"
            return data
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup."""
    global model, tokenizer, start_time
    print("=" * 60)
    print("  Local Router Service — Qwen3-1.7B-R13")
    print(f"  Model path: {MODEL_PATH}")
    print(f"  Port: {PORT}")
    print(f"  CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        print(f"  GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    print("=" * 60)

    t0 = time.time()
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_PATH,
            torch_dtype="auto",
            device_map="auto",
            trust_remote_code=True,
        )
        model.eval()
    except Exception as e:
        print(f"\n[FATAL] Failed to load model: {e}")
        raise SystemExit(1)

    # Warmup inference
    warmup_msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": 'Query: "hello"'},
    ]
    warmup_text = tokenizer.apply_chat_template(warmup_msgs, tokenize=False, add_generation_prompt=True)
    warmup_ids = tokenizer(warmup_text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        model.generate(**warmup_ids, max_new_tokens=5, do_sample=False)
    del warmup_ids
    print(f"\n  Warmup done")

    load_time = time.time() - t0
    mem_used = torch.cuda.memory_allocated() / 1024**3 if torch.cuda.is_available() else 0
    print(f"  Model loaded in {load_time:.1f}s | GPU mem: {mem_used:.2f} GB")
    print(f"  Serving on http://0.0.0.0:{PORT}")
    print("=" * 60)
    start_time = time.time()
    yield


app = FastAPI(title="Local Router", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health():
    model_loaded = model is not None and tokenizer is not None
    return {
        "status": "ok" if model_loaded else "degraded",
        "model_loaded": model_loaded,
        "model": "qwen3-1.7b-r13",
        "gpu": "cuda" if torch.cuda.is_available() else "cpu",
        "uptime_s": int(time.time() - start_time),
    }


@app.post("/route", response_model=RouteResponse)
async def route(req: RouteRequest):
    t0 = time.time()
    query_preview = req.query[:80]

    try:
        user_content = build_prompt(req.query, req.mode, req.ide)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        async with _inference_lock:
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(text, return_tensors="pt").to(model.device)

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=40,
                    do_sample=False,
                )

            generated = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
            del inputs, outputs

        result = parse_model_output(generated)

        if result is None:
            result = fallback_route(req.query, req.mode)
            result["source"] = "fallback"
        else:
            result["source"] = "local_model"

    except Exception as e:
        print(f"[ERROR] Inference failed: {e}")
        result = {"intent": "unknown", "complexity": 0.5, "backend": "longcat_lite", "confidence": 0.0, "source": "error"}

    latency_ms = (time.time() - t0) * 1000
    print(f"[ROUTE] {latency_ms:.0f}ms | {result['backend']} | {query_preview}")
    return RouteResponse(**result)


if __name__ == "__main__":
    uvicorn.run("local_router:app", host="0.0.0.0", port=PORT, workers=1)

