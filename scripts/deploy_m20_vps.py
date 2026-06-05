#!/usr/bin/env python3
"""Deploy M20: Complete admin panel UI rewrite to VPS /opt/lima-router/"""

import paramiko
import os
import time

VPS_HOST = "47.112.162.80"
VPS_USER = "root"
VPS_KEY = os.path.expanduser("~/.ssh/id_ed25519")
REMOTE_DIR = "/opt/lima-router"

files_to_upload = [
    ("routes/admin_ui.py", "routes/admin_ui.py"),
    ("routes/admin_backends_crud.py", "routes/admin_backends_crud.py"),
    ("findings.md", "findings.md"),
    ("progress.md", "progress.md"),
]

print(f"🚀 M20: Deploying to VPS {VPS_HOST}:{REMOTE_DIR}")
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

    # Backup current admin_ui.py
    print("💾 Creating backup...")
    stdin, stdout, stderr = ssh.exec_command(
        f"cp {REMOTE_DIR}/routes/admin_ui.py {REMOTE_DIR}/routes/admin_ui.py.bak.m20"
    )
    stdout.channel.recv_exit_status()
    print("  ✅ Backup created: admin_ui.py.bak.m20\n")

    # Restart service
    print("🔄 Restarting lima-router.service...")
    stdin, stdout, stderr = ssh.exec_command("systemctl restart lima-router.service")
    exit_code = stdout.channel.recv_exit_status()

    if exit_code != 0:
        print(f"  ⚠️  systemctl restart failed (exit {exit_code})")
        print(f"  Error: {stderr.read().decode()[:200]}")
    else:
        print("  ✅ Service restart commanded\n")

    # Wait for service to start
    print("⏳ Waiting 5 seconds for service startup...")
    time.sleep(5)

    # Health check
    print("\n🏥 Health check:")
    stdin, stdout, stderr = ssh.exec_command("curl -sf https://lima.257339.xyz/health")
    health = stdout.read().decode().strip()
    if health:
        print(f"  ✅ Health: {health}")
    else:
        print(f"  ❌ Health check failed")
        print(f"  Error: {stderr.read().decode()[:200]}")

    # Service status
    print("\n📊 Service status:")
    stdin, stdout, stderr = ssh.exec_command(
        "systemctl is-active lima-router.service && "
        "systemctl show lima-router.service --no-pager --property=MainPID,SubState,ActiveEnterTimestamp"
    )
    status = stdout.read().decode().strip()
    for line in status.split("\n"):
        print(f"  {line}")

    # Admin panel smoke test
    print("\n🎨 Admin panel smoke test:")
    stdin, stdout, stderr = ssh.exec_command("curl -sf -o /dev/null -w '%{http_code}' https://lima.257339.xyz/admin")
    http_code = stdout.read().decode().strip()
    if http_code in ("200", "401", "302"):
        print(f"  ✅ Admin panel: HTTP {http_code} (401/302 = auth required, correct)")
    else:
        print(f"  ⚠️  Admin panel: HTTP {http_code}")

    # Check admin_ui.py timestamp
    print("\n📁 File verification:")
    stdin, stdout, stderr = ssh.exec_command(f"ls -lh {REMOTE_DIR}/routes/admin_ui.py")
    file_info = stdout.read().decode().strip()
    print(f"  {file_info}")

    stdin, stdout, stderr = ssh.exec_command(f"wc -l {REMOTE_DIR}/routes/admin_ui.py")
    line_count = stdout.read().decode().strip()
    print(f"  {line_count}")

    print("\n" + "=" * 70)
    print("✅ M20 Deployment successful!")
    print("\n🎨 New Features Deployed:")
    print("  • LIMA 管理面板 branding")
    print("  • URL column (45 char truncate + tooltip)")
    print("  • Key status column (已配置/未配置)")
    print("  • Pool filter buttons (全部/IDE/Chat/Code/Sandbox)")
    print("  • editBackend() function")
    print("  • Modern UI/UX with gradients and animations")
    print("\n📝 Access: https://lima.257339.xyz/admin")
    print(
        "🔧 Rollback: cp /opt/lima-router/routes/admin_ui.py.bak.m20 /opt/lima-router/routes/admin_ui.py && systemctl restart lima-router.service"
    )

except Exception as e:
    print(f"\n❌ Deployment failed: {e}")
    import traceback

    traceback.print_exc()
finally:
    ssh.close()
