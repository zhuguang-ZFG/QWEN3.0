from dataclasses import dataclass


@dataclass(frozen=True)
class SmokeTarget:
    name: str
    url: str
    requires_auth: bool = False


def default_smoke_targets(base_url: str) -> list[SmokeTarget]:
    root = base_url.rstrip("/")
    return [
        SmokeTarget("health", f"{root}/health"),
        SmokeTarget("models", f"{root}/v1/models"),
        SmokeTarget("chat", f"{root}/v1/chat/completions", requires_auth=True),
        SmokeTarget("messages", f"{root}/v1/messages", requires_auth=True),
    ]
