# Hardware Companion References

> Updated: 2026-05-24
> Purpose: keep external hardware references in the LiMa roadmap without
> confusing them with the first writing-machine implementation target.

## Position

LiMa's first direct hardware target remains `esp32S_XYZ`: U8 connects to the
LiMa Device Gateway, receives bounded `motion_task` commands, controls U1
through the existing Edge-D UART JSON contract, and returns `motion_event`
state.

Voice, display, and companion-device references are admitted as later hardware
families only after the writing-machine control loop is verified.

## Reference Classes

| Reference | Class | Borrow | Boundary |
|---|---|---|---|
| `https://github.com/akdeb/ElatoAI.git` | Voice AI / ESP32 companion device | ESP32-to-cloud WebSocket device shape, realtime audio posture, device lifecycle ideas | Do not copy code or assume its voice stack controls motion hardware. LiMa still needs deterministic task, safety, and telemetry layers. |
| `https://github.com/NVIDIA/personaplex.git` | Realtime speech/persona companion model | Full-duplex speech-to-speech interaction, text persona prompting, and audio voice-conditioning shape for future companion devices | Treat as a model and interaction reference only. Model weights need separate NVIDIA Open Model License, compute, privacy, and safety review before use. |
| `https://did321.github.io/2021/07/28/ESP32-TFT-%E5%88%86%E5%85%89%E6%A3%B1%E9%95%9C%E5%AE%9E%E7%8E%B0%E9%80%8F%E6%98%8E%E5%B0%8F%E7%94%B5%E8%A7%86/` | Display / transparent companion screen | ESP32 + TFT display pattern for visual status, avatar, prompts, and ambient companion output | Treat as display output only. It does not replace writing-machine motion safety, path planning, or actuator control. |

## Roadmap Placement

1. Writing machine direct control:
   - `/device/v1/ws`;
   - `hello`, `heartbeat`, `transcript`, `motion_task`, `motion_event`;
   - deterministic `write_text`, `draw_generated`, `home`, `pause`, `resume`,
     and `stop`;
   - real-device safety smoke.
2. Voice hardware extension:
   - direct audio framing;
   - ASR/TTS through LiMa provider routing;
   - optional realtime speech-to-speech persona model evaluation after privacy,
     safety, and compute gates;
   - wake/listen/speak state;
   - voice confirmation events.
3. Display hardware extension:
   - `display_task` or `ui_state` message family;
   - text/image/status payloads;
   - low-bandwidth update and offline fallback rules.
4. Companion-device orchestration:
   - combine motion, voice, and display as separate capabilities under one
     Device Gateway contract;
   - keep each actuator/display class behind its own allowlist and safety
     policy.

## Non-Goals For The Current Slice

- Do not expand Phase 1 of the LiMa Device Gateway beyond text-only fake U8
  protocol and bounded motion-task proof.
- Do not make ElatoAI or the transparent-TV reference a runtime dependency.
- Do not claim LiMa can operate arbitrary smart hardware until a specific
  adapter, protocol schema, tests, and safety gates exist for that hardware
  class.
