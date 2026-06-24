#!/usr/bin/env python3
"""Build a public-only OpenAPI 3.0 spec from the full FastAPI export."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from openapi_examples import (
    parameter_with_example,
    request_example,
    response_example,
    synthetic_query_param,
)


class CompactSeq:
    """PyYAML wrapper that emits a short list in flow style."""

    __slots__ = ("value",)

    def __init__(self, value: list[Any]) -> None:
        self.value = value


def _compact_seq_representer(dumper: yaml.Dumper, data: CompactSeq) -> Any:
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data.value, flow_style=True)


yaml.SafeDumper.add_representer(CompactSeq, _compact_seq_representer)

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "openapi_full.json"
OUTPUT = ROOT / "docs" / "openapi.yaml"
KEEP_V1 = {"/v1/chat/completions", "/v1/images/generations"}
DUPLICATE_PREFIX = "/device/v1/app/device/v1/app/"


def is_public(path: str) -> bool:
    """Return True for public endpoints only."""
    return path in KEEP_V1 or path.startswith("/device/v1/app/")


def clean_public_path(path: str) -> str:
    """Normalize any accidentally duplicated /device/v1/app/ prefix."""
    while DUPLICATE_PREFIX in path:
        path = path.replace(DUPLICATE_PREFIX, "/device/v1/app/")
    return path


def clean_text(key: str, text: str | None) -> str | None:
    """Decode mixed-encoding text safely; never silently drop content."""
    if text is None:
        return None
    try:
        raw = text.encode("latin-1")
    except UnicodeEncodeError:
        return text
    for encoding in ("utf-8", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    cleaned = raw.decode("utf-8", errors="replace")
    print(f"Warning: could not decode text for key {key!r}; replaced bad bytes")
    return cleaned


def load_spec(path: Path) -> dict[str, Any]:
    """Load the JSON spec, trying UTF-8 first then GBK."""
    raw = path.read_bytes()
    for encoding in ("utf-8", "gbk"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
        print("Warning: could not decode openapi_full.json as utf-8 or gbk; replaced bad bytes")
    return json.loads(text)


def human_summary(path: str, method: str, existing: str | None) -> str:
    """Return a concise human-friendly summary."""
    if existing and len(existing) > 2:
        return existing
    parts = [p for p in path.strip("/").split("/") if p and not p.startswith("{")]
    action = {
        "get": "List" if path.endswith("s") else "Get",
        "post": "Create",
        "put": "Update",
        "patch": "Update",
        "delete": "Delete",
    }.get(method.lower(), method.upper())
    noun = " ".join(parts[-2:]) if len(parts) > 1 else (parts[-1] if parts else "resource")
    return f"{action} {noun.replace('_', ' ').title()}"


def human_description(path: str, method: str) -> str:
    """Return a short description for the endpoint."""
    method = method.upper()
    if path == "/v1/chat/completions":
        return "OpenAI-compatible chat completions with multi-backend routing."
    if path == "/v1/images/generations":
        return "OpenAI-compatible image generation (text-to-image)."
    base = path.replace("/device/v1/app/", "").replace("/", " ").replace("_", " ")
    base = re.sub(r"\{[^}]+\}", "a resource", base)
    return f"{method} {base.strip()}."


def enrich_operation(path: str, method: str, op: dict[str, Any]) -> dict[str, Any]:
    """Add summary, description, and examples to an operation."""
    op = dict(op)
    op["summary"] = human_summary(path, method, clean_text("summary", op.get("summary")))
    desc = clean_text("description", op.get("description"))
    if desc:
        op["description"] = desc
    elif path in {"/v1/chat/completions", "/v1/images/generations"}:
        op["description"] = human_description(path, method)
    op.pop("operationId", None)

    params = op.get("parameters", [])
    if method.lower() in {"get", "delete"}:
        if not params:
            params = [synthetic_query_param(path)]
        params = [parameter_with_example(p) for p in params]
    op["parameters"] = CompactSeq(params)
    if "tags" in op:
        op["tags"] = CompactSeq(op["tags"])

    req = request_example(path, method)
    if req is not None and req != {}:
        op["requestBody"] = {"content": {"application/json": {"example": req}}}

    op["responses"] = {
        "200": {
            "description": "Successful response",
            "content": {"application/json": {"example": response_example(path, method)}},
        }
    }
    return op


def to_openapi_30(spec: dict[str, Any]) -> dict[str, Any]:
    """Convert a minimal 3.1 export to OpenAPI 3.0.3."""
    spec = dict(spec)
    spec["openapi"] = "3.0.3"
    info = dict(spec.get("info", {}))
    info["title"] = info.get("title", "LiMa Public API")
    info["version"] = info.get("version", "1.3")
    info["description"] = "LiMa public API surface for chat, image generation, and device-app integration."
    spec["info"] = info
    spec.pop("webhooks", None)
    spec.pop("jsonSchemaDialect", None)
    if not spec.get("servers"):
        spec["servers"] = [{"url": "https://chat.donglicao.com", "description": "Production"}]
    components = dict(spec.get("components", {}))
    schemas = components.get("schemas", {})
    components["schemas"] = {name: downgrade_schema(schema) for name, schema in schemas.items()}
    spec["components"] = components
    return spec


def downgrade_schema(schema: Any) -> Any:
    """Recursively convert 3.1 schema idioms to 3.0."""
    if isinstance(schema, dict):
        schema = dict(schema)
        typ = schema.get("type")
        if isinstance(typ, list) and "null" in typ:
            non_null = [t for t in typ if t != "null"]
            if non_null:
                schema["type"] = non_null[0]
                schema["nullable"] = True
            else:
                schema["type"] = "object"
                schema["nullable"] = True
        for key in ("exclusiveMinimum", "exclusiveMaximum"):
            if isinstance(schema.get(key), bool):
                schema.pop(key, None)
        for k, v in schema.items():
            schema[k] = downgrade_schema(v)
    elif isinstance(schema, list):
        return [downgrade_schema(v) for v in schema]
    return schema


def _unwrap_compact(obj: Any) -> Any:
    if isinstance(obj, CompactSeq):
        return obj.value
    if isinstance(obj, dict):
        return {k: _unwrap_compact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_unwrap_compact(v) for v in obj]
    return obj


def referenced_schemas(spec: dict[str, Any]) -> set[str]:
    """Return schema names referenced from paths (not from other schemas)."""
    found: set[str] = set()
    paths = _unwrap_compact(spec.get("paths", {}))
    for m in re.finditer(r"#/components/schemas/([A-Za-z0-9_]+)", json.dumps(paths)):
        found.add(m.group(1))
    return found


def main() -> None:
    spec = to_openapi_30(load_spec(INPUT))
    new_paths: dict[str, Any] = {}
    for path in sorted(spec.get("paths", {}).keys()):
        if not is_public(path):
            continue
        clean_path = clean_public_path(path)
        new_methods = {
            method: enrich_operation(clean_path, method, spec["paths"][path][method])
            for method in spec["paths"][path]
        }
        new_paths[clean_path] = new_methods
    spec["paths"] = new_paths

    used = referenced_schemas(spec)
    if "components" in spec and "schemas" in spec["components"]:
        spec["components"]["schemas"] = {
            k: v for k, v in spec["components"]["schemas"].items() if k in used
        }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        yaml.dump(
            spec,
            f,
            Dumper=yaml.SafeDumper,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=None,
            width=500,
        )
    print(f"Wrote {OUTPUT} ({len(new_paths)} paths)")


if __name__ == "__main__":
    main()
