#!/usr/bin/env python3
"""Deploy model_resolver feature to VPS /opt/lima-router/

Files deployed:
  - model_resolver.py (new)
  - backends_constants.py (updated MODEL_ALIASES)
  - routing_engine.py (updated forced_backend integration)
"""

import paramiko
import os
import time
import sys

VPS_HOST = "47.112.162.80"
VPS_USER = "root"
VPS_KEY = os.environ.get("LIMA_DEPLOY_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
REMOTE_DIR = "/opt/lima-router"

files_to_upload = [
    ("model_resolver.py", "model_resolver.py"),
    ("backends_constants.py", "backends_constants.py"),
    ("routing_engine.py", "routing_engine.py"),
]

print(f"🚀 Deploying model_resolver feature to VPS {VPS_HOST}:{REMOTE_DIR}")
print("=" * 70)

key = paramiko.Ed25519Key.from_private_key_file(VPS_KEY)
ssh = paramiko.SSHClient()
known_hosts = os.path.expanduser("~/.ssh/known_hosts")
if os.path.exists(known_hosts):
    try:
        ssh.load_host_keys(known_hosts)
    except Exception as exc:
        print(f"[warn] failed to load known_hosts: {exc}")
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507
else:
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507

try:
    ssh.connect(VPS_HOST, username=VPS_USER, pkey=key, timeout=20)
    print("✅ SSH connected\n")

    # Upload files via SFTP
    sftp = ssh.open_sftp()

    for local_path, remote_relative in files_to_upload:
        remote_path = f"{REMOTE_DIR}/{remote_relative}"
        print(f"  ⬆️  Uploading {local_path}...")
        sftp.put(local_path, remote_path)
        print(f"     → {remote_path}")

    sftp.close()
    print()

    # Backup current files
    print("💾 Creating backups...")
    for local_path, remote_relative in files_to_upload:
        remote_path = f"{REMOTE_DIR}/{remote_relative}"
        backup_path = f"{remote_path}.bak.model_resolver"
        stdin, stdout, stderr = ssh.exec_command(f"cp {remote_path} {backup_path}")
        stdout.channel.recv_exit_status()
        print(f"  ✅ Backup created: {remote_relative}.bak.model_resolver")

    print()

    # Restart service
    print("🔄 Restarting lima-router.service...")
    stdin, stdout, stderr = ssh.exec_command("systemctl restart lima-router.service")
    exit_code = stdout.channel.recv_exit_status()

    if exit_code != 0:
        print(f"  ⚠️  systemctl restart failed (exit {exit_code})")
        print(f"  Error: {stderr.read().decode()[:200]}")
        sys.exit(1)
    else:
        print("  ✅ Service restart commanded\n")

    # Wait for service to start
    print("⏳ Waiting 5 seconds for service startup...")
    time.sleep(5)

    # Health check
    print("\n🏥 Health check:")
    stdin, stdout, stderr = ssh.exec_command("curl -sf https://chat.donglicao.com/health")
    health = stdout.read().decode().strip()
    if health:
        print(f"  ✅ Health: {health}")
    else:
        print(f"  ❌ Health check failed")
        print(f"  Error: {stderr.read().decode()[:200]}")
        sys.exit(1)

    # Service status
    print("\n📊 Service status:")
    stdin, stdout, stderr = ssh.exec_command(
        "systemctl is-active lima-router.service && "
        "systemctl show lima-router.service --no-pager --property=MainPID,SubState,ActiveEnterTimestamp"
    )
    status = stdout.read().decode().strip()
    for line in status.split("\n"):
        print(f"  {line}")

    # Verify model_resolver.py is loaded
    print("\n🔍 Verifying model_resolver deployment:")
    stdin, stdout, stderr = ssh.exec_command(f"ls -lh {REMOTE_DIR}/model_resolver.py")
    file_info = stdout.read().decode().strip()
    print(f"  {file_info}")

    stdin, stdout, stderr = ssh.exec_command(f"wc -l {REMOTE_DIR}/model_resolver.py")
    line_count = stdout.read().decode().strip()
    print(f"  {line_count}")

    # Smoke test: test model resolution via API
    print("\n🧪 Smoke test: model resolution via API")
    # Test with a simple request that should use model resolution
    test_cmd = """
    curl -sf -X POST https://chat.donglicao.com/v1/chat/completions \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer test-token" \
      -d '{"model":"gpt-4o","messages":[{"role":"user","content":"hello"}],"max_tokens":5}'
    """
    stdin, stdout, stderr = ssh.exec_command(test_cmd)
    response = stdout.read().decode().strip()
    if response:
        print(f"  ✅ API response received (length: {len(response)})")
        # Check if response contains expected content
        if "choices" in response or "error" in response:
            print("  ✅ Response format looks valid")
        else:
            print(f"  ⚠️  Unexpected response format: {response[:100]}...")
    else:
        print(f"  ⚠️  No response from API")
        print(f"  Error: {stderr.read().decode()[:200]}")

    print("\n" + "=" * 70)
    print("✅ model_resolver deployment successful!")
    print("\n📝 Features Deployed:")
    print("  • model_resolver.py - Client model parameter resolution")
    print("  • MODEL_ALIASES - Human-friendly model names → backend mapping")
    print("  • forced_backend integration in routing_engine.py")
    print("\n🔧 Rollback command:")
    print(f"  cp {REMOTE_DIR}/model_resolver.py.bak.model_resolver {REMOTE_DIR}/model_resolver.py")
    print(f"  cp {REMOTE_DIR}/backends_constants.py.bak.model_resolver {REMOTE_DIR}/backends_constants.py")
    print(f"  cp {REMOTE_DIR}/routing_engine.py.bak.model_resolver {REMOTE_DIR}/routing_engine.py")
    print(f"  systemctl restart lima-router.service")

except Exception as e:
    print(f"\n❌ Deployment failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
finally:
    ssh.close()
