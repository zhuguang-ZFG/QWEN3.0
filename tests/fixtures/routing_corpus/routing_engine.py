"""Fixture stub: routing engine five-layer selection."""

from http_caller import call_api
import health_tracker


def select_backend(candidates: list[str]) -> str:
    """Five-layer routing engine selects backends based on health scores."""
    scores = health_tracker.get_scores()
    for name in candidates:
        if health_tracker.is_cooled_down(name):
            continue
        if scores.get(name, 0) >= 40:
            return name
    return candidates[0] if candidates else "local"


def route_request(query: str, messages: list[dict]) -> dict:
    backend = select_backend(["longcat", "nvidia_phi4"])
    answer = call_api(backend, messages, max_tokens=1024)
    return {"backend": backend, "answer": answer}
