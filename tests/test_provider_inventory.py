"""Tests for CF-G-0 provider inventory."""

import json
from unittest.mock import MagicMock

import httpx
import pytest

from provider_inventory.cloudflare import (
    fetch_cloudflare_models,
    normalize_cloudflare_item,
    parse_cloudflare_response,
)
from provider_inventory.compare import compare_inventory, format_inventory_report
from provider_inventory.google import (
    fetch_google_models,
    normalize_google_item,
    parse_google_response,
)


def test_parse_cloudflare_response_list_result():
    payload = {
        "success": True,
        "result": [
            {"id": "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "name": "Llama 3.3"},
            {"id": "@cf/qwen/qwen2.5-coder-32b-instruct", "name": "Qwen Coder"},
        ],
    }
    models = parse_cloudflare_response(payload)
    assert len(models) == 2
    assert models[0]["model_id"].startswith("@cf/")


def test_normalize_cloudflare_item_prefers_name_slug_over_uuid():
    item = {
        "id": "02c16efa-29f5-4304-8e6c-3d188889f875",
        "name": "@cf/qwen/qwq-32b",
        "description": "QwQ reasoning model",
    }
    normalized = normalize_cloudflare_item(item)
    assert normalized["model_id"] == "@cf/qwen/qwq-32b"


def test_parse_google_response_filters_generate_content():
    payload = {
        "models": [
            {
                "name": "models/gemini-2.5-flash",
                "displayName": "Gemini Flash",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/embedding-001",
                "displayName": "Embedding",
                "supportedGenerationMethods": ["embedContent"],
            },
        ]
    }
    models = parse_google_response(payload)
    assert len(models) == 1
    assert models[0]["model_id"] == "gemini-2.5-flash"


def test_compare_inventory_cf_unregistered():
    inventory = {
        "provider": "cloudflare",
        "models": [
            {"model_id": "@cf/meta/llama-3.3-70b-instruct-fp8-fast"},
            {"model_id": "@cf/new/model-not-registered"},
        ],
    }
    diff = compare_inventory(inventory, backend_prefixes=("cf_", "cfai_"))
    assert diff["remote_count"] == 2
    assert "@cf/new/model-not-registered" in diff["unregistered_remote"]
    assert diff["registered_backend_count"] >= 1


def test_fetch_cloudflare_models_with_mock_client():
    payload = {
        "success": True,
        "result": [{"id": "@cf/test/model-a", "name": "A"}],
    }
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=payload)
    client = MagicMock(spec=httpx.Client)
    client.get.return_value = response

    inventory = fetch_cloudflare_models(
        account_id="acct",
        token="token",
        client=client,
    )
    assert inventory["model_count"] == 1
    client.get.assert_called_once()


def test_fetch_google_models_pagination():
    page1 = {
        "models": [
            {
                "name": "models/gemini-a",
                "displayName": "A",
                "supportedGenerationMethods": ["generateContent"],
            }
        ],
        "nextPageToken": "t2",
    }
    page2 = {
        "models": [
            {
                "name": "models/gemini-b",
                "displayName": "B",
                "supportedGenerationMethods": ["generateContent"],
            }
        ],
    }

    def fake_get(url, params=None):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if params and params.get("pageToken") == "t2":
            resp.json = MagicMock(return_value=page2)
        else:
            resp.json = MagicMock(return_value=page1)
        return resp

    client = MagicMock(spec=httpx.Client)
    client.get.side_effect = fake_get

    inventory = fetch_google_models(api_key="key", client=client)
    assert inventory["model_count"] == 2
    assert client.get.call_count == 2


def test_format_inventory_report_contains_counts():
    cf_inv = {"provider": "cloudflare", "models": []}
    cf_diff = {
        "remote_count": 10,
        "registered_backend_count": 4,
        "registered_in_remote": [],
        "unregistered_remote": ["@cf/x"],
        "registered_missing_from_remote": [],
    }
    text = format_inventory_report(cf_inv, cf_diff, None, None)
    assert "Cloudflare Workers AI" in text
    assert "Unregistered remote models" in text
