#!/usr/bin/env python3
"""Deploy M22-M26: Admin panel enhancements (health, fallback, batch, keys, latency)."""
import paramiko
import os
import time

VPS_HOST = "47.112.162.80"
VPS_USER = "root"
VPS_KEY = os.path.expanduser("~/.ssh/id_ed25519")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

key = paramiko.Ed25519Key.from_private_key_file(VPS_KEY)
ssh = paramiko.SSHClient()
known_hosts = os.path.expanduser("~/.ssh/known_hosts")
if os.path.exists(known_hosts):
    try:
        ssh.load_host_keys(known_hosts)
    except Exception:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
else:
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(VPS_HOST, username=VPS_USER, pkey=key, timeout=20)
    print("=" * 70)
    print("M22-M26 Deploy: Admin Panel Enhancements")
    print("=" * 70)

    # Step 1: Backup
    print("\n[1/5] Backup...")
    cmds = [
        "cp /opt/lima-router/routes/admin_api.py /opt/lima-router/routes/admin_api.py.bak.m22",
        "cp /opt/lima-router/routes/admin_ui.py /opt/lima-router/routes/admin_ui.py.bak.m22",
    ]
    for cmd in cmds:
        ssh.exec_command(cmd)
        time.sleep(0.3)
    print("   Backed up 2 files")

    # Step 2: Upload files
    print("\n[2/5] Upload admin_api.py and admin_ui.py...")
    sftp = ssh.open_sftp()
    files = [
        (os.path.join(REPO, "routes", "admin_api.py"), "/opt/lima-router/routes/admin_api.py"),
        (os.path.join(REPO, "routes", "admin_ui.py"), "/opt/lima-router/routes/admin_ui.py"),
    ]
    for local, remote in files:
        sftp.put(local, remote)
        print(f"   Uploaded {os.path.basename(local)}")
    sftp.close()

    # Step 3: Restart LiMa service
    print("\n[3/5] Restart LiMa service...")
    ssh.exec_command("systemctl restart lima-router")
    time.sleep(4)
    _, out, _ = ssh.exec_command("systemctl is-active lima-router")
    status = out.read().decode().strip()
    print(f"   Service status: {status}")
    if status != "active":
        _, out, _ = ssh.exec_command("journalctl -u lima-router --no-pager -n 20 2>&1")
        print(f"   Recent logs:\n{out.read().decode()[:500]}")

    # Step 4: Health check
    print("\n[4/5] Health check...")
    _, out, _ = ssh.exec_command("curl -s http://127.0.0.1:8080/health 2>&1 | head -5")
    health = out.read().decode().strip()
    print(f"   /health: {health[:200]}")

    # Step 5: Smoke tests - new API endpoints
    print("\n[5/5] Smoke test new API endpoints...")
    _, out, _ = ssh.exec_command("grep LIMA_ADMIN_TOKEN /opt/lima-router/.env | cut -d= -f2")
    token = out.read().decode().strip()

    py_cookie = f"import hmac,hashlib; print(hmac.new('{token}'.encode(), b'lima-admin-session', hashlib.sha256).hexdigest())"
    _, out, _ = ssh.exec_command(f'python3 -c "{py_cookie}"')
    cookie = out.read().decode().strip()

    endpoints = [
        ("GET", "/admin/api/backend-health", "M22: Health Dashboard"),
        ("GET", "/admin/api/fallback-analysis", "M23: Fallback Analysis"),
        ("GET", "/admin/api/retrain/jobs", "M24: Retrain Jobs"),
        ("GET", "/admin/api/key-url-inventory", "M25: Key/URL Inventory"),
        ("GET", "/admin/api/stats", "M26: Stats (with version)"),
    ]

    all_pass = True
    for method, url, label in endpoints:
        cmd = f'curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:8080{url} -b "lima_admin_session={cookie}"'
        _, out, _ = ssh.exec_command(cmd, timeout=15)
        code = out.read().decode().strip()
        ok = code == "200"
        if not ok:
            all_pass = False
        print(f"   {label}: HTTP {code} {'PASS' if ok else 'FAIL'}")

    # Test admin page loads
    cmd = f'curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:8080/admin -b "lima_admin_session={cookie}"'
    _, out, _ = ssh.exec_command(cmd, timeout=15)
    code = out.read().decode().strip()
    ok = code == "200"
    if not ok:
        all_pass = False
    print(f"   Admin page: HTTP {code} {'PASS' if ok else 'FAIL'}")

    # Verify version info in stats
    cmd = f'curl -s http://127.0.0.1:8080/admin/api/stats -b "lima_admin_session={cookie}"'
    _, out, _ = ssh.exec_command(cmd, timeout=15)
    stats_body = out.read().decode().strip()
    if "version" in stats_body and "git_commit" in stats_body:
        print("   Version info in stats: PASS")
    else:
        print("   Version info in stats: FAIL")
        all_pass = False

    print("\n" + "=" * 70)
    print(f"M22-M26 Deploy complete! All smoke tests: {'PASS' if all_pass else 'SOME FAILED'}")
    print("Changes:")
    print("  M22: Backend health dashboard (health_tracker + circuit_breaker)")
    print("  M23: Fallback root cause analysis (by backend, intent, hourly)")
    print("  M24: Batch ops + log export + retrain progress")
    print("  M25: Key/URL management panel (masked keys + key pool)")
    print("  M26: Retrieval P50/P95 stats + version/deploy info")
    print("=" * 70)

finally:
    ssh.close()
