"""Deploy and run r8.py verification test on production server."""
import paramiko
import os
from scripts.deploy_common import configure_ssh_host_keys
import sys

SERVER = "47.112.162.80"
USER = "root"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

SCRIPT = r'''
import http.client
import json
import time

API_HOST = "localhost"
API_PORT = 8080
API_PATH = "/v1/chat/completions"
TIMEOUT = 25

CODE_KEYWORDS = ["def ", "function ", "class ", "import ", "const "]

TESTS = [
    ("what is the capital of Japan", False),
    ("translate hello to French", False),
    ("what is 15 times 23", False),
    ("who painted the Mona Lisa", False),
    ("write a python fibonacci with type hints", True),
    ("implement a JavaScript debounce function", True),
]

def run_test(query, expect_code):
    body = json.dumps({
        "model": "lima",
        "messages": [{"role": "user", "content": query}],
        "stream": True
    })
    headers = {"Content-Type": "application/json"}
    start = time.time()
    try:
        conn = http.client.HTTPConnection(API_HOST, API_PORT, timeout=TIMEOUT)
        conn.request("POST", API_PATH, body=body, headers=headers)
        resp = conn.getresponse()
        full_text = ""
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload == "[DONE]":
                break
            try:
                obj = json.loads(payload)
                delta = obj.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    full_text += content
            except (json.JSONDecodeError, IndexError, KeyError):
                pass
        conn.close()
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        return {"query": query[:40], "latency_ms": latency, "error": str(e), "passed": False}

    latency = int((time.time() - start) * 1000)
    has_code = any(kw in full_text for kw in CODE_KEYWORDS)
    if expect_code:
        passed = has_code
    else:
        passed = not has_code
    return {
        "query": query[:40],
        "latency_ms": latency,
        "has_code": has_code,
        "expect_code": expect_code,
        "first100": full_text[:100].replace("\n", " "),
        "passed": passed,
    }

print("=" * 70)
print("R8 VERIFICATION: chat_only backend whitelist fix")
print("=" * 70)
results = []
for i, (q, expect) in enumerate(TESTS, 1):
    tag = "CODING" if expect else "NON-CODE"
    print("\n[Test %d/%d] (%s) %s" % (i, len(TESTS), tag, q[:50]))
    r = run_test(q, expect)
    results.append(r)
    if "error" in r:
        print("  ERROR: %s (%dms)" % (r["error"], r["latency_ms"]))
    else:
        status = "PASS" if r["passed"] else "FAIL"
        print("  %s | %dms | code_kw=%s | %s" % (status, r["latency_ms"], r["has_code"], r["first100"]))

print("\n" + "=" * 70)
all_passed = all(r["passed"] for r in results)
pass_count = sum(1 for r in results if r["passed"])
print("RESULT: %d/%d passed" % (pass_count, len(results)))
if all_passed:
    print("VERDICT: ALL PASS - chat_only whitelist fix VERIFIED")
else:
    print("VERDICT: SOME FAILED - needs investigation")
    for r in results:
        if not r["passed"]:
            print("  FAILED: %s" % r["query"])
print("=" * 70)
'''

def main():
    print("Connecting to %s..." % SERVER)
    client = paramiko.SSHClient()
    configure_ssh_host_keys(client)
    client.connect(SERVER, username=USER, key_filename=KEY, timeout=10)
    print("Connected. Uploading /tmp/r8.py...")

    sftp = client.open_sftp()
    with sftp.open("/tmp/r8.py", "w") as f:
        f.write(SCRIPT)
    sftp.close()
    print("Uploaded. Executing...")

    stdin, stdout, stderr = client.exec_command("python3 /tmp/r8.py", timeout=180)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("STDERR:", err)
    client.close()

if __name__ == "__main__":
    main()
