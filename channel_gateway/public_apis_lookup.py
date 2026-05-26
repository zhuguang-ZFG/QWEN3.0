"""Lookup helpers for channel §十三 tools (dictionary, WHOIS, QR, geocode)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

_log = logging.getLogger(__name__)

_USER_AGENT = "LiMa-ChannelTools/1.0"
_TIMEOUT = 12


def _get_json(url: str, *, headers: dict | None = None) -> dict | list:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def fetch_dictionary(word: str) -> dict:
    term = re.sub(r"[^\w\s\-']", "", word.strip())[:60]
    if not term:
        return {"ok": False, "error": "用法：/词典 hello（英文单词）"}
    try:
        enc = urllib.parse.quote(term)
        data = _get_json(f"https://api.dictionaryapi.dev/api/v2/entries/en/{enc}")
        if not isinstance(data, list) or not data:
            return {"ok": False, "error": f"未找到释义：{term}"}
        entry = data[0]
        head = str(entry.get("word") or term)
        lines: list[str] = [f"【{head}】"]
        for meaning in (entry.get("meanings") or [])[:3]:
            pos = str(meaning.get("partOfSpeech") or "")
            for defn in (meaning.get("definitions") or [])[:2]:
                text = str(defn.get("definition") or "").strip()
                if text:
                    prefix = f"{pos}: " if pos else ""
                    lines.append(f"· {prefix}{text[:300]}")
        if len(lines) <= 1:
            return {"ok": False, "error": "释义为空"}
        return {"ok": True, "text": "\n".join(lines)[:1500]}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"词典暂不可用：{type(exc).__name__}"}


def fetch_whois(domain: str) -> dict:
    raw = domain.strip().lower()
    raw = re.sub(r"^https?://", "", raw).split("/")[0].split(":")[0]
    if not raw or not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", raw):
        return {"ok": False, "error": "用法：/whois example.com"}
    try:
        data = _get_json(f"https://rdap.org/domain/{urllib.parse.quote(raw)}")
        status = ", ".join(str(s) for s in (data.get("status") or [])[:3])
        events = data.get("events") or []
        created = next(
            (e.get("eventDate", "") for e in events if e.get("eventAction") == "registration"),
            "",
        )
        entities = data.get("entities") or []
        registrar = ""
        for ent in entities:
            if "registrar" in (ent.get("roles") or []):
                vcard = ent.get("vcardArray")
                if isinstance(vcard, list) and len(vcard) > 1:
                    for row in vcard[1]:
                        if len(row) >= 4 and row[0] == "fn":
                            registrar = str(row[3])
                            break
        lines = [raw]
        if status:
            lines.append(f"状态：{status[:200]}")
        if created:
            lines.append(f"注册：{created[:40]}")
        if registrar:
            lines.append(f"注册商：{registrar[:120]}")
        if len(lines) <= 1:
            return {"ok": False, "error": "WHOIS 无有效字段"}
        return {"ok": True, "text": "\n".join(lines)[:1500]}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"WHOIS 暂不可用：{type(exc).__name__}"}


def fetch_qr(text: str) -> dict:
    payload = text.strip()[:500]
    if not payload:
        return {"ok": False, "error": "用法：/二维码 https://example.com"}
    enc = urllib.parse.quote(payload)
    url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={enc}"
    return {
        "ok": True,
        "text": f"二维码链接（打开或下载）：\n{url}\n\n内容：{payload[:200]}",
    }


def fetch_geocode(place: str) -> dict:
    query = re.sub(r"[^\w\u4e00-\u9fff\s\-,]", "", place.strip())[:80]
    if not query:
        return {"ok": False, "error": "用法：/地理 北京市天安门"}
    try:
        params = urllib.parse.urlencode(
            {"q": query, "format": "json", "limit": 1},
        )
        data = _get_json(
            f"https://nominatim.openstreetmap.org/search?{params}",
            headers={"Accept-Language": "zh-CN,en"},
        )
        if not isinstance(data, list) or not data:
            return {"ok": False, "error": f"未找到地点：{query}"}
        hit = data[0]
        name = str(hit.get("display_name") or query)
        lat = hit.get("lat", "")
        lon = hit.get("lon", "")
        return {
            "ok": True,
            "text": f"{name}\n坐标：{lat}, {lon}",
        }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"地理编码暂不可用：{type(exc).__name__}"}


def fetch_randomuser(seed: str = "") -> dict:
    """Generate one fake user profile (randomuser.me, no API key)."""
    try:
        params: dict[str, str] = {"results": "1"}
        clean_seed = re.sub(r"[^\w\-]", "", (seed or "").strip())[:32]
        if clean_seed:
            params["seed"] = clean_seed
        url = "https://randomuser.me/api/?" + urllib.parse.urlencode(params)
        data = _get_json(url)
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list) or not results:
            return {"ok": False, "error": "假数据生成失败"}
        user = results[0]
        name = user.get("name") or {}
        loc = user.get("location") or {}
        full = " ".join(
            x for x in (name.get("title"), name.get("first"), name.get("last")) if x
        ).strip()
        city = loc.get("city", "")
        country = loc.get("country", "")
        email = user.get("email", "")
        phone = user.get("phone", "")
        lines = [f"【假用户】{full or 'Anonymous'}"]
        if city or country:
            lines.append(f"地点：{city} {country}".strip())
        if email:
            lines.append(f"邮箱：{email}")
        if phone:
            lines.append(f"电话：{phone}")
        if clean_seed:
            lines.append(f"seed：{clean_seed}")
        return {"ok": True, "text": "\n".join(lines)[:1500]}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"假数据服务暂不可用：{type(exc).__name__}"}


def _normalize_host(raw: str) -> str:
    host = raw.strip().lower()
    host = re.sub(r"^https?://", "", host)
    host = host.split("/")[0].split(":")[0]
    return host[:253]


def fetch_ssl(host: str) -> dict:
    """Check TLS certificate expiry for a public host (stdlib, no API key)."""
    name = _normalize_host(host)
    if not name or not re.match(r"^[a-z0-9.-]+$", name):
        return {"ok": False, "error": "用法：/ssl example.com"}
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((name, 443), timeout=_TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=name) as ssock:
                cert = ssock.getpeercert() or {}
                cipher = ssock.cipher()
        not_after = cert.get("notAfter", "")
        issuer = cert.get("issuer", ())
        org = ""
        for item in issuer:
            if item[0] == "organizationName":
                org = str(item[1])
                break
        expiry = ""
        if not_after:
            try:
                dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(
                    tzinfo=timezone.utc
                )
                expiry = dt.strftime("%Y-%m-%d")
            except ValueError:
                expiry = not_after
        lines = [name, f"颁发者：{org or 'unknown'}"]
        if expiry:
            lines.append(f"到期：{expiry}")
        if cipher:
            lines.append(f"加密：{cipher[0]}")
        return {"ok": True, "text": "\n".join(lines)[:1500]}
    except (TimeoutError, OSError, ssl.SSLError) as exc:
        return {"ok": False, "error": f"SSL 检查失败：{type(exc).__name__}"}


def fetch_regex_test(args: str) -> dict:
    """Local regex match test (no external API)."""
    raw = args.strip()
    if not raw:
        return {"ok": False, "error": "用法：/正则 \\d+ hello123"}
    parts = raw.split(maxsplit=1)
    if len(parts) < 2:
        return {"ok": False, "error": "用法：/正则 <pattern> <text>"}
    pattern, text = parts[0][:120], parts[1][:500]
    try:
        match = re.search(pattern, text)
    except re.error as exc:
        return {"ok": False, "error": f"无效正则：{exc}"}
    if not match:
        return {"ok": True, "text": f"模式 `{pattern}` 未匹配\n文本：{text[:200]}"}
    return {
        "ok": True,
        "text": (
            f"匹配：`{match.group(0)[:200]}`\n"
            f"位置：{match.start()}-{match.end()}\n"
            f"文本：{text[:200]}"
        ),
    }


def fetch_image(keyword: str = "") -> dict:
    """Return a stable placeholder image URL (picsum.photos, no API key)."""
    kw = re.sub(r"[^\w\u4e00-\u9fff\s\-]", "", (keyword or "lima").strip())[:40] or "lima"
    seed = hashlib.sha256(kw.encode("utf-8")).hexdigest()[:12]
    url = f"https://picsum.photos/seed/{seed}/800/600"
    return {
        "ok": True,
        "text": f"图片链接：\n{url}\n关键词：{kw}",
    }
