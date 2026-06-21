"""SileroVAD provider — local voice activity detection using ONNX runtime.

Ported from xiaozhi-server core/providers/vad/silero.py.
Uses silero_vad.onnx model for speech probability estimation.

Dependency: pip install onnxruntime numpy
Model file: ~2MB silero_vad.onnx (auto-downloaded on first use)
"""

from __future__ import annotations

import logging
import os
import time

import numpy as np

from device_voice.vad import VADModelUnavailableError, VADProvider, VADState

_log = logging.getLogger(__name__)

# Default model cache directory
_MODEL_DIR = os.environ.get("LIMA_VOICE_MODEL_DIR", "data/voice_models")
_MODEL_URL = "https://models.silero.ai/vad_models/v5/silero_vad.onnx"

# Audio processing constants
_FRAME_SAMPLES = 512  # 32ms at 16kHz — SileroVAD native frame size
_FRAME_BYTES = _FRAME_SAMPLES * 2  # 16-bit samples


class SileroVADProvider(VADProvider):
    """SileroVAD using ONNX Runtime for speech detection.

    Uses a dual-threshold approach:
      - speech_prob >= high_threshold → definitely speaking
      - speech_prob <= low_threshold  → definitely silent
      - in between → keep previous state
    """

    def __init__(
        self,
        threshold: float = 0.5,
        threshold_low: float = 0.2,
        silence_duration_ms: int = 1200,
        frame_window: int = 3,
    ) -> None:
        self._threshold = threshold
        self._threshold_low = threshold_low
        self._silence_duration_ms = silence_duration_ms
        self._frame_window = frame_window
        self._session = None

    def _ensure_model(self) -> bool:
        """Lazy-load the SileroVAD ONNX model."""
        if self._session is not None:
            return True
        try:
            import onnxruntime
        except ImportError:
            _log.warning("onnxruntime not installed; SileroVAD unavailable")
            return False

        model_path = os.path.join(_MODEL_DIR, "silero_vad.onnx")
        if not os.path.exists(model_path):
            _log.warning(
                "SileroVAD model not found at %s — download from %s",
                model_path,
                _MODEL_URL,
            )
            return False

        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        self._session = onnxruntime.InferenceSession(model_path, providers=["CPUExecutionProvider"], sess_options=opts)
        _log.info("SileroVAD model loaded from %s", model_path)
        return True

    def detect(self, audio_chunk: bytes, state: VADState) -> bool:
        """Process PCM audio chunk and update VAD state.

        Raises:
            VADModelUnavailableError: if the SileroVAD ONNX model cannot be
            loaded. Callers must handle this explicitly rather than accepting
            a silently degraded pass-through.
        """
        if not self._ensure_model():
            raise VADModelUnavailableError(
                "SileroVAD model unavailable: ensure onnxruntime is installed "
                f"and the model is present at {_MODEL_DIR}/silero_vad.onnx "
                f"(download from {_MODEL_URL})"
            )

        if state.onnx_state is None or state.onnx_context is None:
            state.onnx_state = np.zeros((2, 1, 128), dtype=np.float32)
            state.onnx_context = np.zeros((1, 64), dtype=np.float32)

        has_voice = False
        offset = 0
        while offset + _FRAME_BYTES <= len(audio_chunk):
            frame = audio_chunk[offset : offset + _FRAME_BYTES]
            offset += _FRAME_BYTES

            audio_int16 = np.frombuffer(frame, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            audio_input = np.concatenate([state.onnx_context, audio_float32.reshape(1, -1)], axis=1).astype(np.float32)

            ort_inputs = {
                "input": audio_input,
                "state": state.onnx_state,
                "sr": np.array(16000, dtype=np.int64),
            }
            out, new_state = self._session.run(None, ort_inputs)
            state.onnx_state = new_state
            state.onnx_context = audio_input[:, -64:]

            speech_prob = out.item()
            # Dual-threshold
            if speech_prob >= self._threshold:
                is_voice = True
            elif speech_prob <= self._threshold_low:
                is_voice = False
            else:
                is_voice = state.last_is_voice

            state.last_is_voice = is_voice
            state.voice_window.append(is_voice)
            if len(state.voice_window) > self._frame_window:
                state.voice_window.pop(0)

            has_voice = state.voice_window.count(True) >= self._frame_window

            if is_voice:
                state.speech_buffer.extend(frame)
                state.is_speaking = True
                state.silence_frames = 0
                state.last_voice_time_ms = time.monotonic() * 1000
            else:
                state.silence_frames += 1

        state.total_frames += 1
        return has_voice

    def is_utterance_end(self, state: VADState) -> bool:
        """Check if silence duration exceeds the utterance-end threshold."""
        if not state.is_speaking:
            return False
        elapsed = time.monotonic() * 1000 - state.last_voice_time_ms
        return elapsed >= self._silence_duration_ms

    def reset(self, state: VADState) -> None:
        """Reset VAD state for a new utterance."""
        super().reset(state)
        state.last_voice_time_ms = 0.0
        state.last_is_voice = False
        state.voice_window.clear()
        if state.onnx_state is not None:
            state.onnx_state = np.zeros((2, 1, 128), dtype=np.float32)
        if state.onnx_context is not None:
            state.onnx_context = np.zeros((1, 64), dtype=np.float32)
