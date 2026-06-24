"""[DEPRECATED v3.1] XiaoZhi v1 compatibility layer retired.
All endpoints have been migrated to routes/device_app_*.py
Kept for reference only; do not import or register."""


from __future__ import annotations

import io
import logging
import secrets
import string

from fastapi.responses import JSONResponse

from .db import connect
from .http_helpers import err, expires_at, new_id, now

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
    ImageFont = None  # type: ignore[assignment]
    _PIL_IMPORT_ERROR: ImportError | None = exc
else:
    _PIL_IMPORT_ERROR = None

_log = logging.getLogger(__name__)
CAPTCHA_CODE_LENGTH = 4
CAPTCHA_TTL_SECONDS = 300
CAPTCHA_IMAGE_WIDTH = 120
CAPTCHA_IMAGE_HEIGHT = 40


def _cleanup_expired() -> None:
    with connect() as conn:
        conn.execute("DELETE FROM v2_captcha WHERE expires_at <= ?", (now(),))
        conn.commit()


def create_captcha(code: str | None = None) -> tuple[str, str]:
    """Create a captcha session and return (captcha_id, code)."""
    if code is None:
        code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(CAPTCHA_CODE_LENGTH))
    code = code.upper()
    captcha_id = new_id()
    with connect() as conn:
        _cleanup_expired()
        conn.execute(
            "INSERT INTO v2_captcha (id, code, expires_at) VALUES (?, ?, ?)",
            (captcha_id, code, expires_at(CAPTCHA_TTL_SECONDS)),
        )
        conn.commit()
    return captcha_id, code


def verify_captcha(captcha_id: str | None, captcha_code: str | None) -> JSONResponse | None:
    """Return an error response if the captcha is missing/invalid/expired."""
    if not captcha_id or not captcha_code:
        return err(400, "captchaId and captcha are required", 400)
    with connect() as conn:
        _cleanup_expired()
        row = conn.execute(
            "SELECT code FROM v2_captcha WHERE id=? AND expires_at > ?",
            (captcha_id, now()),
        ).fetchone()
        if row is None:
            return err(4001, "Invalid or expired captcha", 400)
        if not secrets.compare_digest(row["code"].upper(), captcha_code.upper()):
            return err(4001, "Invalid or expired captcha", 400)
        conn.execute("DELETE FROM v2_captcha WHERE id=?", (captcha_id,))
        conn.commit()
    return None


def generate_captcha_image(code: str) -> bytes | None:
    """Render a simple PNG captcha image. Returns None if PIL is unavailable."""
    if Image is None or ImageDraw is None or ImageFont is None:
        _log.warning("PIL is not installed: %s", _PIL_IMPORT_ERROR)
        return None
    try:
        img = Image.new("RGB", (CAPTCHA_IMAGE_WIDTH, CAPTCHA_IMAGE_HEIGHT), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        for _ in range(5):
            draw.line(
                [
                    (secrets.randbelow(CAPTCHA_IMAGE_WIDTH), secrets.randbelow(CAPTCHA_IMAGE_HEIGHT)),
                    (secrets.randbelow(CAPTCHA_IMAGE_WIDTH), secrets.randbelow(CAPTCHA_IMAGE_HEIGHT)),
                ],
                fill=(secrets.randbelow(200), secrets.randbelow(200), secrets.randbelow(200)),
                width=1,
            )
        try:
            font = ImageFont.truetype("arial.ttf", 22)
        except Exception as exc:
            _log.warning("Preferred captcha font unavailable, falling back to default: %s", exc)
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), code, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (CAPTCHA_IMAGE_WIDTH - text_width) // 2
        y = (CAPTCHA_IMAGE_HEIGHT - text_height) // 2 - 2
        draw.text((x, y), code, fill=(0, 0, 0), font=font)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as exc:
        _log.warning("Failed to generate captcha image: %s", exc)
        return None
