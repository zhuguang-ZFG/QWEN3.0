"""TinyFish transport for search_gateway.AnySearchAdapter."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .safety import is_public_http_url

SEARCH_URL = "https://api.search.tinyfish.ai"
FETCH_URL = "https://api.fetch.tinyfish.ai"

def _is_safe_url(url: str) -> bool:
    """Reject private/loopback URLs to prevent SSRF."""
    return is_public_http_url(url)


def _opener():
    return urllib.request.build_opener()


def tinyfish_transport(payload: dict) -> dict:
    """Route AnySearchAdapter calls to TinyFish Search/Fetch APIs."""
    method = payload.get("method", "")
    params = payload.get("params", {})
    key = os.environ.get("TINYFISH_API_KEY", "")

    if not key:
        return {"ok": False, "error": "TINYFISH_API_KEY not configured"}

    opener = _opener()

    try:
        if method == "search":
            query = urllib.parse.urlencode({"query": params["query"]})
            req = urllib.request.Request(
                f"{SEARCH_URL}?{query}",
                headers={"X-API-Key": key, "User-Agent": "LiMa/1.3"},
            )
            resp = opener.open(req, timeout=10)
            data = json.loads(resp.read())
            results = data if isinstance(data, list) else data.get("results", [])
            return {"ok": True, "results": results[:params.get("max_results", 5)]}

        elif method == "batch_search":
            queries = params.get("queries", [])
            all_results = []
            for q in queries:
                query = urllib.parse.urlencode({"query": q})
                req = urllib.request.Request(
                    f"{SEARCH_URL}?{query}",
                    headers={"X-API-Key": key, "User-Agent": "LiMa/1.3"},
                )
                resp = opener.open(req, timeout=10)
                data = json.loads(resp.read())
                items = data if isinstance(data, list) else data.get("results", [])
                all_results.extend(items[:params.get("max_results", 5)])
            return {"ok": True, "results": all_results}

        elif method == "extract_url":
            url = params.get("url", "")
            if not _is_safe_url(url):
                return {"ok": False, "error": "URL blocked: private/invalid"}
            body = json.dumps({"urls": [url]}).encode()
            req = urllib.request.Request(
                FETCH_URL, data=body,
                headers={"X-API-Key": key, "Content-Type": "application/json",
                         "User-Agent": "LiMa/1.3"},
            )
            resp = opener.open(req, timeout=15)
            data = json.loads(resp.read())
            results = data.get("results", [])
            if results:
                return {"ok": True, "text": results[0].get("text", "")}
            errors = data.get("errors", [])
            return {"ok": False, "error": errors[0] if errors else "no content"}

        return {"ok": False, "error": f"unknown method: {method}"}

    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)[:100]}
