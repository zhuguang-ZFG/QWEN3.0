"""Context Pipeline — Google ADK-inspired ordered processor chain.

Each processor transforms a RequestContext through a defined stage:
1. IDE Detection → identify client environment
2. Scenario Classification → coding/chat/vision
3. Code Context → semantic search for relevant files
4. Prompt Composition → build structured system prompt (vibe-coding layers)
5. Cache Optimization → stable prefix for model prefix caching
6. Session Memory → inject relevant cross-request memory (P1)
"""

from dataclasses import dataclass, field


@dataclass
class RequestContext:
    """Mutable context object passed through the processor pipeline."""

    # Input
    messages: list[dict] = field(default_factory=list)
    headers: dict = field(default_factory=dict)
    path: str = ""

    # Derived by processors
    ide: str = ""
    scenario: str = "chat"
    code_context: str = ""
    system_prompt: str = ""
    quality_gate: str = ""

    # Pipeline metadata
    processors_applied: list[str] = field(default_factory=list)
