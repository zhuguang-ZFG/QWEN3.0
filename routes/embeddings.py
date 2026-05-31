"""routes/embeddings.py — OpenAI-compatible embeddings proxy (Jina AI)."""
import json
import os
import urllib.error as _ue
import urllib.request as _ur

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from access_guard import require_private_api_key
from routes.json_body import read_json_object

router = APIRouter()


@router.post("/v1/embeddings", dependencies=[Depends(require_private_api_key)])
async def embeddings(request: Request):
    """OpenAI-compatible embeddings endpoint, proxied to Jina AI."""
    body = await read_json_object(request)
    if isinstance(body, JSONResponse):
        return body
    inp = body.get("input", [])
    if isinstance(inp, str):
        inp = [inp]
    model = body.get("model", "jina-embeddings-v3")
    dimensions = body.get("dimensions", 256)

    jina_key = os.environ.get("JINA_API_KEY", "")
    if not jina_key:
        return JSONResponse({"error": "JINA_API_KEY not configured"}, status_code=503)

    gfw_proxy = os.environ.get("GFW_PROXY", "")
    if gfw_proxy:
        proxy = _ur.ProxyHandler({"https": gfw_proxy, "http": gfw_proxy})
        opener = _ur.build_opener(proxy)
    else:
        opener = _ur.build_opener()
    payload = json.dumps({"model": model, "input": inp, "dimensions": dimensions}).encode()
    req = _ur.Request("https://api.jina.ai/v1/embeddings", data=payload, headers={
        "Authorization": f"Bearer {jina_key}",
        "Content-Type": "application/json",
        "User-Agent": "LiMa/1.3",
    })
    try:
        resp = opener.open(req, timeout=15)
        data = json.loads(resp.read())
        return JSONResponse(data)
    except (_ue.URLError, OSError, json.JSONDecodeError) as e:
        return JSONResponse({"error": str(e)[:100]}, status_code=502)
