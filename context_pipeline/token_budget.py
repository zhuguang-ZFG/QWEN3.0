"""Token Budget Manager — GenericAgent-inspired token consumption tracking.

Tracks and controls token consumption per request:
- Estimate input/output tokens before sending
- Budget allocation per request type
- Over-budget degradation (switch to smaller model or truncate)
- Cumulative tracking for cost optimization
"""

from dataclasses import dataclass


@dataclass
class TokenBudget:
    """Token budget for a single request."""

    max_input_tokens: int = 8000
    max_output_tokens: int = 4000
    estimated_input: int = 0
    estimated_output: int = 0
    actual_input: int = 0
    actual_output: int = 0

    @property
    def is_over_budget(self) -> bool:
        return self.estimated_input > self.max_input_tokens

    @property
    def utilization(self) -> float:
        if self.max_input_tokens == 0:
            return 0.0
        return self.estimated_input / self.max_input_tokens


SCENARIO_BUDGETS = {
    "chat": TokenBudget(max_input_tokens=4000, max_output_tokens=2000),
    "coding": TokenBudget(max_input_tokens=16000, max_output_tokens=8000),
    "vision": TokenBudget(max_input_tokens=8000, max_output_tokens=4000),
}


def estimate_tokens(text: str) -> int:
    """Rough token estimation (4 chars ≈ 1 token for English, 2 chars for CJK)."""
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    cjk_chars = len(text) - ascii_chars
    return (ascii_chars // 4) + (cjk_chars // 2) + 1


def estimate_request_tokens(messages: list[dict], system_prompt: str = "") -> int:
    """Estimate total input tokens for a request."""
    total = estimate_tokens(system_prompt) if system_prompt else 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        total += estimate_tokens(part.get("text", ""))
                    elif part.get("type") == "image_url":
                        total += 1000
    return total


def get_budget_for_scenario(scenario: str) -> TokenBudget:
    """Get the token budget for a given scenario."""
    budget = SCENARIO_BUDGETS.get(scenario, SCENARIO_BUDGETS["chat"])
    return TokenBudget(
        max_input_tokens=budget.max_input_tokens,
        max_output_tokens=budget.max_output_tokens,
    )


def check_budget(
    messages: list[dict],
    system_prompt: str,
    scenario: str,
) -> dict:
    """Check if a request fits within its token budget.

    Returns budget status and recommended action.
    """
    budget = get_budget_for_scenario(scenario)
    estimated = estimate_request_tokens(messages, system_prompt)
    budget.estimated_input = estimated

    if not budget.is_over_budget:
        return {
            "within_budget": True,
            "estimated_tokens": estimated,
            "max_tokens": budget.max_input_tokens,
            "utilization": round(budget.utilization, 2),
            "action": "proceed",
        }

    over_by = estimated - budget.max_input_tokens
    if over_by < budget.max_input_tokens * 0.5:
        action = "truncate_context"
    else:
        action = "downgrade_model"

    return {
        "within_budget": False,
        "estimated_tokens": estimated,
        "max_tokens": budget.max_input_tokens,
        "utilization": round(budget.utilization, 2),
        "over_by": over_by,
        "action": action,
    }


class TokenTracker:
    """Cumulative token consumption tracker."""

    def __init__(self) -> None:
        self.total_input: int = 0
        self.total_output: int = 0
        self.request_count: int = 0

    def record(self, input_tokens: int, output_tokens: int) -> None:
        self.total_input += input_tokens
        self.total_output += output_tokens
        self.request_count += 1

    @property
    def total_tokens(self) -> int:
        return self.total_input + self.total_output

    @property
    def avg_per_request(self) -> int:
        if self.request_count == 0:
            return 0
        return self.total_tokens // self.request_count

    def summary(self) -> dict:
        return {
            "total_input": self.total_input,
            "total_output": self.total_output,
            "total": self.total_tokens,
            "requests": self.request_count,
            "avg_per_request": self.avg_per_request,
        }
