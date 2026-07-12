"""Production E2E probes for device-app gallery (upload, thumb_token, file proxy)."""

from __future__ import annotations

import io
import os
import urllib.parse
from dataclasses import dataclass

from voice_e2e_http import get_json, post_multipart
from voice_e2e_probe import resolve_device_app_token

GALLERY_PATH = "/device/v1/app/gallery"


@dataclass(frozen=True)
class GalleryProbeResult:
    name: str
    status: str
    message: str


def gallery_e2e_strict() -> bool:
    return os.environ.get("LIMA_GALLERY_E2E_STRICT", "").strip().lower() in {"1", "true", "yes"}


def gallery_e2e_skipped() -> bool:
    return os.environ.get("LIMA_GALLERY_E2E_SKIP", "").strip().lower() in {"1", "true", "yes"}


def _minimal_jpeg_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color=(240, 240, 240)).save(buf, format="JPEG")
    return buf.getvalue()


def _get_bytes(host: str, path: str, *, bearer: str = "", timeout: float = 90) -> tuple[int, bytes]:
    import urllib.error
    import urllib.request

    from voice_e2e_http import UA, https_ctx

    headers = dict(UA)
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(f"https://{host}{path}", headers=headers)
    try:
        with urllib.request.urlopen(req, context=https_ctx(), timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _parse_fetch_token(download_url: str) -> str:
    parsed = urllib.parse.urlparse(download_url)
    query = urllib.parse.parse_qs(parsed.query)
    values = query.get("fetch_token") or []
    return values[0] if values else ""


def run_gallery_e2e_probes_authenticated(host: str, *, token: str | None = None) -> list[GalleryProbeResult]:
    """Resolve bearer (env/wechat) when omitted, then run gallery probes."""
    bearer = token
    if not bearer:
        bearer, source = resolve_device_app_token(host)
        if not bearer:
            return [GalleryProbeResult("gallery_auth_e2e", "skip", source)]
    return run_gallery_e2e_probes(host, bearer)


def _probe_upload(host: str, token: str) -> tuple[list[GalleryProbeResult], str, str]:
    status, body = post_multipart(
        host,
        GALLERY_PATH,
        files={"file": ("gallery-e2e.jpg", _minimal_jpeg_bytes(), "image/jpeg")},
        bearer=token,
    )
    if status == 503:
        return [GalleryProbeResult("gallery_upload", "skip", "gallery storage not configured (503)")], "", ""
    if status != 200 or body.get("code") != 0:
        return [GalleryProbeResult("gallery_upload", "fail", f"HTTP {status} {repr(body)[:200]}")], "", ""
    data = body.get("data") or {}
    image_id = str(data.get("id") or "")
    thumb_token = str(data.get("thumbToken") or "")
    if not image_id or not thumb_token:
        return [GalleryProbeResult("gallery_upload", "fail", "missing id or thumbToken in upload response")], "", ""
    return [GalleryProbeResult("gallery_upload", "ok", f"image_id={image_id[:12]}")], image_id, thumb_token


def _probe_list(host: str, token: str, image_id: str) -> GalleryProbeResult:
    status, list_body = get_json(host, GALLERY_PATH, bearer=token)
    if status != 200 or list_body.get("code") != 0:
        return GalleryProbeResult("gallery_list", "fail", f"HTTP {status}")
    payload = list_body.get("data") or {}
    total = payload.get("total")
    images = payload.get("images") or []
    ok = isinstance(total, int) and any(str(item.get("id")) == image_id for item in images)
    return GalleryProbeResult("gallery_list", "ok" if ok else "fail", f"total={total} count={len(images)}")


def _probe_thumbs(host: str, token: str, image_id: str, thumb_token: str) -> list[GalleryProbeResult]:
    thumb_path = f"{GALLERY_PATH}/{image_id}/thumb?thumb_token={urllib.parse.quote(thumb_token)}"
    thumb_status, thumb_bytes = _get_bytes(host, thumb_path)
    results = [
        GalleryProbeResult(
            "gallery_thumb_token",
            "ok" if thumb_status == 200 and len(thumb_bytes) >= 16 else "fail",
            f"HTTP {thumb_status} bytes={len(thumb_bytes)}"
            if not (thumb_status == 200 and len(thumb_bytes) >= 16)
            else f"bytes={len(thumb_bytes)}",
        )
    ]
    legacy_status, _ = _get_bytes(host, f"{GALLERY_PATH}/{image_id}/thumb?access_token={urllib.parse.quote(token)}")
    results.append(
        GalleryProbeResult(
            "gallery_thumb_rejects_access_token",
            "ok" if legacy_status == 401 else "fail",
            "401" if legacy_status == 401 else f"expected 401 got {legacy_status}",
        )
    )
    return results


def _probe_download_and_file(host: str, token: str, image_id: str) -> list[GalleryProbeResult]:
    dl_status, dl_body = get_json(host, f"{GALLERY_PATH}/{image_id}/download", bearer=token)
    fetch_token = ""
    if dl_status == 200 and dl_body.get("code") == 0:
        fetch_token = _parse_fetch_token(str((dl_body.get("data") or {}).get("url") or ""))
    if not fetch_token:
        return [GalleryProbeResult("gallery_download", "fail", f"HTTP {dl_status}")]
    results = [GalleryProbeResult("gallery_download", "ok", "fetch_token issued")]
    file_status, file_bytes = _get_bytes(
        host,
        f"{GALLERY_PATH}/{image_id}/file?fetch_token={urllib.parse.quote(fetch_token)}",
    )
    results.append(
        GalleryProbeResult(
            "gallery_file_proxy",
            "ok" if file_status == 200 and len(file_bytes) >= 16 else "fail",
            f"bytes={len(file_bytes)}"
            if file_status == 200 and len(file_bytes) >= 16
            else f"HTTP {file_status} bytes={len(file_bytes)}",
        )
    )
    return results


def _probe_delete(host: str, token: str, image_id: str, thumb_token: str) -> list[GalleryProbeResult]:
    thumb_path = f"{GALLERY_PATH}/{image_id}/thumb?thumb_token={urllib.parse.quote(thumb_token)}"
    del_status, del_body = post_json_delete(host, f"{GALLERY_PATH}/{image_id}", bearer=token)
    if del_status != 200 or del_body.get("code") != 0:
        return [GalleryProbeResult("gallery_delete", "fail", f"HTTP {del_status}")]
    results = [GalleryProbeResult("gallery_delete", "ok", "deleted")]
    gone_status, _ = _get_bytes(host, thumb_path)
    results.append(
        GalleryProbeResult(
            "gallery_deleted_thumb_404",
            "ok" if gone_status == 404 else "fail",
            "404" if gone_status == 404 else f"HTTP {gone_status}",
        )
    )
    return results


def run_gallery_e2e_probes(host: str, token: str) -> list[GalleryProbeResult]:
    """Exercise gallery upload/list/thumb/file/delete on production."""
    results, image_id, thumb_token = _probe_upload(host, token)
    if not image_id:
        return results
    results.append(_probe_list(host, token, image_id))
    results.extend(_probe_thumbs(host, token, image_id, thumb_token))
    results.extend(_probe_download_and_file(host, token, image_id))
    results.extend(_probe_delete(host, token, image_id, thumb_token))
    return results


def post_json_delete(host: str, path: str, *, bearer: str) -> tuple[int, dict]:
    import json
    import urllib.error
    import urllib.request

    from voice_e2e_http import UA, https_ctx

    headers = dict(UA)
    headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(f"https://{host}{path}", headers=headers, method="DELETE")
    try:
        with urllib.request.urlopen(req, context=https_ctx(), timeout=90) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"detail": raw}


def exit_code_for_results(results: list[GalleryProbeResult]) -> int:
    if gallery_e2e_skipped():
        return 0
    for item in results:
        if item.status == "fail":
            return 1
        if item.status == "skip" and gallery_e2e_strict():
            return 1
    return 0


def print_probe_results(results: list[GalleryProbeResult]) -> None:
    for item in results:
        print(f"{item.status.upper():4} {item.name}: {item.message}")
