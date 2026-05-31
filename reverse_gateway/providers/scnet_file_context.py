"""SCNet Web Chat long-context file upload bridge."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any

import httpx


SIGNATURE_URL = "https://www.scnet.cn/acx/chatbot/file/sso/form/signature"
OSS_CONTENT_TYPE = "text/plain"


@dataclass(frozen=True)
class UploadedTextFile:
    name: str
    path: str
    size: int
    type: str = OSS_CONTENT_TYPE

    def as_payload(self) -> dict[str, Any]:
        return {"name": self.name, "path": self.path, "size": self.size, "type": self.type}


def should_bridge_text(content: str, threshold_chars: int) -> bool:
    return len(content) >= max(1, threshold_chars)


def upload_text_context(content: str, headers: dict[str, str], timeout: float) -> UploadedTextFile:
    files = upload_text_context_chunks(content, headers, timeout, chunk_chars=len(content), max_files=1)
    return files[0]


def upload_text_context_chunks(
    content: str,
    headers: dict[str, str],
    timeout: float,
    chunk_chars: int,
    max_files: int,
    max_total_chars: int | None = None,
) -> list[UploadedTextFile]:
    if max_total_chars is not None and len(content) > max_total_chars:
        raise httpx.HTTPError(
            f"SCNet Web Chat file context limit is {max_total_chars} chars; "
            f"received {len(content)} chars. Use retrieval/MCP chunk selection instead of raw 1M pass-through."
        )
    chunks = split_text_chunks(content, chunk_chars, max_files)
    signature = _request_signature(headers, timeout)
    uploaded = []
    for index, chunk in enumerate(chunks, start=1):
        data = chunk.encode("utf-8")
        key = _object_key(signature, data, index)
        _upload_to_oss(signature, key, data, timeout)
        uploaded.append(
            UploadedTextFile(name=key.rsplit("/", 1)[-1], path=_public_url(signature, key), size=len(data))
        )
    return uploaded


def split_text_chunks(content: str, chunk_chars: int, max_files: int) -> list[str]:
    safe_chunk_chars = max(1, chunk_chars)
    safe_max_files = max(1, max_files)
    chunks = [content[index : index + safe_chunk_chars] for index in range(0, len(content), safe_chunk_chars)]
    if len(chunks) > safe_max_files:
        raise httpx.HTTPError(
            f"SCNet file context requires {len(chunks)} chunks, above limit {safe_max_files}"
        )
    return chunks or [""]


def _request_signature(headers: dict[str, str], timeout: float) -> dict[str, Any]:
    safe_headers = {k: v for k, v in headers.items() if k.lower() != "content-type"}
    response = httpx.get(SIGNATURE_URL, headers=safe_headers, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if str(payload.get("code")) != "0" or not isinstance(payload.get("data"), dict):
        raise httpx.HTTPError(f"SCNet file signature failed: {payload}")
    return payload["data"]


def _object_key(signature: dict[str, Any], data: bytes, index: int = 1) -> str:
    directory = str(signature.get("dir") or "").strip("/")
    digest = hashlib.sha256(data).hexdigest()[:32]
    stamp = int(time.time() * 1000)
    filename = f"lima_context_{stamp}_{index:03d}_{digest}.txt"
    return f"{directory}/{filename}" if directory else filename


def _upload_to_oss(signature: dict[str, Any], key: str, data: bytes, timeout: float) -> None:
    host = str(signature.get("host") or "").rstrip("/")
    if not host:
        raise httpx.HTTPError("SCNet file signature did not include OSS host")
    form = {
        "key": key,
        "policy": str(signature.get("policy") or ""),
        "OSSAccessKeyId": str(signature.get("accessid") or ""),
        "success_action_status": "200",
        "signature": str(signature.get("signature") or ""),
    }
    access_control = signature.get("accessControl")
    if access_control:
        form["x-oss-object-acl"] = str(access_control)
    files = {"file": (key.rsplit("/", 1)[-1], data, OSS_CONTENT_TYPE)}
    response = httpx.post(host + "/", data=form, files=files, timeout=timeout)
    response.raise_for_status()


def _public_url(signature: dict[str, Any], key: str) -> str:
    host = str(signature.get("host") or "").rstrip("/")
    if not host:
        raise httpx.HTTPError("SCNet file signature did not include OSS host")
    return f"{host}/{key}"
