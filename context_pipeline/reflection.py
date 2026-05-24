"""Reflection module — routing decision self-check and correction.

Based on all-agentic-architectures Reflection pattern:
- After selecting a backend, verify the decision makes sense
- Check scenario/backend capability alignment
- Record mismatches for future routing improvement
- Self-correct before sending request when possible
"""

from dataclasses import dataclass

from backends import backend_has_capability, first_backend_with_capability, is_weak_backend


@dataclass
class ReflectionResult:
    """Result of a routing decision self-check."""

    original_backend: str
    corrected_backend: str
    reason: str
    was_corrected: bool


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
    if scenario == "coding" and ide and is_weak_backend(backend):
        if available_backends:
            alt = first_backend_with_capability(available_backends, "code")
            if alt:
                corrected = alt
                reason = f"IDE coding request routed to weak backend {backend}, corrected to {alt}"
        if corrected == backend:
            reason = f"WARNING: IDE coding on weak backend {backend}, no alternative available"

    # Rule 2: Vision requests need vision-capable backends
    if scenario == "vision" and not backend_has_capability(backend, "vision"):
        if available_backends:
            alt = first_backend_with_capability(available_backends, "vision")
            if alt:
                corrected = alt
                reason = f"Vision request on non-vision backend {backend}, corrected to {alt}"
        if corrected == backend and not reason:
            reason = f"WARNING: Vision on non-vision backend {backend}"

    # Rule 3: Coding requests prefer coding-capable backends
    if scenario == "coding" and not backend_has_capability(backend, "code") and not reason:
        if available_backends:
            alt = first_backend_with_capability(available_backends, "code")
            if alt:
                corrected = alt
                reason = f"Coding request on general backend {backend}, upgraded to {alt}"

    return ReflectionResult(
        original_backend=backend,
        corrected_backend=corrected,
        reason=reason,
        was_corrected=(corrected != backend),
    )
