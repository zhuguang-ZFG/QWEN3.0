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


CODESEARCH_MARKERS = (
    ".py",
    ".ts",
    ".tsx",
    ".rs",
    ".go",
    "routing_engine",
    "where is",
    "find ",
    "locate ",
    "在哪个文件",
    "哪段代码",
    "代码在哪",
    "源码",
    "函数定义",
    "class ",
    "def ",
)


def should_codesearch_local(query: str) -> bool:
    """Prefer local codesearch for repo-scoped code location queries."""
    lowered = (query or "").lower()
    if should_dev_search(query):
        return False
    return any(marker in lowered for marker in CODESEARCH_MARKERS)
