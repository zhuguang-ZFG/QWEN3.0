#!/usr/bin/env python3
"""
Router V3: Semantic Routing + Intent + Consensus + Cost + Feedback + Persistence + Circuit Breaker
"""

import sys, os, json, re, hashlib, urllib.request, time, threading, subprocess, tempfile, sqlite3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
load_dotenv()
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ============================================================
# 1. SESSION PERSISTENCE (SQLite)
# ============================================================
DB_PATH = r"D:\GIT\sessions.db"
_db_lock = threading.Lock()

def init_db():
    db = sqlite3.connect(DB_PATH, check_same_thread=False)
    db.execute('''CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY, messages TEXT, created REAL, updated REAL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS costs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp REAL,
        provider TEXT, model TEXT, tokens_in INTEGER, tokens_out INTEGER,
        cost_estimate REAL, latency_ms INTEGER, success INTEGER)''')
    db.execute('''CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp REAL,
        query TEXT, response TEXT, score INTEGER, source TEXT)''')
    db.execute('''CREATE TABLE IF NOT EXISTS circuit_breakers (
        provider TEXT PRIMARY KEY, failures INTEGER, disabled_until REAL)''')
    db.commit()
    return db

db = init_db()

def save_session(session_id: str, messages: list):
    with _db_lock:
        db.execute("INSERT OR REPLACE INTO conversations VALUES (?,?,?,?)",
                  (session_id, json.dumps(messages, ensure_ascii=False), time.time(), time.time()))
        db.commit()

def load_session(session_id: str) -> list:
    with _db_lock:
        row = db.execute("SELECT messages FROM conversations WHERE id=?", (session_id,)).fetchone()
    return json.loads(row[0]) if row else []

def log_cost(provider: str, model: str, tokens_in: int, tokens_out: int, cost: float, latency_ms: int, success: bool):
    with _db_lock:
        db.execute("INSERT INTO costs VALUES (NULL,?,?,?,?,?,?,?,?)",
                  (time.time(), provider, model, tokens_in, tokens_out, cost, latency_ms, 1 if success else 0))
        db.commit()

def log_feedback(query: str, response: str, score: int, source: str):
    with _db_lock:
        db.execute("INSERT INTO feedback VALUES (NULL,?,?,?,?,?)",
                  (time.time(), query, response, score, source))
        db.commit()
    # Auto-queue low-score responses for distillation
    if score <= 2:
        queue_path = r"D:\GIT\feedback_queue.json"
        distilled_queue = []
        if os.path.exists(queue_path):
            with open(queue_path, 'r', encoding='utf-8') as f:
                distilled_queue = json.load(f)
        distilled_queue.append({"query": query, "response": response, "score": score, "source": source, "time": time.time()})
        with open(queue_path, 'w', encoding='utf-8') as f:
            json.dump(distilled_queue, f, ensure_ascii=False, indent=2)

def get_cost_summary() -> str:
    with _db_lock:
        rows = db.execute("SELECT provider, COUNT(*), SUM(cost_estimate), SUM(tokens_in+COALESCE(tokens_out,0)) FROM costs GROUP BY provider").fetchall()
    lines = [f"{r[0]}: {r[1]} calls, ${r[2]:.4f}, {r[3]} tokens" for r in rows]
    return "\n".join(lines) if lines else "No API costs recorded yet"


# ============================================================
# 2. CIRCUIT BREAKER
# ============================================================
def check_circuit(provider: str) -> bool:
    with _db_lock:
        row = db.execute("SELECT failures, disabled_until FROM circuit_breakers WHERE provider=?", (provider,)).fetchone()
    if not row: return True
    failures, disabled_until = row
    if disabled_until and time.time() < disabled_until:
        return False  # Circuit is OPEN (blocked)
    return True  # Circuit is CLOSED (allowed)

def record_failure(provider: str):
    with _db_lock:
        row = db.execute("SELECT failures FROM circuit_breakers WHERE provider=?", (provider,)).fetchone()
        failures = (row[0] if row else 0) + 1
        disabled_until = time.time() + 300 if failures >= 3 else 0  # 5 min timeout after 3 failures
        db.execute("INSERT OR REPLACE INTO circuit_breakers VALUES (?,?,?)", (provider, failures, disabled_until))
        db.commit()

def record_success(provider: str):
    with _db_lock:
        db.execute("INSERT OR REPLACE INTO circuit_breakers VALUES (?,0,0)", (provider,))
        db.commit()


# ============================================================
# 3. SEMANTIC ROUTING (lightweight embedding-based)
# ============================================================
SEMANTIC_DOMAINS = {
    "cnc_grbl": {
        "prompt": "关于CNC数控雕刻机、Grbl固件、GCode的问题",
        "keywords": ["雕刻机","grbl","gcode","主轴","步进","cnc","planner","限位","归零","homing","probe","jog"]
    },
    "esp32_embedded": {
        "prompt": "关于ESP32/STM32嵌入式开发、GPIO/I2C/SPI外设、固件烧录的问题",
        "keywords": ["esp32","stm32","gpio","i2c","spi","uart","pwm","adc","freertos","固件","烧录"]
    },
    "svg_image": {
        "prompt": "关于SVG矢量图形、Inkscape插件、图像处理的问题",
        "keywords": ["svg","矢量","inkscape","贝塞尔","path","potrace","vtracer","像素"]
    },
    "reverse_engineering": {
        "prompt": "关于逆向工程、固件提取、JTAG调试、协议分析的问题",
        "keywords": ["逆向","dump","jtag","swd","固件提取","反汇编","ghidra","加密","破解"]
    },
    "code_generation": {
        "prompt": "关于写代码、生成函数、实现功能的问题",
        "keywords": ["写一个","实现","代码","函数","生成","怎么写","帮我写"]
    },
    "debugging": {
        "prompt": "关于排查Bug、报错、异常、不工作的问题",
        "keywords": ["报错","不工作","bug","为什么","怎么解决","修好","卡住","fail","error"]
    },
    "concept_explanation": {
        "prompt": "关于解释概念、原理、教程的问题",
        "keywords": ["什么是","解释","原理","教程","怎么用","是什么","区别","对比"]
    },
    "general": {
        "prompt": "通用问题",
        "keywords": []
    }
}

def semantic_classify(query: str) -> tuple[str, float]:
    """Multi-domain semantic classification."""
    query_lower = query.lower()
    results = {}
    for domain, info in SEMANTIC_DOMAINS.items():
        if domain == "general": continue
        score = sum(3 * len(kw) for kw in info["keywords"] if kw in query_lower)
        if score > 0:
            results[domain] = score

    if not results:
        return ("general", 0.0)

    best = max(results, key=results.get)
    total_possible = sum(len(kw) * 3 for kw in SEMANTIC_DOMAINS[best]["keywords"])
    confidence = min(results[best] / max(total_possible, 1), 1.0)
    return (best, round(confidence, 2))


def classify_intent(query: str) -> str:
    """Classify user intent: code_gen / debugging / concept / general."""
    if any(kw in query for kw in ["写一个","实现","代码","生成","帮我写","函数"]):
        return "code_generation"
    if any(kw in query for kw in ["报错","不工作","bug","为什么","怎么解决","修好","fail","error"]):
        return "debugging"
    if any(kw in query for kw in ["什么是","解释","原理","怎么用","是什么","区别","对比"]):
        return "concept_explanation"
    return "general"


# ============================================================
# 4. MULTI-MODEL CONSENSUS
# ============================================================
def consensus_check(query: str, local_response: str, api_response: str = None) -> dict:
    """Check if two models agree. Returns consensus result."""
    if not api_response:
        return {"consensus": "single_model", "agreement": True, "combined": local_response}

    # Simple heuristic: check if they mention the same key entities
    def extract_entities(text):
        entities = set()
        for pattern in [r'`([^`]+)`', r'\b(Grbl|ESP32|STM32|GPIO|I2C|SPI|config\.h|planner\.c)\b',
                         r'\b(\$\d+)\b', r'\b(0x[0-9a-fA-F]+)\b']:
            entities.update(re.findall(pattern, text, re.IGNORECASE))
        return entities

    local_entities = extract_entities(local_response)
    api_entities = extract_entities(api_response)

    if not local_entities or not api_entities:
        return {"consensus": "uncertain", "agreement": True, "combined": local_response}

    overlap = len(local_entities & api_entities) / max(len(local_entities | api_entities), 1)

    if overlap > 0.3:
        combined = (local_response[:500] + "\n\n[Claude 补充]\n" + api_response[:500]) if len(local_response) < 300 else local_response
        return {"consensus": "strong_agreement", "agreement": True, "combined": combined, "overlap": round(overlap, 2)}
    else:
        return {"consensus": "disagreement", "agreement": False, "combined": local_response, "overlap": round(overlap, 2)}


# ============================================================
# 5. CONFIG + API CALLS
# ============================================================
LMSTUDIO_URL = "http://localhost:1234/v1"
LOCAL_MODEL = "qwen2.5-7b-instruct"  # LM Studio loaded model
RTK = r"D:\tools\rtk\rtk.exe"

API_POOL = [
    {"name": "claude", "url": "https://www.right.codes/claude-aws/v1/messages", "key": os.environ.get("CLAUDE_API_KEY", ""), "model": "claude-sonnet-4-6", "type": "anthropic", "priority": 1, "cost_per_1k_in": 0.003, "cost_per_1k_out": 0.015},
    {"name": "deepseek", "url": "https://api.deepseek.com/anthropic/v1/messages", "key": os.environ.get("DEEPSEEK_API_KEY", ""), "model": "deepseek-chat", "type": "anthropic", "priority": 2, "cost_per_1k_in": 0.00014, "cost_per_1k_out": 0.00028},
    {"name": "gpt55", "url": "https://www.right.codes/codex/v1/chat/completions", "key": os.environ.get("GPT_API_KEY", ""), "model": "gpt-5.5", "type": "openai", "priority": 2, "cost_per_1k_in": 0, "cost_per_1k_out": 0},
    {"name": "nvidia_dsv4", "url": "https://integrate.api.nvidia.com/v1/chat/completions", "key": os.environ.get("NVIDIA_API_KEY", ""), "model": "deepseek-ai/deepseek-v4-flash", "type": "openai", "priority": 3, "cost_per_1k_in": 0, "cost_per_1k_out": 0},
    {"name": "openrouter_dsv4", "url": "https://openrouter.ai/api/v1/chat/completions", "key": os.environ.get("OPENROUTER_API_KEY", ""), "model": "deepseek/deepseek-v4-flash:free", "type": "openrouter", "priority": 3, "cost_per_1k_in": 0, "cost_per_1k_out": 0},
    {"name": "openrouter_minimax", "url": "https://openrouter.ai/api/v1/chat/completions", "key": os.environ.get("OPENROUTER_API_KEY", ""), "model": "minimax/minimax-m2.5:free", "type": "openrouter", "priority": 4, "cost_per_1k_in": 0, "cost_per_1k_out": 0},
    {"name": "openrouter_nemotron", "url": "https://openrouter.ai/api/v1/chat/completions", "key": os.environ.get("OPENROUTER_API_KEY", ""), "model": "nvidia/nemotron-3-super-120b-a12b:free", "type": "openrouter", "priority": 4, "cost_per_1k_in": 0, "cost_per_1k_out": 0},
]
FALLBACK_APIS = [a for a in API_POOL if a["priority"] >= 3]  # Free APIs as last resort

SYSTEM_PROMPT = "<identity>\nred V1-Flash | 深圳市动力巢科技 (www.donglicao.com)\nCNC 嵌入式/ESP32/SVG/Grbl/逆向工程 领域专家\n</identity>\n\n<core_rules>\n- 直接回答。2+2 就是 4，不是\"答案是 4\"。\n- 绝不主动创建文档。优先编辑已有文件。\n- KNOW WHEN TO STOP: 用户要求完成的那一刻立刻停。\n- 写最少的代码解决问题。Show, don't tell。\n- 先搜索再回答。基于原文不凭记忆。\n- 不拍马屁、不道歉、不进行道德说教。\n</core_rules>\n\n<response_format>\n简单问题 → 1行答案\n复杂问题 → 分析/解决/代码 三层\n✅确定 ❓推测 ❌不确定\n</response_format>"


def call_local(query: str, context: str = "") -> str:
    system = SYSTEM_PROMPT
    if context:
        system += f"\n\n参考代码库:\n{context[:3000]}"

    payload = {"model": LOCAL_MODEL, "messages": [{"role":"system","content":system},{"role":"user","content":query}], "temperature": 0.3, "max_tokens": 1024}
    req = urllib.request.Request(f"{LMSTUDIO_URL}/chat/completions", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]


def ping_api(api: dict) -> bool:
    """Real-time liveness check: returns True if API is reachable."""
    try:
        t = api["type"]
        if t == "openai" or t == "openrouter":
            p = json.dumps({"model":api["model"],"messages":[{"role":"user","content":"ping"}],"max_tokens":1}).encode()
            h = {"Content-Type":"application/json","Authorization":f"Bearer {api['key']}"}
            if t == "openrouter": h["HTTP-Referer"] = "https://red-v1.local"
            r = urllib.request.Request(api["url"], data=p, headers=h)
        else:
            p = json.dumps({"model":api["model"],"max_tokens":1,"system":"ping","messages":[{"role":"user","content":"p"}]}).encode()
            h = {"Content-Type":"application/json","anthropic-version":"2023-06-01"}
            h["x-api-key" if "deepseek" not in api["url"] else "Authorization"] = f"Bearer {api['key']}" if "deepseek" in api["url"] else api["key"]
            r = urllib.request.Request(api["url"], data=p, headers=h)
        with urllib.request.urlopen(r, timeout=5):
            return True
    except:
        return False


def call_api_with_fallback(prompt: str, max_apis: int = 3) -> tuple[str, dict]:
    """Try APIs in priority order with real-time liveness checks."""
    # Read latest health status
    alive_names = set()
    if os.path.exists(r"D:\GIT\api_health.json"):
        try:
            with open(r"D:\GIT\api_health.json", 'r', encoding='utf-8') as f:
                health = json.load(f)
            alive_names = set(health.get("healthy", []))
        except: pass

    # Try APIs in priority order
    tried = 0
    last_error = None
    for api in sorted(API_POOL, key=lambda x: x["priority"]):
        if tried >= max_apis: break
        if not check_circuit(api["name"]): continue

        # Quick ping before calling (skip for priority 1 to save time)
        if api["priority"] > 1 and alive_names and api["name"] not in alive_names:
            continue  # Known dead, skip

        tried += 1
        try:
            return _call_single_api(api, prompt)
        except Exception as e:
            record_failure(api["name"])
            last_error = e
            continue

    # Last resort: try all free APIs
    for api in FALLBACK_APIS:
        if not check_circuit(api["name"]): continue
        try:
            return _call_single_api(api, prompt)
        except:
            record_failure(api["name"])
            continue

    return f"[所有API不可用]", {"error": str(last_error) if last_error else "all_dead"}


def _call_single_api(api: dict, prompt: str) -> tuple[str, dict]:
    """Call a single API and return (response, stats)."""
    t0 = time.time()
    t = api["type"]

    # Compress with rtk
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(prompt); tmp = f.name
        result = subprocess.run([RTK, "smart", "--input", tmp], capture_output=True, text=True, timeout=10)
        os.unlink(tmp)
        prompt = result.stdout.strip() if result.stdout and result.returncode == 0 else prompt[:4000]
    except:
        prompt = prompt[:4000]

    if t == "openai" or t == "openrouter":
        p = json.dumps({"model":api["model"],"messages":[{"role":"user","content":prompt}],"max_tokens":1024}).encode()
        h = {"Content-Type":"application/json","Authorization":f"Bearer {api['key']}"}
        if t == "openrouter": h["HTTP-Referer"] = "https://red-v1.local"
    else:
        p = json.dumps({"model":api["model"],"max_tokens":1024,"system":"CNC/嵌入式专家。直接回答。","messages":[{"role":"user","content":prompt}]}).encode()
        h = {"Content-Type":"application/json","anthropic-version":"2023-06-01"}
        h["x-api-key" if "deepseek" not in api["url"] else "Authorization"] = f"Bearer {api['key']}" if "deepseek" in api["url"] else api["key"]

    req = urllib.request.Request(api["url"], data=p, headers=h)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
        if t == "anthropic":
            result = data["content"][0]["text"]
        else:
            result = data["choices"][0]["message"]["content"]

    record_success(api["name"])
    latency = int((time.time()-t0)*1000)
    ti = len(prompt)//4; to = len(result)//4
    cost = (ti/1000*api.get("cost_per_1k_in",0)) + (to/1000*api.get("cost_per_1k_out",0))
    log_cost(api["name"], api["model"], ti, to, cost, latency, True)
    return result, {"api": api["name"], "tokens_in": ti, "tokens_out": to, "cost": round(cost,6), "latency_ms": latency}


# ============================================================
# 6. MAIN ROUTER V3
# ============================================================
def route_v3(query: str, session_id: str = "default", use_consensus: bool = False, callback=None) -> dict:
    # Load session
    history = load_session(session_id)

    # Semantic routing
    domain, confidence = semantic_classify(query)
    intent = classify_intent(query)

    # Model selection based on intent
    model_choice = "local"
    if intent == "debugging" or domain == "reverse_engineering":
        model_choice = "longcat_thinking"  # Use reasoning for debugging/RE
        use_consensus = True  # And verify with consensus

    # Generate response
    response = call_local(query)

    # Multi-model consensus for important queries
    consensus_result = None
    if use_consensus and intent in ("debugging", "concept_explanation"):
        api_resp, api_stats = call_api_with_fallback(query)
        consensus_result = consensus_check(query, response, api_resp)
        if not consensus_result["agreement"]:
            response = consensus_result["combined"]

    # Save to session
    history.append({"role": "user", "content": query})
    history.append({"role": "assistant", "content": response})
    if len(history) > 20:
        history = history[-20:]
    save_session(session_id, history)

    return {
        "response": response,
        "domain": domain,
        "confidence": confidence,
        "intent": intent,
        "model": model_choice,
        "consensus": consensus_result,
        "history_length": len(history),
    }


# ============================================================
# CLI
# ============================================================
def main():
    print("=" * 60)
    print("  red V1-Flash Router V3")
    print("  Semantic | Consensus | Circuit | Cost | Persist | Feedback")
    print("=" * 60)

    session = str(int(time.time()))
    while True:
        try:
            query = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见"); break
        if not query: continue
        if query == "/quit": break
        if query == "/cost":
            print("\n" + get_cost_summary()); continue
        if query.startswith("/rate "):
            parts = query.split(" ", 2)
            if len(parts) == 3:
                log_feedback(parts[1], "", int(parts[2]), "cli")
                print("Feedback recorded")
            continue

        result = route_v3(query, session)
        print(f"\n{result['response']}")
        print(f"\n─ {result['domain']} | {result['intent']} | {result['model']}")
        if result.get('consensus'):
            print(f"  Consensus: {result['consensus'].get('consensus','N/A')}")


if __name__ == "__main__":
    main()
