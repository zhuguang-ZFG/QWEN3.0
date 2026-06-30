"""Pydantic request/response models for client key endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class KeyCreateRequest(BaseModel):
    label: str = Field(..., min_length=1)
    quota_daily: int = Field(default=1000, ge=0)
    quota_monthly: int = Field(default=30000, ge=0)
    rate_limit_rpm: int = Field(default=20, ge=0)
    allowed_urls: list[str] = Field(default_factory=lambda: ["*"])
    reveal: bool = False

    @field_validator("allowed_urls")
    @classmethod
    def _validate_allowed_urls(cls, value: list[str]) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("allowed_urls must be a list of strings")
        if not all(isinstance(item, str) for item in value):
            raise ValueError("allowed_urls must be a list of strings")
        return value


class KeyUpdateRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1)
    enabled: bool | None = None
    quota_daily: int | None = Field(default=None, ge=0)
    quota_monthly: int | None = Field(default=None, ge=0)
    rate_limit_rpm: int | None = Field(default=None, ge=0)
    allowed_urls: list[str] | None = None

    @field_validator("allowed_urls")
    @classmethod
    def _validate_allowed_urls(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError("allowed_urls must be a list of strings")
        if not all(isinstance(item, str) for item in value):
            raise ValueError("allowed_urls must be a list of strings")
        return value


class KeyRegenerateRequest(BaseModel):
    reveal: bool = False


class KeyResponse(BaseModel):
    key_id: str
    key_masked: str
    label: str
    enabled: bool
    created_at: float
    last_used_at: float | None = None
    request_count: int = 0
    quota_daily: int
    quota_monthly: int
    rate_limit_rpm: int
    allowed_urls: list[str]
    usage_daily: int = 0
    usage_monthly: int = 0


class KeyListResponse(BaseModel):
    keys: list[KeyResponse]
    total: int
