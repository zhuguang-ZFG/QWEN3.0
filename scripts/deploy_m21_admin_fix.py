#!/usr/bin/env python3
"""Deploy M21: Admin panel CSRF fix + JS button fix + Nginx Origin/Referer forwarding"""

import paramiko, os, time

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
    except Exception as exc:
        print(f"[warn] failed to load known_hosts: {exc}")
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507
else:
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507

try:
    ssh.connect(VPS_HOST, username=VPS_USER, pkey=key, timeout=20)
    print("=" * 70)
    print("M21 Deploy: Admin Panel CSRF + JS Button Fix")
    print("=" * 70)

    # Step 1: Backup
    print("\n[1/7] Backup...")
    cmds = [
        "cp /opt/lima-router/routes/admin_auth.py /opt/lima-router/routes/admin_auth.py.bak",
        "cp /opt/lima-router/routes/admin_ui.py /opt/lima-router/routes/admin_ui.py.bak",
        "cp /etc/nginx/conf.d/chat.donglicao.com.conf /etc/nginx/conf.d/chat.donglicao.com.conf.bak.m21",
    ]
    for cmd in cmds:
        ssh.exec_command(cmd)
        time.sleep(0.3)
    print("   Backed up 3 files")

    # Step 2: Upload fixed Python files
    print("\n[2/7] Upload admin_auth.py and admin_ui.py...")
    sftp = ssh.open_sftp()
    files = [
        (os.path.join(REPO, "routes", "admin_auth.py"), "/opt/lima-router/routes/admin_auth.py"),
        (os.path.join(REPO, "routes", "admin_ui.py"), "/opt/lima-router/routes/admin_ui.py"),
    ]
    for local, remote in files:
        sftp.put(local, remote)
        print(f"   Uploaded {os.path.basename(local)}")
    sftp.close()

    # Step 3: Fix Nginx config - add Origin/Referer forwarding
    print("\n[3/7] Fix Nginx config (add Origin/Referer forwarding)...")
    # Use sed to add proxy_set_header Origin and Referer after X-Forwarded-Proto in admin blocks
    sed_cmds = [
        # Add Origin header after X-Forwarded-Proto in admin location blocks
        r"""sed -i '/location.*\/admin/,/^[[:space:]]*}/ { /proxy_set_header X-Forwarded-Proto \$scheme;/{/Origin/!a\          proxy_set_header Origin \$http_origin; } }' /etc/nginx/conf.d/chat.donglicao.com.conf""",
        r"""sed -i '/location.*\/admin/,/^[[:space:]]*}/ { /proxy_set_header Origin \$http_origin;/{/Referer/!a\          proxy_set_header Referer \$http_referer; } }' /etc/nginx/conf.d/chat.donglicao.com.conf""",
    ]
    for cmd in sed_cmds:
        _, out, err = ssh.exec_command(cmd)
        out.read()
        e = err.read().decode().strip()
        if e:
            print(f"   sed warning: {e}")

    # Verify the fix was applied
    _, out, _ = ssh.exec_command("grep -A10 'location = /admin' /etc/nginx/conf.d/chat.donglicao.com.conf")
    admin_block = out.read().decode()
    print("   Admin proxy block now:")
    for line in admin_block.split("\n")[:12]:
        print(f"     {line}")

    if "Origin" in admin_block and "Referer" in admin_block:
        print("   Origin/Referer forwarding: OK")
    else:
        print("   WARNING: Origin/Referer not found, trying Python-based fix...")
        _, out, _ = ssh.exec_command("cat /etc/nginx/conf.d/chat.donglicao.com.conf")
        config = out.read().decode()
        # Direct string replacement
        old1 = "proxy_set_header X-Forwarded-Proto $scheme;\n          proxy_buffering off;"
        new1 = "proxy_set_header X-Forwarded-Proto $scheme;\n          proxy_set_header Origin $http_origin;\n          proxy_set_header Referer $http_referer;\n          proxy_buffering off;"
        if old1 in config:
            config = config.replace(old1, new1)
            sftp = ssh.open_sftp()
            with sftp.file("/etc/nginx/conf.d/chat.donglicao.com.conf", "w") as f:
                f.write(config)
            sftp.close()
            print("   Python-based fix applied")
        else:
            print("   Could not apply fix automatically - manual intervention needed")

    # Step 4: Test and reload Nginx
    print("\n[4/7] Test Nginx config...")
    _, out, err = ssh.exec_command("nginx -t 2>&1")
    result = out.read().decode().strip() + err.read().decode().strip()
    print(f"   {result}")
    if "syntax is ok" in result and "test is successful" in result:
        ssh.exec_command("systemctl reload nginx")
        print("   Nginx reloaded")
    else:
        print("   FAILED - rolling back Nginx config")
        ssh.exec_command(
            "cp /etc/nginx/conf.d/chat.donglicao.com.conf.bak.m21 /etc/nginx/conf.d/chat.donglicao.com.conf"
        )
        ssh.exec_command("nginx -t 2>&1 && systemctl reload nginx")

    # Step 5: Restart LiMa service
    print("\n[5/7] Restart LiMa service...")
    _, out, err = ssh.exec_command("systemctl restart lima-router")
    time.sleep(3)
    _, out, _ = ssh.exec_command("systemctl is-active lima-router")
    status = out.read().decode().strip()
    print(f"   Service status: {status}")

    # Step 6: Health check
    print("\n[6/7] Health check...")
    _, out, _ = ssh.exec_command("curl -s http://127.0.0.1:8080/health 2>&1 | head -5")
    health = out.read().decode().strip()
    print(f"   /health: {health[:100]}")

    # Step 7: Verify CSRF fix
    print("\n[7/7] Verify CSRF fix...")
    _, out, _ = ssh.exec_command("grep LIMA_ADMIN_TOKEN /opt/lima-router/.env | cut -d= -f2")
    token = out.read().decode().strip()

    py_cookie = (
        f"import hmac,hashlib; print(hmac.new('{token}'.encode(), b'lima-admin-session', hashlib.sha256).hexdigest())"
    )
    _, out, _ = ssh.exec_command(f'python3 -c "{py_cookie}"')
    cookie = out.read().decode().strip()

    # Test POST through Nginx (with Origin)
    cmd = " ".join(
        [
            'curl -s -o /dev/null -w "%{http_code}"',
            "-X POST http://127.0.0.1:80/admin/backends",
            '-H "Origin: https://chat.donglicao.com"',
            '-H "Referer: https://chat.donglicao.com/admin"',
            '-H "Host: chat.donglicao.com"',
            '-H "Content-Type: application/json"',
            f'-b "lima_admin_session={cookie}"',
            """-d '{"name":"_m21_test","url":"http://localhost:9999","model":"test"}'""",
        ]
    )
    _, out, _ = ssh.exec_command(cmd, timeout=20)
    code = out.read().decode().strip()
    print(f"   POST via Nginx: HTTP {code} {'PASS' if code == '200' else 'FAIL'}")

    # Test PUT through Nginx
    cmd = " ".join(
        [
            'curl -s -o /dev/null -w "%{http_code}"',
            "-X PUT http://127.0.0.1:80/admin/backends/_m21_test",
            '-H "Origin: https://chat.donglicao.com"',
            '-H "Referer: https://chat.donglicao.com/admin"',
            '-H "Host: chat.donglicao.com"',
            '-H "Content-Type: application/json"',
            f'-b "lima_admin_session={cookie}"',
            """-d '{"url":"http://localhost:8888","model":"test2"}'""",
        ]
    )
    _, out, _ = ssh.exec_command(cmd, timeout=20)
    code = out.read().decode().strip()
    print(f"   PUT via Nginx: HTTP {code} {'PASS' if code == '200' else 'FAIL'}")

    # Test DELETE through Nginx
    cmd = " ".join(
        [
            'curl -s -o /dev/null -w "%{http_code}"',
            "-X DELETE http://127.0.0.1:80/admin/backends/_m21_test",
            '-H "Origin: https://chat.donglicao.com"',
            '-H "Referer: https://chat.donglicao.com/admin"',
            '-H "Host: chat.donglicao.com"',
            f'-b "lima_admin_session={cookie}"',
        ]
    )
    _, out, _ = ssh.exec_command(cmd, timeout=20)
    code = out.read().decode().strip()
    print(f"   DELETE via Nginx: HTTP {code} {'PASS' if code == '200' else 'FAIL'}")

    # Test admin page loads
    cmd = " ".join(
        [
            'curl -s -o /dev/null -w "%{http_code}"',
            "http://127.0.0.1:80/admin",
            f'-b "lima_admin_session={cookie}"',
        ]
    )
    _, out, _ = ssh.exec_command(cmd, timeout=15)
    code = out.read().decode().strip()
    print(f"   GET /admin: HTTP {code} {'PASS' if code == '200' else 'FAIL'}")

    # Clean up test backend via direct backend API
    cmd = " ".join(
        [
            'curl -s -o /dev/null -w "%{http_code}"',
            "-X DELETE http://127.0.0.1:8080/admin/backends/_m21_test",
            '-H "Origin: https://chat.donglicao.com"',
            '-H "Referer: https://chat.donglicao.com/admin"',
            f'-b "lima_admin_session={cookie}"',
        ]
    )
    ssh.exec_command(cmd, timeout=10)

    print("\n" + "=" * 70)
    print("M21 Deploy complete!")
    print("Changes:")
    print("  1. CSRF: Now checks X-Forwarded-Host and Host headers (Nginx proxy)")
    print("  2. Nginx: Added Origin/Referer forwarding to admin proxy blocks")
    print("  3. JS: Nav switching triggers data loading")
    print("  4. JS: All API calls have error handling")
    print("  5. JS: Toast messages use correct API response fields")
    print("  6. JS: Auto-refresh interval: 5s -> 10s")
    print("=" * 70)

finally:
    ssh.close()
