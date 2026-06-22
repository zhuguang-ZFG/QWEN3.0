"""Pydantic request/response models for the browser microservice."""

from pydantic import BaseModel


class RenderRequest(BaseModel):
    url: str
    wait_ms: int = 3000
    extract_text: bool = True
    screenshot: bool = False
    extra_http_headers: dict[str, str] | None = None


class RenderResponse(BaseModel):
    url: str
    title: str = ""
    text: str = ""
    html_length: int = 0
    status_code: int | None = None
    network_requests: list[dict] = []
    screenshot_b64: str | None = None


class ExtractRequest(BaseModel):
    url: str
    selector: str | None = None
    wait_ms: int = 2000


class ExtractResponse(BaseModel):
    url: str
    text: str = ""
    items: list[str] = []
