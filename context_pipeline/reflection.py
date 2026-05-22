"""Reflection module — routing decision self-check and correction.

Based on all-agentic-architectures Reflection pattern:
- After selecting a backend, verify the decision makes sense
- Check scenario/backend capability alignment
- Record mismatches for future routing improvement
- Self-correct before sending request when possible
"""

from dataclasses import dataclass


@dataclass
class ReflectionResult:
    """Result of a routing decision self-check."""

    original_backend: str
    corrected_backend: str
    reason: str
    was_corrected: bool


# Backend capability tiers
_STRONG_BACKENDS = {
    "scnet_qwen72b", "scnet_deepseek", "scnet_qwen32b",
    "github_gpt4o", "github_o1mini", "groq_llama70b",
    "cerebras_llama70b", "cohere_command_a",
}

_CODING_CAPABLE = _STRONG_BACKENDS | {
    "cf_qwen_coder", "cfai_coder", "deepseek_free",
    "cohere_command_a_plus", "github_codex",
}

_VISION_CAPABLE = {
    "scnet_qwen72b", "github_gpt4o", "cf_llava",
    "cohere_command_a_vision",
}

_WEAK_BACKENDS = {
    "chat_ubi", "pollinations", "llm7",
}


def reflect_on_routing(
    backend: str,
    scenario: str,
    ide: str,
    available_backends: list[str] | None = None,
) -> ReflectionResult:
    """Self-check a routing decision before sending the request.

    Returns a ReflectionResult indicating whether correction is needed.
    """
    reason = ""
    corrected = backend

    # Rule 1: IDE coding requests should not go to weak backends
    if scenario == "coding" and ide and backend in _WEAK_BACKENDS:
        if available_backends:
            for alt in available_backends:
                if alt in _CODING_CAPABLE:
                    corrected = alt
                    reason = f"IDE coding request routed to weak backend {backend}, corrected to {alt}"
                    break
        if corrected == backend:
            reason = f"WARNING: IDE coding on weak backend {backend}, no alternative available"

    # Rule 2: Vision requests need vision-capable backends
    if scenario == "vision" and backend not in _VISION_CAPABLE:
        if available_backends:
            for alt in available_backends:
                if alt in _VISION_CAPABLE:
                    corrected = alt
                    reason = f"Vision request on non-vision backend {backend}, corrected to {alt}"
                    break
        if corrected == backend and not reason:
            reason = f"WARNING: Vision on non-vision backend {backend}"

    # Rule 3: Coding requests prefer coding-capable backends
    if scenario == "coding" and backend not in _CODING_CAPABLE and not reason:
        if available_backends:
            for alt in available_backends:
                if alt in _CODING_CAPABLE:
                    corrected = alt
                    reason = f"Coding request on general backend {backend}, upgraded to {alt}"
                    break

    return ReflectionResult(
        original_backend=backend,
        corrected_backend=corrected,
        reason=reason,
        was_corrected=(corrected != backend),
    )
