#!/usr/bin/env python3
import os
"""Test one-api end-to-end from cloud server"""
import urllib.request, json, sys, time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:3001/v1"
TOKEN = os.environ.get("ONEAPI_ACCESS_TOKEN", "")

body = json.dumps({
    "model": "glm-4-flash",
    "messages": [{"role": "user", "content": "say hi in 3 words"}],
    "max_tokens": 20
}).encode()

req = urllib.request.Request(
    BASE + "/chat/completions",
    data=body,
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + TOKEN,
    }
)

t0 = time.time()
try:
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read().decode())
    ms = int((time.time() - t0) * 1000)
    content = data["choices"][0]["message"]["content"]
    model = data.get("model", "?")
    print("OK " + str(ms) + "ms [" + model + "]: " + content[:80])
except urllib.error.HTTPError as e:
    body_err = e.read().decode("utf-8", errors="replace")[:200]
    print("HTTP " + str(e.code) + ": " + body_err)
except Exception as e:
    ms = int((time.time() - t0) * 1000)
    print("FAIL " + str(ms) + "ms: " + str(e)[:100])
