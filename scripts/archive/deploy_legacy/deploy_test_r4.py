"""Deploy and run /tmp/r4.py on production server to verify chat_fast pool fix."""
import paramiko
import os
from scripts.deploy_common import configure_ssh_host_keys
import textwrap

SERVER = "47.112.162.80"
USER = "root"
KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))

SCRIPT = textwrap.dedent(r'''
import urllib.request
import json
import time
import sys

API = "http://localhost:8080/v1/chat/completions"
TESTS = [
    {"query": "what is the capital of Japan", "expect_code": False},
    {"query": "translate hello to French", "expect_code": False},
    {"query": "write a python fibonacci", "expect_code": True},
]
CODE_KEYWORDS = ["def ", "function ", "class ", "import ", "const ", "```"]

def run_test(query, expect_code):
    payload = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": query}],
        "stream": True
    }).encode()
    req = urllib.request.Request(API, data=payload,
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=20)
    except Exception as e:
        return {"query": query, "error": str(e), "verdict": "ERROR"}
    chunks = []
    for line in resp:
        line = line.decode("utf-8", errors="replace").strip()
        if not line.startswith("data: "):
            continue
        data = line[6:]
        if data == "[DONE]":
            break
        try:
            obj = json.loads(data)
            delta = obj.get("choices", [{}])[0].get("delta", {})
            c = delta.get("content", "")
            if c:
                chunks.append(c)
        except json.JSONDecodeError:
            pass
    latency = int((time.time() - t0) * 1000)
    text = "".join(chunks)
    has_code = any(kw in text for kw in CODE_KEYWORDS)
    if expect_code:
        verdict = "PASS" if has_code else "FAIL"
    else:
        verdict = "PASS" if not has_code else "FAIL"
    return {
        "query": query,
        "latency_ms": latency,
        "has_code": has_code,
        "first_100": text[:100].replace("\n", " "),
        "verdict": verdict,
    }

print("=" * 60)
print("Chat-fast pool verification test")
print("=" * 60)
all_pass = True
for t in TESTS:
    r = run_test(t["query"], t["expect_code"])
    print(f"\nQuery: {r['query']}")
    if "error" in r:
        print(f"  ERROR: {r['error']}")
        all_pass = False
    else:
        print(f"  Latency: {r['latency_ms']}ms")
        print(f"  Has code: {r['has_code']}")
        print(f"  Content: {r['first_100']}")
        print(f"  Verdict: {r['verdict']}")
        if r["verdict"] != "PASS":
            all_pass = False
print("\n" + "=" * 60)
print(f"OVERALL: {'ALL PASS' if all_pass else 'SOME FAILED'}")
print("=" * 60)
''')

def main():
    ssh = paramiko.SSHClient()
    configure_ssh_host_keys(ssh)
    print(f"Connecting to {SERVER}...")
    ssh.connect(SERVER, username=USER, key_filename=KEY, timeout=10)
    print("Connected. Uploading /tmp/r4.py...")

    sftp = ssh.open_sftp()
    with sftp.file("/tmp/r4.py", "w") as f:
        f.write(SCRIPT)
    sftp.close()
    print("Uploaded. Running test...")

    stdin, stdout, stderr = ssh.exec_command("python3 /tmp/r4.py", timeout=60)
    out = stdout.read().decode()
    err = stderr.read().decode()
    print(out)
    if err:
        print("STDERR:", err)
    ssh.close()

if __name__ == "__main__":
    main()
