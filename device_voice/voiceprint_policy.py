"""Voiceprint policy decision logic."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from device_voice.voiceprint_types import SpeakerIdentity, VoiceprintEntry, VoiceprintPolicy

_log = logging.getLogger(__name__)


def decide_voiceprint_policy(
    mode: str,
    entries: list[VoiceprintEntry],
    speaker_ref: Optional[str],
) -> VoiceprintPolicy:
    """Decide whether to allow a request based on voiceprint policy.

    Modes (ported from xiaozhi-server):
      - voiceprint_off: always allow, no identification
      - loose: allow even if unknown speaker
      - child: allow children + unknown, block adults
      - strict: block unknown speakers

    Args:
        mode: Policy mode string.
        entries: Active voiceprint entries for the device.
        speaker_ref: Matched speaker reference from 3D-Speaker.

    Returns:
        VoiceprintPolicy with allowed, reason, and matched member.
    """
    normalized_mode = (mode or "voiceprint_off").strip().lower()
    active_entries = [e for e in entries if e.status == "active"]

    if normalized_mode == "voiceprint_off":
        return VoiceprintPolicy(allowed=True, reason="voiceprint_off")

    matched = next(
        (e for e in active_entries if speaker_ref and e.speaker_ref == speaker_ref),
        None,
    )
    if matched is not None:
        reason = (
            "child_reenroll_required" if matched.member_type == "child" and matched.reenroll_required else "matched"
        )
        return VoiceprintPolicy(allowed=True, reason=reason, member=matched)

    if normalized_mode == "loose":
        return VoiceprintPolicy(allowed=True, reason="unknown_allowed")
    if normalized_mode == "child":
        child_entries = [e for e in active_entries if e.member_type == "child"]
        reason = "child_unknown_allowed" if child_entries else "child_no_profile_allowed"
        return VoiceprintPolicy(allowed=True, reason=reason)
    if normalized_mode == "strict":
        return VoiceprintPolicy(allowed=False, reason="unknown_rejected")
    return VoiceprintPolicy(allowed=False, reason="invalid_mode")


async def _identify_speaker_impl(
    provider: object,
    wav_data: bytes,
    device_id: str,
    threshold: float,
    similarity_fn: Callable[[list[float], list[float]], float],
) -> SpeakerIdentity:
    """Identify the speaker by comparing embeddings in the provider cache."""
    if not provider.enabled:
        return SpeakerIdentity(reason="voiceprint_off")
    embedding = await provider.extract_embedding(wav_data)
    if embedding is None:
        _log.warning("device=%s voiceprint embedding extraction failed", device_id)
        return SpeakerIdentity(reason="extraction_failed")
    entries = provider.cache.entries_for_device(device_id)
    if not entries:
        await provider._load_device_embeddings(device_id)
        entries = provider.cache.entries_for_device(device_id)
    if not entries:
        _log.info("device=%s no registered voiceprints", device_id)
        return SpeakerIdentity(reason="no_voiceprints")
    best_match = None
    best_score = 0.0
    for entry in entries:
        if entry.embedding is None:
            continue
        score = similarity_fn(embedding, entry.embedding)
        if score > best_score:
            best_score = score
            best_match = entry
    if best_match is None or best_score < threshold:
        _log.info("device=%s voiceprint unknown (best_score=%.3f threshold=%.3f)", device_id, best_score, threshold)
        return SpeakerIdentity(confidence=best_score, is_known=False, reason="unknown")
    _log.info(
        "device=%s voiceprint matched: member=%s display=%s score=%.3f",
        device_id,
        best_match.member_id,
        best_match.display_name,
        best_score,
    )
    return SpeakerIdentity(
        member_id=str(best_match.member_id),
        display_name=best_match.display_name,
        confidence=best_score,
        is_known=True,
        speaker_ref=best_match.speaker_ref,
        reason="matched",
    )


__all__ = ["decide_voiceprint_policy"]
