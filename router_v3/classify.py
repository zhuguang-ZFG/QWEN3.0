"""Request classification for LiMa Router V3."""

from router_v3.ide import detect_ide_by_fingerprints


def classify_request(path: str, headers: dict, body: dict) -> dict:
    """看元数据分类，不看内容。<1ms"""
    req_type = "chat"

    if path.startswith("/v1/messages"):
        req_type = "ide"
    else:
        ua = headers.get("user-agent", "").lower()
        if any(
            x in ua
            for x in [
                "claude-code",
                "cursor",
                "aider",
                "codex",
                "cline",
                "continue",
                "vscode",
                "kiro",
                "zed",
                "trae",
                "windsurf",
                "copilot",
            ]
        ):
            req_type = "ide"

    if req_type != "ide":
        system = _extract_system(body)
        if system:
            if detect_ide_by_fingerprints(system):
                req_type = "ide"

    if req_type != "ide":
        if _has_image_blocks(body):
            req_type = "vision"

    return {"type": req_type}


def _extract_system(body: dict) -> str:
    system = body.get("system", "")
    if isinstance(system, list):
        return " ".join(b.get("text", "") for b in system if b.get("type") == "text")
    if isinstance(system, str) and system:
        return system
    msgs = body.get("messages", [])
    for m in msgs:
        if isinstance(m, dict) and m.get("role") == "system":
            c = m.get("content", "")
            return c if isinstance(c, str) else ""
    return ""


def _has_image_blocks(body: dict) -> bool:
    for m in body.get("messages", []):
        content = m.get("content", "") if isinstance(m, dict) else ""
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") in ("image", "image_url"):
                    return True
    return False
