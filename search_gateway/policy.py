SEARCH_MARKERS = (
    "search",
    "latest",
    "current",
    "today",
    "web",
    "http://",
    "https://",
    "网页",
    "搜索",
    "最新",
    "查一下",
    "联网",
)


def should_search(query: str) -> bool:
    lowered = query.lower()
    return any(marker in lowered for marker in SEARCH_MARKERS)
