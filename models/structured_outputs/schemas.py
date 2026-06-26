"""Pydantic schemas for LiMa structured outputs (P4-3 baseline).

These models act as the source of truth for outputs that may later be produced
by an Instructor-patched LLM client. For now they are used for runtime
validation and safe fallbacks.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ClassifyResult(BaseModel):
    """Result of request-type classification."""

    request_type: Literal["ide", "chat", "vision", "image"] = Field(
        default="chat",
        description="High-level request type used for backend routing.",
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ScenarioResult(BaseModel):
    """Result of scenario classification. v3.0 retired non-chat scenarios."""

    scenario: Literal["chat"] = Field(
        default="chat",
        description="User scenario; always 'chat' since coding retirement.",
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class IntentResult(BaseModel):
    """Result of user-intent analysis."""

    intent: str = Field(default="chat", min_length=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    complexity: float = Field(default=0.5, ge=0.0, le=1.0)
    needs_code: bool = Field(default=False)
    domain_keywords: list[str] = Field(default_factory=list)
    cnc_subdomain: str = Field(default="general")
    source: str = Field(default="default_fallback")
    entities: dict[str, str | int | float] = Field(default_factory=dict)

    @field_validator("intent")
    @classmethod
    def _intent_lowercase(cls, value: str) -> str:
        return value.strip().lower() or "chat"


class BackendScore(BaseModel):
    """Score assigned to a backend during route scoring."""

    backend: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)
    reason: str = Field(default="")
