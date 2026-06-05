#!/usr/bin/env python3
"""Key Rotation Daemon for LiMa Router
- Scrapes free API keys from GitHub repos
- Validates keys periodically
- Provides valid key via simple HTTP API for smart_router.py
- Auto check-in for FreeTheAI daily
"""

import urllib.request, json, re, time, sys, threading, os
import http.server
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GITHUB_RAW = "https://raw.githubusercontent.com/alistaitsacle/free-llm-api-keys/main/README.md"
PEKPIK_BASE = "https://aiapiv2.pekpik.com/v1"
FREETHEAI_BASE = "https://api.freetheai.xyz/v1"
FREETHEAI_KEY = os.environ.get("FREETHEAI_KEY", "")
STATE_FILE = "/opt/lima-router/key_pool.json"
PROXY_URL = os.environ.get("PROXY_URL", "http://127.0.0.1:7897")
LISTEN_PORT = 8909

_lock = threading.Lock()

state = {
    "pekpik_keys": [],
    "pekpik_valid": [],
    "pekpik_current": "",
    "freetheai_checked_in": False,
    "freetheai_checkin_date": "",
    "last_scrape": "",
    "last_validate": "",
}


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def get_proxy_opener():
    handler = urllib.request.ProxyHandler({"https": PROXY_URL, "http": PROXY_URL})
    return urllib.request.build_opener(handler)


def save_state():
    tmp = STATE_FILE + ".tmp"
    with _lock:
        with open(tmp, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, STATE_FILE)


def load_state():
    global state
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f:
                state.update(json.load(f))
    except (json.JSONDecodeError, ValueError):
        pass


def scrape_keys():
    log("Scraping keys from GitHub...")
    try:
        opener = get_proxy_opener()
        req = urllib.request.Request(GITHUB_RAW)
        resp = opener.open(req, timeout=15)
        content = resp.read().decode("utf-8", errors="replace")
        keys = list(set(re.findall(r"sk-[a-zA-Z0-9]{30,80}", content)))
        log(f"  Found {len(keys)} unique keys")
        state["pekpik_keys"] = keys
        state["last_scrape"] = datetime.now(timezone.utc).isoformat()
        save_state()
    except Exception as e:
        log(f"  Scrape failed: {e}")


def validate_key(key, model="deepseek-chat"):
    try:
        data = json.dumps({"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}).encode()
        req = urllib.request.Request(
            f"{PEKPIK_BASE}/chat/completions",
            data=data,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        )
        resp = urllib.request.urlopen(req, timeout=10)
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if "无权访问" in body:
            return False
        if "额度" in body or "quota" in body.lower():
            return False
        return False
    except Exception:
        return False


def validate_all():
    log("Validating keys...")
    valid = []
    for key in state["pekpik_keys"]:
        if validate_key(key):
            valid.append(key)
            log(f"  VALID: {key[:20]}...")
        time.sleep(1)
    state["pekpik_valid"] = valid
    if valid and not state["pekpik_current"]:
        state["pekpik_current"] = valid[0]
    state["last_validate"] = datetime.now(timezone.utc).isoformat()
    log(f"  Result: {len(valid)}/{len(state['pekpik_keys'])} valid")
    save_state()


def rotate_key():
    """Switch to next valid key when current fails"""
    valid = state["pekpik_valid"]
    if not valid:
        return ""
    current = state["pekpik_current"]
    if current in valid:
        idx = (valid.index(current) + 1) % len(valid)
    else:
        idx = 0
    state["pekpik_current"] = valid[idx]
    save_state()
    log(f"  Rotated to: {valid[idx][:20]}...")
    return valid[idx]


def freetheai_checkin():
    """Daily check-in for FreeTheAI"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state["freetheai_checkin_date"] == today:
        return
    log("FreeTheAI check-in...")
    try:
        opener = get_proxy_opener()
        req = urllib.request.Request(
            f"{FREETHEAI_BASE}/chat/completions",
            data=json.dumps(
                {"model": "bbl/gpt-4.1", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
            ).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {FREETHEAI_KEY}"},
        )
        resp = opener.open(req, timeout=15)
        state["freetheai_checked_in"] = True
        state["freetheai_checkin_date"] = today
        log("  Check-in OK")
    except Exception as e:
        log(f"  Check-in failed: {e}")
        state["freetheai_checked_in"] = False
    save_state()


class APIHandler(http.server.BaseHTTPRequestHandler):
    """HTTP API for smart_router.py to query valid keys"""

    def do_GET(self):
        if self.path == "/pekpik/key":
            key = state["pekpik_current"] or ""
            body = json.dumps({"key": key, "valid_count": len(state["pekpik_valid"])}).encode()
        elif self.path == "/pekpik/rotate":
            key = rotate_key()
            body = json.dumps({"key": key}).encode()
        elif self.path == "/freetheai/status":
            body = json.dumps(
                {
                    "key": FREETHEAI_KEY,
                    "checked_in": state["freetheai_checked_in"],
                    "date": state["freetheai_checkin_date"],
                }
            ).encode()
        elif self.path == "/status":
            body = json.dumps(state, indent=2).encode()
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def run_api():
    srv = http.server.HTTPServer(("127.0.0.1", LISTEN_PORT), APIHandler)
    srv.serve_forever()


def main():
    load_state()
    log(f"Key Rotation Daemon starting on :{LISTEN_PORT}")
    threading.Thread(target=run_api, daemon=True).start()
    log("API server ready")
    scrape_keys()
    validate_all()
    freetheai_checkin()
    while True:
        time.sleep(1800)
        scrape_keys()
        validate_all()
        freetheai_checkin()


if __name__ == "__main__":
    main()
