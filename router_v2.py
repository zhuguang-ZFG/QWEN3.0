#!/usr/bin/env python3
"""
Router V2: RAG + Quality Gates + Cache + Streaming
"""

import sys, os, json, re, hashlib, urllib.request, time, threading, subprocess, tempfile
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ============================================================
# CONFIG
# ============================================================
LMSTUDIO_URL = "http://localhost:1234/v1"
LOCAL_MODEL = "local-model"
RTK = r"D:\tools\rtk\rtk.exe"  # Token compressor - saves 60-90% API costs
API = {
    "claude": {"url": "https://www.right.codes/claude-aws/v1/messages", "key": "YOUR_API_KEY_HERE", "model": "claude-sonnet-4-6", "type": "general"},
    "longcat": {"url": "https://api.longcat.chat/anthropic", "key": "YOUR_API_KEY_HERE", "model": "longcat-flash-thinking-2601", "type": "reasoning"},
}
CACHE_DIR = r"D:\GIT\cache"
SEARCH_DIRS = [r"D:\GIT\Grbl_Esp32", r"D:\GIT\bCNC", r"D:\GIT\axidraw", r"D:\GIT\svg2gcode", r"D:\GIT\esp-idf-v6.0", r"D:\GIT\cc-switch"]

os.makedirs(CACHE_DIR, exist_ok=True)

# Load domain keywords
import model_router
classify_query = model_router.classify_query

# File index for RAG
_file_index = {}
def build_index():
    global _file_index
    if _file_index: return
    sources = {'.py','.cpp','.c','.h','.hpp','.rs','.ts','.js','.ino','.md','.txt','.json','.cfg','.ini'}
    for d in SEARCH_DIRS:
        if not os.path.isdir(d): continue
        for root, _, files in os.walk(d):
            for f in files:
                if os.path.splitext(f)[1].lower() in sources:
                    fp = os.path.join(root, f)
                    try:
                        if os.path.getsize(fp) > 500*1024: continue
                        with open(fp,'r',encoding='utf-8',errors='ignore') as fh:
                            _file_index[fp] = fh.read()[:3000]
                    except: pass


# ============================================================
# 1. RAG SEARCH
# ============================================================
def search_codebase(query: str, top_k=3) -> list[dict]:
    build_index()
    qkws = set(query.lower().split())
    scored = []
    for fp, content in _file_index.items():
        content_lower = content.lower()
        score = sum(content_lower.count(kw)*3 for kw in qkws if kw in content_lower)
        score += sum(content_lower.count(kw)*10 for kw in qkws if kw in fp.lower())
        if score > 0: scored.append((score, fp, content))
    scored.sort(key=lambda x:-x[0])
    return [{"file":fp, "content":content[:2000]} for _,fp,content in scored[:top_k]]


# ============================================================
# 2. QUALITY SCORING
# ============================================================
def quality_score(response: str, query: str) -> float:
    if not response or len(response) < 20: return 0.0
    if "[错误" in response or "调用失败" in response: return 0.1
    score = 1.0
    keywords = {"配置","参数","代码","文件","定义","函数","调用","地址","引脚","寄存器","src",".c",".h",".py","`","```"}
    domain_terms = {"grbl","esp32","cortex","stm32","gcode","spindle","stepper"}
    response_lower = response.lower()
    hits = sum(1 for k in keywords if k.lower() in response_lower)
    score += hits * 0.1
    domain_hits = sum(1 for d in domain_terms if d in response_lower)
    score += domain_hits * 0.15
    score -= abs(len(response) - 800) / 800 * 0.3
    return min(score, 2.0)


# ============================================================
# 3. CACHE
# ============================================================
def get_cache(query: str) -> str | None:
    h = hashlib.md5(query.encode()).hexdigest()
    cf = os.path.join(CACHE_DIR, h)
    if os.path.exists(cf):
        with open(cf,'r',encoding='utf-8') as f:
            entry = json.load(f)
            if time.time() - entry["time"] < 86400:
                return entry["response"]
    return None

def set_cache(query: str, response: str):
    h = hashlib.md5(query.encode()).hexdigest()
    with open(os.path.join(CACHE_DIR, h),'w',encoding='utf-8') as f:
        json.dump({"response":response,"time":time.time()}, f)


# ============================================================
# 4. MODEL CALLS
# ============================================================
def call_local(query: str, context: str = "", stream_callback=None) -> str:
    system = "<identity>\nred V1-Flash | 深圳市动力巢科技 (www.donglicao.com)\nCNC 嵌入式/ESP32/SVG/Grbl/逆向工程 领域专家\n</identity>\n\n<core_rules>\n# 从 Claude Code 2.0 萃取\n- 直接回答。2+2 就是 4，不是\"答案是 4\"。\n- 绝不主动创建文档 (*.md / README)。\n- 优先编辑已有文件，不新建。\n\n# 从 Orchids.app 萃取\n- KNOW WHEN TO STOP: 用户要求完成的那一刻立刻停。不额外优化。\n- PRESERVE EXISTING FUNCTIONALITY: 只改要改的，不动其他代码。\n- 一句话想清楚再动手，然后立刻执行。\n\n# 从 Kiro 萃取\n- 写最少的代码解决问题。不要多余的实现。不要 verbose。\n- Show, don't tell。用代码说话，不解释代码。\n- 果断、精准、清晰。去掉废话。\n- 不要重复自己。\n\n# 从 Comet 萃取\n- 不拍马屁。跳过所有\"好问题\"\"好主意\"。\n- 任务必须彻底完成。半完成不可接受。\n- 用 todo_write 规划复杂任务。\n\n# 从 Cursor 萃取\n- 先搜索再回答。基于原文不凭记忆。\n- 必要时自己决定调用工具，不要问用户。\n</core_rules>\n\n<response_format>\n# 从 Claude Code + Orchids 萃取\n简单问题 → 1行答案\n复杂问题 → 三层结构:\n\n**分析**: [1句话直达本质]\n**解决**: [步骤，含文件和行号]\n**代码**: [可直接运行]\n❓|✅ 确定性标注\n</response_format>\n\n<anti_patterns>\n# 所有这些 AI 工具的共同禁止项\n- 不输出\"<< 解释 >>"
    if context:
        system += f"\n\n参考以下代码库内容回答问题:\n{context[:3000]}"

    payload = {"model": LOCAL_MODEL, "messages": [{"role":"system","content":system},{"role":"user","content":query}], "temperature": 0.3, "max_tokens": 1024, "stream": stream_callback is not None}
    req = urllib.request.Request(f"{LMSTUDIO_URL}/chat/completions", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})

    if stream_callback:
        with urllib.request.urlopen(req, timeout=120) as resp:
            buffer = b""
            full = ""
            while True:
                chunk = resp.read(1024)
                if not chunk: break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if line.startswith(b"data: "):
                        data = line[6:]
                        if data == b"[DONE]": break
                        try:
                            d = json.loads(data.decode())
                            delta = d["choices"][0].get("delta", {}).get("content", "")
                            if delta:
                                full += delta
                                stream_callback(delta)
                        except: pass
            return full
    else:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]


def compress_prompt(text: str) -> str:
    """Use rtk to compress API prompts, saving 60-90% tokens."""
    if not os.path.exists(RTK): return text[:4000]
    try:
        import subprocess, tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(text)
            tmp = f.name
        result = subprocess.run([RTK, "smart", "--input", tmp], capture_output=True, text=True, timeout=15)
        os.unlink(tmp)
        return result.stdout.strip() if result.stdout else text[:4000]
    except:
        return text[:4000]


def call_api(query: str) -> str:
    compressed = compress_prompt(query)
    payload = json.dumps({"model": "claude-sonnet-4-6", "max_tokens": 1024, "system": "你是 CNC/嵌入式专家。直接回答。", "messages": [{"role":"user","content": compressed}]}).encode("utf-8")
    req = urllib.request.Request(API["claude"]["url"], data=payload, headers={"Content-Type":"application/json","x-api-key":API["claude"]["key"],"anthropic-version":"2023-06-01"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))["content"][0]["text"]


# ============================================================
# 4.5 DEEP REASONING ENGINE (LongCat Thinking)
# ============================================================
def call_longcat_thinking(query: str) -> str:
    """Call LongCat Thinking for deep reasoning on complex problems."""
    payload = json.dumps({
        "model": "longcat-flash-thinking-2601",
        "max_tokens": 2048,
        "system": "你是推理引擎。对问题进行深度分析，给出推理过程。专注于技术原理、架构设计、根本原因分析。用中文输出推理结果。",
        "messages": [{"role": "user", "content": query}]
    }).encode("utf-8")

    req = urllib.request.Request(
        API["longcat"]["url"] + "/v1/messages",
        data=payload,
        headers={"Content-Type": "application/json", "x-api-key": API["longcat"]["key"], "anthropic-version": "2023-06-01"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))["content"][0]["text"]


def is_complex(query: str) -> bool:
    """Determine if a question needs deep reasoning."""
    complex_markers = ["为什么", "原理", "怎么设计", "如何优化", "架构", "根本原因",
                        "权衡", "对比", "选型", "为什么不用", "能不能做"]
    return any(m in query for m in complex_markers) or len(query) > 100


# ============================================================
# 5. MAIN ROUTER WITH TWO-TIER GATE + DEEP REASONING
# ============================================================
def route_v2(query: str, use_rag: bool = True, stream: callable = None) -> dict:
    # Check cache
    cached = get_cache(query)
    if cached:
        return {"response": cached, "source": "cache", "score": 1.0}

    # RAG search
    context = ""
    if use_rag:
        results = search_codebase(query)
        context = "\n".join(f"文件 {r['file']}:\n{r['content']}" for r in results)

    # Tier 1: Local model or LongCat Thinking
    source = "red V1-Flash (本地)"
    thinking = ""

    if is_complex(query):
        try:
            thinking = call_longcat_thinking(query)
            source = "LongCat Thinking + red V1-Flash"
        except:
            pass  # Fall back on LongCat failure

    # Add thinking result as context for the local model
    if thinking:
        enhanced_query = f"[深度推理结果]\n{thinking[:3000]}\n\n[用户问题]\n{query}\n\n请结合以上推理和你的领域知识给出最终回答。"
    else:
        enhanced_query = query

    response = call_local(enhanced_query, context, stream)

    score = quality_score(response, query)

    # Tier 2: Quality gate - if low score, fall back to Claude
    if score < 0.6:
        try:
            api_resp = call_api(query)
            api_score = quality_score(api_resp, query)
            if api_score > score:
                response = api_resp
                source = "Claude (API兜底)"
        except:
            pass  # Keep local response on API failure

    # Cache
    if not stream:
        set_cache(query, response)

    return {"response": response, "source": source, "score": round(score, 2)}


# ============================================================
# CLI
# ============================================================
def main():
    print("=" * 60)
    print("  red V1-Flash Router V2")
    print("  RAG | Quality Gate | Cache | Streaming")
    print("=" * 60)
    print("  /rag on|off  /clear  /quit")
    print()

    use_rag = True
    while True:
        try:
            query = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见"); break
        if not query: continue
        if query == "/quit": break
        if query == "/rag off": use_rag = False; print("RAG: OFF"); continue
        if query == "/rag on": use_rag = True; print("RAG: ON"); continue
        if query == "/clear":
            import shutil; shutil.rmtree(CACHE_DIR, ignore_errors=True); os.makedirs(CACHE_DIR); print("Cache cleared"); continue

        def stream_cb(delta):
            print(delta, end="", flush=True)

        print("\nThinking...\n" + "─" * 50)
        result = route_v2(query, use_rag, stream_cb)
        print("\n" + "─" * 50)
        print(f"Source: {result['source']} | Score: {result['score']}\n")


if __name__ == "__main__":
    main()
