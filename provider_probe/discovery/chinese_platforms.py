"""Chinese platform scraper: V2EX, Zhihu, and other Chinese tech forums.

Discovers domestic AI API services by scraping Chinese-language tech
communities where new free/cheap AI APIs are often shared.
"""

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chinese platform configuration
# ---------------------------------------------------------------------------

V2EX_TOPICS = [
    ("https://www.v2ex.com/go/ai", "V2EX AI"),
    ("https://www.v2ex.com/go/programmer", "V2EX Programmer"),
    ("https://www.v2ex.com/go/api", "V2EX API"),
]

# V2EX API endpoints (unofficial)
V2EX_API = "https://www.v2ex.com/api/v2/topics"

# Keywords for Chinese AI API discussions
_CN_KEYWORDS = re.compile(
    r"(免费|白嫖|不要钱|无需注册|无需API.?[Kk]ey|不限量|公益)"
    r"(大模型|AI|API|接口|LLM|GPT|聊天|编程)",
)

_API_URL_CN = re.compile(
    r"(https?://[^\s\)]*(?:api|gateway|v1|chat|completion|models)[^\s\)]*)",
    re.IGNORECASE,
)

# Common Chinese AI API domains
_KNOWN_DOMAINS = {
    "api.siliconflow.cn": "SiliconFlow",
    "dashscope.aliyuncs.com": "DashScope",
    "api.baichuan-ai.com": "Baichuan",
    "api.moonshot.cn": "Moonshot/Kimi",
    "open.bigmodel.cn": "Zhipu/GLM",
    "api.deepseek.com": "DeepSeek",
    "api.minimax.chat": "MiniMax",
    "api.stepfun.com": "StepFun",
    "api.z.ai": "Z-API",
    "ark.cn-beijing.volces.com": "Volcengine",
}

# Sites known to discuss free AI APIs
_TRACKED_URLS = [
    "https://linux.do/search?q=免费API%20大模型",
    "https://hellogithub.com/search?q=免费API",
]


async def fetch_page(url: str, headers: dict | None = None) -> str | None:
    """Fetch a page with browser-like headers."""
    default_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if headers:
        default_headers.update(headers)

    try:
        async with httpx.AsyncClient(timeout=15, headers=default_headers) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            logger.debug("fetch_page %s: HTTP %d", url[:60], resp.status_code)
            return None
    except Exception as exc:
        logger.debug("fetch_page %s: %s", url[:60], type(exc).__name__)
        return None


def extract_api_info(html: str) -> list[dict]:
    """Extract API-related information from HTML content."""
    results: list[dict] = []

    # Find API URLs
    urls = _API_URL_CN.findall(html)
    for url in urls:
        url = url.rstrip(".,;:)]}'\"")
        results.append({"url": url, "source": "html_scrape"})

    # Check for known domains
    for domain, name in _KNOWN_DOMAINS.items():
        if domain in html:
            results.append({
                "url": f"https://{domain}",
                "name": name,
                "source": "known_domain",
            })

    return results


async def scan_v2ex() -> list[dict]:
    """Scan V2EX for Chinese AI API discussions."""
    all_results: list[dict] = []

    for endpoint, label in V2EX_TOPICS:
        logger.info("Scanning V2EX: %s", label)
        content = await fetch_page(endpoint)
        if content:
            # Look for topic titles containing AI/API keywords
            title_pattern = re.compile(
                r'<a[^>]*href="/t/(\d+)"[^>]*>([^<]*'
                r"(?:免费|API|大模型|AI|接口|LLM)[^<]*)</a>",
                re.IGNORECASE,
            )
            matches = title_pattern.findall(content)
            for topic_id, title in matches:
                all_results.append({
                    "source": f"v2ex:{label}",
                    "topic_id": topic_id,
                    "title": title.strip(),
                    "url": f"https://www.v2ex.com/t/{topic_id}",
                })
                logger.info("  V2EX topic: %s", title.strip()[:60])

    logger.info("V2EX scan: %d relevant topics", len(all_results))
    return all_results


async def scan_tracked_urls() -> list[dict]:
    """Scan tracked Chinese tech sites for AI API discussions."""
    results: list[dict] = []

    for url in _TRACKED_URLS:
        logger.info("Scanning tracked URL: %s", url[:60])
        content = await fetch_page(url)
        if content:
            api_info = extract_api_info(content)
            for info in api_info:
                info["source_url"] = url
                results.append(info)

    return results


async def scan_chinese_platforms() -> list[dict]:
    """Run all Chinese platform scans.

    Returns list of discovered providers and discussions.
    """
    all_results: list[dict] = []

    # V2EX
    v2ex_results = await scan_v2ex()
    all_results.extend(v2ex_results)

    # Tracked URLs
    tracked = await scan_tracked_urls()
    all_results.extend(tracked)

    return all_results
