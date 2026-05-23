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


DEV_SEARCH_MARKERS = (
    "docs",
    "documentation",
    "official doc",
    "search latest",
    "read http://",
    "read https://",
    "error",
    "exception",
    "traceback",
    "typeerror",
    "valueerror",
    "runtimeerror",
    "importerror",
    "how to fix",
    "查一下",
    "查下",
    "官方文档",
    "怎么用",
    "怎么修",
    "报错",
    "异常",
    "读取",
    "打开链接",
    "看一下",
)


def should_dev_search(query: str) -> bool:
    lowered = (query or "").lower()
    return any(marker in lowered for marker in DEV_SEARCH_MARKERS)
