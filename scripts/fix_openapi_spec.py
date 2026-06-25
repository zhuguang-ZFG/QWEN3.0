"""Patch docs-site/public/openapi.yaml so it passes Redocly recommended lint."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "docs-site" / "public" / "openapi.yaml"

PUBLIC_PATHS = {
    "/device/v1/app/auth/login",
    "/device/v1/app/auth/register",
    "/device/v1/app/auth/captcha",
}

HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options", "trace"}


def _operation_id(method: str, path: str) -> str:
    parts = [method.lower()] + [p.strip("{}") for p in path.strip("/").split("/")]
    return "_".join(re.sub(r"[^0-9a-zA-Z_]", "_", p) for p in parts).strip("_")


def main() -> None:
    spec = yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))

    spec.setdefault("components", {})
    spec["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "使用 Bearer Token 认证，例如 `Bearer lima_api_token` 或用户 JWT。",
        }
    }
    spec["security"] = [{"bearerAuth": []}]

    info = spec.setdefault("info", {})
    info["license"] = {"name": "Proprietary", "url": "https://donglicao.com"}

    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation["operationId"] = _operation_id(method, path)
            responses = operation.setdefault("responses", {})
            if not any(str(code).startswith("4") for code in responses):
                responses["400"] = {"description": "请求参数错误或未通过验证"}
                responses["401"] = {"description": "认证失败或 Token 无效"}
            if path in PUBLIC_PATHS:
                operation["security"] = []

    # Preserve a reasonable ordering for readability.
    output = yaml.dump(
        spec,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=120,
    )
    SPEC_PATH.write_text(output, encoding="utf-8")
    print(f"Patched {SPEC_PATH}")


if __name__ == "__main__":
    main()
