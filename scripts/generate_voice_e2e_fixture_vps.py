#!/usr/bin/env python3
"""Generate voice E2E fixture on VPS (DashScope TTS) and download locally."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from scripts.deploy_unified_common import get_deploy_target
from scripts.deploy_unified_restart import _connect_ssh, _ssh_exec

REMOTE = r"""/opt/dlc-drawing/.venv/bin/python - <<'PY'
import base64
import json
import os
import sqlite3
import wave
from pathlib import Path

def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out

env = load_env(Path('/opt/dlc-drawing/.env'))
api_key = env.get('DASHSCOPE_API_KEY') or env.get('ALIYUN_API_KEY') or ''
if not api_key:
    print(json.dumps({'error': 'missing_dashscope_key'}))
    raise SystemExit(1)

text = '画一只猫'
out_path = Path('/tmp/voice_probe_draw_cat.wav')

try:
    import dashscope
    from dashscope.audio.tts_v2 import SpeechSynthesizer
    from dashscope.audio.tts_v2.speech_synthesizer import AudioFormat
except ImportError as exc:
    print(json.dumps({'error': f'dashscope_tts_import:{exc}'}))
    raise SystemExit(1)

dashscope.api_key = api_key
synth = SpeechSynthesizer(
    model='cosyvoice-v1',
    voice='longxiaochun',
    format=AudioFormat.WAV_16000HZ_MONO_16BIT,
)
result = synth.call(text)
if isinstance(result, (bytes, bytearray)):
    audio = bytes(result)
else:
    status = result.get_status_code() if hasattr(result, 'get_status_code') else getattr(result, 'status_code', None)
    if status and status != 200:
        print(json.dumps({'error': 'tts_failed', 'detail': str(result)}))
        raise SystemExit(1)
    audio = result.get_audio_data() if hasattr(result, 'get_audio_data') else None
    if audio is None and hasattr(result, 'get_audio_frame'):
        frames = []
        while True:
            frame = result.get_audio_frame()
            if not frame:
                break
            frames.append(frame)
        audio = b''.join(frames) if frames else None
if not audio:
    print(json.dumps({'error': 'tts_empty_audio', 'result_type': type(result).__name__, 'repr': repr(result)[:300]}))
    raise SystemExit(1)

out_path.write_bytes(audio)
print(json.dumps({'ok': True, 'bytes': len(audio), 'path': str(out_path), 'b64': base64.b64encode(audio).decode('ascii')}))
PY"""


def main() -> int:
    out_file = Path(__file__).resolve().parent / "fixtures" / "voice_probe_draw_cat.wav"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    ssh = _connect_ssh(get_deploy_target())
    try:
        code, stdout, stderr = _ssh_exec(ssh, REMOTE)
    finally:
        ssh.close()
    if stderr:
        print(stderr[:400])
    if code != 0:
        print(f"remote failed exit={code}")
        print(stdout[:400])
        return 1
    import json

    payload = json.loads(stdout.strip().splitlines()[-1])
    if payload.get("error"):
        print(f"error: {payload['error']}")
        return 1
    audio = base64.b64decode(payload["b64"])
    out_file.write_bytes(audio)
    print(f"Wrote {out_file} ({len(audio) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
