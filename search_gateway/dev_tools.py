from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Protocol

from .safety import is_public_http_url, sanitize_error_text


class DevSearchAdapter(Protocol):
    def search(self, query: str, *, domain: str | None = None, max_results: int = 5) -> dict: ...
    def batch_search(self, queries: list[str], *, domain: str | None = None, max_results: int = 5) -> dict: ...
    def extract_url(self, url: str) -> dict: ...


@dataclass(frozen=True)
class DevSearchResult:
    title: str
    url: str
    snippet: str
    source: str

    def as_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
        }


def _normalize_results(raw: dict, *, source: str) -> list[dict[str, str]]:
    results = raw.get("results", []) if isinstance(raw, dict) else []
    normalized: list[dict[str, str]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "Untitled")[:200]
        url = str(item.get("url") or item.get("link") or "")
        snippet = str(item.get("snippet") or item.get("content") or item.get("text") or "")[:1000]
        normalized.append(DevSearchResult(title, url, snippet, source).as_dict())
    return normalized


def search_docs(
    query: str,
    domains: list[str] | None = None,
    *,
    adapter: DevSearchAdapter,
    max_results: int = 5,
) -> dict:
    clean_query = sanitize_error_text(query, max_chars=500)
    domain = domains[0] if domains else None
    raw = adapter.search(clean_query, domain=domain, max_results=max_results)
    if not raw.get("ok"):
        return {"ok": False, "tool": "dev_search_docs", "error": raw.get("error", "search_failed")}
    return {"ok": True, "tool": "dev_search_docs", "results": _normalize_results(raw, source="search")}


def search_error(
    error_text: str,
    language: str = "",
    framework: str = "",
    *,
    adapter: DevSearchAdapter,
    max_results: int = 5,
) -> dict:
    parts = [sanitize_error_text(error_text, max_chars=1500)]
    if language:
        parts.append(language)
    if framework:
        parts.append(framework)
    query = " ".join(part for part in parts if part).strip()
    raw = adapter.search(query, domain=None, max_results=max_results)
    if not raw.get("ok"):
        return {"ok": False, "tool": "dev_search_error", "error": raw.get("error", "search_failed")}
    return {"ok": True, "tool": "dev_search_error", "results": _normalize_results(raw, source="error_search")}


def search_codesearch(
    query: str,
    *,
    max_results: int = 5,
    path_hint: str | None = None,
) -> dict:
    from search_gateway.codesearch_adapter import search_local_code

    raw = search_local_code(query, max_results=max_results, path_hint=path_hint)
    if not raw.get("ok"):
        return {
            "ok": False,
            "tool": "dev_search_codesearch",
            "error": raw.get("error", "search_failed"),
        }
    results = []
    for item in raw.get("results") or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        snippet = str(item.get("snippet") or "")[:1000]
        title = path.rsplit("/", 1)[-1] if path else "match"
        results.append(
            DevSearchResult(title, path or "local", snippet, "codesearch").as_dict()
        )
    return {
        "ok": True,
        "tool": "dev_search_codesearch",
        "engine": raw.get("engine"),
        "root": raw.get("root"),
        "results": results,
    }


def read_url(url: str, *, adapter: DevSearchAdapter, max_chars: int = 6000) -> dict:
    if not is_public_http_url(url):
        return {"ok": False, "tool": "dev_read_url", "error": "url_blocked"}
    raw = adapter.extract_url(url)
    if not raw.get("ok"):
        return {"ok": False, "tool": "dev_read_url", "error": raw.get("error", "fetch_failed")}
    return {
        "ok": True,
        "tool": "dev_read_url",
        "url": url,
        "title": str(raw.get("title") or "")[:200],
        "text": str(raw.get("text") or "")[:max_chars],
    }


def fetch_github_file(
    repo: str,
    path: str,
    ref: str = "main",
    *,
    adapter: DevSearchAdapter,
    max_chars: int = 8000,
) -> dict:
    safe_repo = repo.strip().strip("/")
    safe_path = path.strip().lstrip("/")
    safe_ref = urllib.parse.quote(ref.strip() or "main", safe="/")
    if safe_repo.count("/") != 1 or not safe_path:
        return {"ok": False, "tool": "dev_fetch_github_file", "error": "invalid_github_target"}
    raw_url = f"https://raw.githubusercontent.com/{safe_repo}/{safe_ref}/{safe_path}"
    read = read_url(raw_url, adapter=adapter, max_chars=max_chars)
    read["tool"] = "dev_fetch_github_file"
    read["repo"] = safe_repo
    read["path"] = safe_path
    read["ref"] = ref
    return read


def search_gitee(
    query: str,
    *,
    repo: str | None = None,
    max_results: int = 5,
) -> dict:
    """Search Gitee repositories and scoped issues (mirror-aware)."""
    from .gitee_tools import search_gitee as _search_gitee

    clean = sanitize_error_text(query, max_chars=200)
    if not clean:
        return {"ok": False, "tool": "dev_search_gitee", "error": "empty_query"}
    raw = _search_gitee(clean, repo=repo, max_results=max_results)
    if not raw.get("ok"):
        out: dict = {"ok": False, "tool": "dev_search_gitee", "error": raw.get("error", "search_failed")}
        if raw.get("skipped"):
            out["skipped"] = True
        return out
    return {
        "ok": True,
        "tool": "dev_search_gitee",
        "repo": raw.get("repo", ""),
        "results": _normalize_results(raw, source="gitee"),
    }


def fetch_gitee_file(
    repo: str,
    path: str,
    ref: str = "master",
    *,
    max_chars: int = 8000,
) -> dict:
    """Fetch a file from a Gitee repository via OpenAPI."""
    from .gitee_tools import fetch_repo_file

    safe_repo = repo.strip().strip("/")
    safe_path = path.strip().lstrip("/")
    if safe_repo.count("/") != 1 or not safe_path:
        return {"ok": False, "tool": "dev_fetch_gitee_file", "error": "invalid_gitee_target"}
    raw = fetch_repo_file(safe_repo, safe_path, ref=ref or "master", max_chars=max_chars)
    if not raw.get("ok"):
        out: dict = {"ok": False, "tool": "dev_fetch_gitee_file", "error": raw.get("error", "fetch_failed")}
        if raw.get("skipped"):
            out["skipped"] = True
        return out
    return {
        "ok": True,
        "tool": "dev_fetch_gitee_file",
        "repo": safe_repo,
        "path": safe_path,
        "ref": ref or "master",
        "text": str(raw.get("text") or "")[:max_chars],
    }


def summarize_sources(sources: list[dict], *, max_chars: int = 3000) -> dict:
    lines: list[str] = []
    for idx, source in enumerate(sources, start=1):
        title = str(source.get("title") or "Untitled")[:160]
        url = str(source.get("url") or "")[:300]
        snippet = str(source.get("snippet") or source.get("text") or "")[:700]
        lines.append(f"[{idx}] {title}\nURL: {url}\nEvidence: {snippet}")
    evidence = "\n\n".join(lines)[:max_chars]
    return {"ok": True, "tool": "dev_summarize_sources", "evidence": evidence}


def build_prompt_evidence(tool_outputs: list[dict], *, max_chars: int = 4000) -> dict:
    sections: list[str] = []
    for output in tool_outputs:
        tool_name = str(output.get("tool") or "unknown_tool")
        if output.get("results"):
            for result in output["results"]:
                url = str(result.get("url", ""))
                path = str(result.get("path", ""))
                loc = url or path
                sections.append(
                    f"Tool: {tool_name}\n"
                    f"Title: {str(result.get('title', 'Untitled'))[:160]}\n"
                    f"Location: {loc[:300]}\n"
                    f"Evidence: {str(result.get('snippet', ''))[:700]}"
                )
        elif output.get("text"):
            sections.append(
                f"Tool: {tool_name}\n"
                f"URL: {str(output.get('url', ''))[:300]}\n"
                f"Evidence: {str(output.get('text', ''))[:900]}"
            )
    return {
        "ok": True,
        "tool": "dev_prompt_evidence",
        "evidence": "\n\n".join(sections)[:max_chars],
    }


def search_google_grounded(query: str, *, max_tokens: int = 2000) -> dict:
    """Search with Google Search grounding via Gemini native API.

    Public doc retrieval only — private code must not be sent here.
    Requires GOOGLE_AI_KEY + LIMA_GOOGLE_NATIVE=1.
    """
    try:
        from search_gateway.gemini_native import generate_content

        result = generate_content(
            query[:4000],
            model="gemini-2.5-flash",
            temperature=0.3,
            max_tokens=max_tokens,
            grounding=True,
            system_instruction=(
                "You are a technical documentation search assistant. "
                "Answer based on the latest official documentation, API references, "
                "and public knowledge sources. Cite URLs when available. "
                "Be concise and factual. Use code examples when helpful."
            ),
        )
        if result.get("ok"):
            return {
                "ok": True,
                "tool": "google_grounded_search",
                "text": result.get("text", ""),
                "grounding": result.get("grounding"),
                "model": result.get("model", ""),
                "token_count": result.get("token_count", 0),
            }
        return result
    except ImportError:
        return {"ok": False, "error": "gemini_native adapter not installed"}
    except Exception as exc:
        return {"ok": False, "error": f"grounded search failed: {exc}"}
