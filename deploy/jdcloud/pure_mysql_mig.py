#!/usr/bin/env python3
"""Migrate NewAPI SQLite→MySQL using network_mode:host (containers cannot reach host:3306)."""

from __future__ import annotations

import re
import sqlite3
import subprocess
import time
from pathlib import Path

NEWAPI = Path("/opt/newapi")
DB = NEWAPI / "data" / "one-api.db"
ENV = NEWAPI / ".env"
COMPOSE = NEWAPI / "docker-compose.yml"


def sh(cmd, check=True) -> str:
    if isinstance(cmd, str):
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    else:
        p = subprocess.run(cmd, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"{cmd!r} -> {p.stderr[:500]}")
    return p.stdout


def env_get() -> dict[str, str]:
    out = {}
    for line in ENV.read_text().splitlines():
        s = line.strip()
        if s.startswith("# SQL_DSN="):
            out["SQL_DSN"] = s[2:].split("  #", 1)[0].split("=", 1)[1]
            continue
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k] = v
    return out


def write_env(em: dict[str, str]) -> None:
    keys = ["CRYPTO_SECRET", "SESSION_SECRET", "NEWAPI_MYSQL_USER", "NEWAPI_MYSQL_PASS", "SQL_DSN"]
    lines = [f"{k}={em[k]}" for k in keys if k in em]
    for k, v in em.items():
        if k not in keys:
            lines.append(f"{k}={v}")
    ENV.write_text("\n".join(lines) + "\n")
    ENV.chmod(0o600)


def sql_escape(val) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, (bytes, bytearray, memoryview)):
        b = bytes(val)
        # MySQL JSON columns reject CHARACTER SET binary — prefer utf-8 text
        try:
            s = b.decode("utf-8")
            return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"
        except UnicodeDecodeError:
            return "X'" + b.hex() + "'"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float)):
        return str(val)
    return "'" + str(val).replace("\\", "\\\\").replace("'", "''") + "'"


def patch_compose_host_net(redis_pass: str = "") -> None:
    """new-api uses host network → 127.0.0.1:3306/6379. Keep redis service unused."""
    from urllib.parse import quote

    text = COMPOSE.read_text(encoding="utf-8")
    if "network_mode: host" not in text:
        text = re.sub(
            r"(  new-api:\n(?:.*\n)*?    restart: always\n)",
            r"\1    network_mode: host\n",
            text,
            count=1,
        )
    text = re.sub(
        r"(  new-api:\n(?:.*\n)*?)    ports:\n      - \"3000:3000\"\n",
        r"\1",
        text,
        count=1,
    )
    text = re.sub(r"^\s*-\s*SQL_DSN=.*\n", "", text, flags=re.M)
    text = re.sub(r"^\s*-\s*SQL_MAX_.*\n", "", text, flags=re.M)
    if redis_pass:
        redis_url = f"redis://:{quote(redis_pass, safe='')}@127.0.0.1:6379"
    else:
        redis_url = "redis://127.0.0.1:6379"
    if re.search(r"REDIS_CONN_STRING=", text):
        text = re.sub(
            r"^\s*-\s*REDIS_CONN_STRING=.*$",
            f"      - REDIS_CONN_STRING={redis_url}",
            text,
            flags=re.M,
        )
    text = re.sub(
        r"(  new-api:\n(?:.*\n)*?)    depends_on:\n      - redis\n",
        r"\1",
        text,
        count=1,
    )
    text = re.sub(
        r"    extra_hosts:\n      - \"host.docker.internal:host-gateway\"\n",
        "",
        text,
    )
    COMPOSE.write_text(text, encoding="utf-8")


def wait_tables(seconds: int = 45) -> bool:
    for i in range(seconds // 2):
        time.sleep(2)
        tables = sh(["mysql", "-N", "-e", "SHOW TABLES FROM newapi;"], check=False)
        if "users" in tables and "channels" in tables:
            print(f"  schema ok @ {(i + 1) * 2}s n={len(tables.split())}")
            return True
        st = sh("docker inspect -f '{{.State.Status}}' newapi_new-api_1 2>/dev/null", check=False).strip()
        print(f"  wait {(i + 1) * 2}s state={st} tables={len(tables.split())}")
    return False


def main() -> int:
    em = env_get()
    user, passwd = em.get("NEWAPI_MYSQL_USER"), em.get("NEWAPI_MYSQL_PASS")
    if not user or not passwd:
        print("missing NEWAPI_MYSQL_*")
        return 1

    # host-mode DSN — no query string
    em["SQL_DSN"] = f"{user}:{passwd}@tcp(127.0.0.1:3306)/newapi"
    write_env(em)
    redis_pass = sh(
        "grep -E '^requirepass ' /etc/redis/redis.conf 2>/dev/null | awk '{print $2}'",
        check=False,
    ).strip()
    patch_compose_host_net(redis_pass)

    stamp = sh("date +%Y%m%d_%H%M%S").strip()
    print("[1] backup + stop")
    sh(f"cp -a {DB} /var/backups/newapi/one-api.pre-mysql.{stamp}.db")
    sh("cd /opt/newapi && docker-compose stop new-api")

    print("[2] reset DB")
    sh(["mysql", "-e", "DROP DATABASE IF EXISTS newapi;"])
    sh(["mysql", "-e", "CREATE DATABASE newapi DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"])
    sh(f"mysql -e \"GRANT ALL PRIVILEGES ON newapi.* TO '{user}'@'127.0.0.1'; FLUSH PRIVILEGES;\"", check=False)

    print("[3] bootstrap schema (host network)")
    sh("cd /opt/newapi && docker rm -f newapi_new-api_1 2>/dev/null; true", check=False)
    sh("cd /opt/newapi && docker-compose up -d --no-deps new-api")
    if not wait_tables(50):
        print(sh("docker logs --tail 80 newapi_new-api_1 2>&1", check=False)[-2500:])
        print(sh("docker exec newapi_new-api_1 printenv SQL_DSN 2>&1 | sed 's/:[^@]*@/:***@/'", check=False))
        return 2

    print("[4] stop for data copy")
    sh("cd /opt/newapi && docker-compose stop new-api")

    print("[5] copy rows")
    conn = sqlite3.connect(str(DB))
    cur = conn.cursor()
    tables = [
        r[0]
        for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    priority = ["users", "tokens", "channels", "options", "abilities", "models", "vendors"]
    ordered = [t for t in priority if t in tables] + [t for t in tables if t not in priority]

    for t in ordered:
        sqlite_cols = [c[1] for c in cur.execute(f"PRAGMA table_info(`{t}`)")]
        mysql_raw = sh(["mysql", "-N", "-e", f"SHOW COLUMNS FROM newapi.`{t}`;"], check=False).strip()
        if not mysql_raw:
            print(f"  skip {t}")
            continue
        mysql_cols = [line.split("\t")[0] for line in mysql_raw.splitlines()]
        cols = [c for c in sqlite_cols if c in mysql_cols]
        rows = cur.execute(f"SELECT {','.join('`' + c + '`' for c in cols)} FROM `{t}`").fetchall()
        sh(
            ["mysql", "-e", f"SET FOREIGN_KEY_CHECKS=0; TRUNCATE TABLE newapi.`{t}`; SET FOREIGN_KEY_CHECKS=1;"],
            check=False,
        )
        if not rows:
            print(f"  {t}: 0")
            continue
        cols_sql = ",".join(f"`{c}`" for c in cols)
        n, batch = 0, []
        for row in rows:
            batch.append("(" + ",".join(sql_escape(row[i]) for i in range(len(cols))) + ")")
            if len(batch) >= 40:
                sql = f"INSERT INTO newapi.`{t}` ({cols_sql}) VALUES " + ",".join(batch) + ";"
                p = subprocess.run(
                    ["mysql", "--default-character-set=utf8mb4"],
                    input=sql,
                    capture_output=True,
                    text=True,
                )
                if p.returncode != 0:
                    print(f"FAIL {t}: {p.stderr[:400]}")
                    return 3
                n += len(batch)
                batch = []
        if batch:
            sql = f"INSERT INTO newapi.`{t}` ({cols_sql}) VALUES " + ",".join(batch) + ";"
            p = subprocess.run(
                ["mysql", "--default-character-set=utf8mb4"],
                input=sql,
                capture_output=True,
                text=True,
            )
            if p.returncode != 0:
                print(f"FAIL {t}: {p.stderr[:400]}")
                return 3
            n += len(batch)
        print(f"  {t}: {n}")
    conn.close()

    print("[6] AUTO_INCREMENT + verify")
    for t in ordered:
        if sh(["mysql", "-N", "-e", f"SHOW COLUMNS FROM newapi.`{t}` LIKE 'id';"], check=False).strip():
            mx = int(sh(["mysql", "-N", "-e", f"SELECT IFNULL(MAX(id),0) FROM newapi.`{t}`;"]).strip())
            sh(["mysql", "-e", f"ALTER TABLE newapi.`{t}` AUTO_INCREMENT={mx + 1};"])
    for t in ("users", "tokens", "channels", "options"):
        s = int(sh(f'sqlite3 {DB} "SELECT COUNT(*) FROM {t};"').strip())
        m = int(sh(["mysql", "-N", "-e", f"SELECT COUNT(*) FROM newapi.`{t}`;"]).strip())
        print(f"  {t} {s}->{m}")
        if s != m:
            return 4

    print("[7] start")
    sh("cd /opt/newapi && docker rm -f newapi_new-api_1 2>/dev/null; true", check=False)
    sh("cd /opt/newapi && docker-compose up -d --no-deps new-api")
    time.sleep(10)
    logs = sh("docker logs --tail 30 newapi_new-api_1 2>&1", check=False)
    st = sh("curl -sf -m 10 http://127.0.0.1:3000/api/status", check=False)
    if "SQL_DSN not set" in logs or "using SQLite" in logs:
        print("still sqlite", logs[-1000:])
        return 5
    if "success" not in st:
        print("status fail", logs[-1000:])
        return 5
    print("OK MySQL host-mode", stamp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
