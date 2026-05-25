"""Send SILK voice bubbles with playtime + context_token (iLink protocol)."""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import uuid
from pathlib import Path

log = logging.getLogger(__name__)


async def send_silk_voice_bubble(
    adapter,
    chat_id: str,
    silk_path: str,
    *,
    playtime_ms: int,
) -> bool:
    """Upload SILK and send ITEM_VOICE with non-zero playtime."""
    from gateway.platforms.weixin import (
        EP_SEND_MESSAGE,
        ITEM_VOICE,
        MEDIA_VOICE,
        MSG_STATE_FINISH,
        MSG_TYPE_BOT,
        API_TIMEOUT_MS,
        _aes128_ecb_encrypt,
        _aes_padded_size,
        _api_post,
        _cdn_upload_url,
        _get_upload_url,
        _upload_ciphertext,
    )

    session = adapter._send_session
    token = adapter._token
    if not session or not token:
        log.warning("send_silk_voice: no session/token")
        return False

    account_id = adapter._account_id
    context_token = adapter._token_store.get(account_id, chat_id)
    if not context_token:
        log.warning("send_silk_voice: missing context_token for %s", chat_id[:12])

    plaintext = Path(silk_path).read_bytes()
    filekey = secrets.token_hex(16)
    aes_key = secrets.token_bytes(16)
    rawsize = len(plaintext)
    rawfilemd5 = hashlib.md5(plaintext).hexdigest()
    play_ms = max(1000, int(playtime_ms or 1000))

    upload_response = await _get_upload_url(
        session,
        base_url=adapter._base_url,
        token=token,
        to_user_id=chat_id,
        media_type=MEDIA_VOICE,
        filekey=filekey,
        rawsize=rawsize,
        rawfilemd5=rawfilemd5,
        filesize=_aes_padded_size(rawsize),
        aeskey_hex=aes_key.hex(),
    )
    upload_param = str(upload_response.get("upload_param") or "")
    upload_full_url = str(upload_response.get("upload_full_url") or "")
    if not upload_param and not upload_full_url:
        log.warning("getUploadUrl failed: %s", upload_response)
        return False

    ciphertext = _aes128_ecb_encrypt(plaintext, aes_key)
    upload_url = upload_full_url or _cdn_upload_url(adapter._cdn_base_url, upload_param, filekey)
    encrypted_query_param = await _upload_ciphertext(
        session, ciphertext=ciphertext, upload_url=upload_url
    )
    aes_key_for_api = base64.b64encode(aes_key.hex().encode("ascii")).decode("ascii")
    media_item = {
        "type": ITEM_VOICE,
        "voice_item": {
            "media": {
                "encrypt_query_param": encrypted_query_param,
                "aes_key": aes_key_for_api,
                "encrypt_type": 1,
            },
            "encode_type": 6,
            "bits_per_sample": 16,
            "sample_rate": 24000,
            "playtime": play_ms,
        },
    }
    client_id = f"lima-voice-{uuid.uuid4().hex}"
    payload_msg = {
        "from_user_id": "",
        "to_user_id": chat_id,
        "client_id": client_id,
        "message_type": MSG_TYPE_BOT,
        "message_state": MSG_STATE_FINISH,
        "item_list": [media_item],
    }
    if context_token:
        payload_msg["context_token"] = context_token

    await _api_post(
        session,
        base_url=adapter._base_url,
        endpoint=EP_SEND_MESSAGE,
        payload={"msg": payload_msg},
        token=token,
        timeout_ms=API_TIMEOUT_MS,
    )
    log.info(
        "voice bubble ok chat=%s playtime_ms=%s ctx=%s",
        chat_id[:12],
        play_ms,
        bool(context_token),
    )
    return True
