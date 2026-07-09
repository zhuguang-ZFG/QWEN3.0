#!/usr/bin/env python3
"""Production E2E smoke for device-app voice (REST transcribe + realtime WS).

Requires credentials (one of):
  - LIMA_VERIFY_DEVICE_APP_TOKEN — device-app JWT
  - LIMA_VERIFY_WECHAT_CODE — WeChat login code (dev or real mini-program)

Optional:
  - LIMA_VERIFY_HOST (default chat.donglicao.com)
  - LIMA_VOICE_E2E_STRICT=1 — require real transcript (画/猫) + 200 transcribe
  - LIMA_VOICE_E2E_AUDIO_PATH — override probe WAV (default scripts/fixtures/voice_probe_draw_cat.wav)
  - LIMA_VOICE_E2E_SKIP=1 — exit 0 immediately

Fixture regeneration (maintainer):
    python scripts/generate_voice_e2e_fixture_vps.py

Run:
    python scripts/smoke_device_app_voice_e2e.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

SMOKE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SMOKE_DIR.parent
if str(SMOKE_DIR) not in sys.path:
    sys.path.insert(0, str(SMOKE_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from config import deploy_config
from voice_e2e_probe import exit_code_for_results, print_probe_results, run_voice_e2e_probes, voice_e2e_skipped


async def _main_async() -> int:
    if voice_e2e_skipped():
        print("SKIP voice E2E (LIMA_VOICE_E2E_SKIP=1)")
        return 0
    host = deploy_config.VERIFY_HOST
    print(f"Voice E2E host: https://{host}")
    results = await run_voice_e2e_probes(host)
    print("---")
    print_probe_results(results)
    print("---")
    code = exit_code_for_results(results)
    print("RESULT: PASS" if code == 0 else "RESULT: FAIL")
    return code


def main() -> int:
    return asyncio.run(_main_async())


if __name__ == "__main__":
    sys.exit(main())
