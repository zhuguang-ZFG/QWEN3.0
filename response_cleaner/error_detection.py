"""Backend error detection helpers for response cleaning."""

_BACKEND_ERROR_MARKERS = [
    "服务繁忙",
    "稍后重试",
    "请求频繁",
    "暂时不可用",
    "服务不可用",
    "系统繁忙",
    "请求过多",
    "限流",
    "服务器繁忙",
    "接口限流",
    "触发风控",
    "访问频率",
    "系统维护",
    "rate limit",
    "too many requests",
    "service unavailable",
    "server is busy",
    "try again later",
    "overloaded",
    "[mimo cookie",
    "[mimo http",
    "[mimo error",
    "[longcat cookie",
    "[longcat http",
    "[longcat error",
    "cookie expired",
    "cookie invalid",
]

_ERROR_CONTEXT_PREFIXES = [
    "抱歉",
    "对不起",
    "很抱歉",
    "非常抱歉",
    "sorry",
    "unfortunately",
    "apolog",
    "当前",
    "目前",
    "暂时",
    "系统",
    "rate limit",
    "service",
    "server",
    "too many",
]

_NOT_ERROR_PREFIXES = [
    "here ",
    "here's",
    "you should",
    "you can",
    "you need",
    "in order",
    "in python",
    "in this",
    "for example",
    "for this",
    "this is",
    "this function",
    "this method",
    "we can",
    "we need",
    "we should",
    "it is",
    "it works",
    "it returns",
    "if you",
    "if the",
    "the function",
    "the method",
    "the code",
    "the class",
    "the overloaded",
    "the module",
    "the api",
    "the endpoint",
    "以下",
    "你可以",
    "建议",
    "可以使用",
    "需要",
    "首先",
    "关于",
    "这是",
    "这个",
    "我来",
    "我建议",
]


def _is_backend_error(text: str) -> bool:
    """检测后端返回的错误消息（伪装成正常回答）。

    条件: 短文本 + 含错误关键词 + 不以解释性词语开头。
    """
    if not text:
        return False
    stripped = text.strip()
    if len(stripped) > 200:
        return False
    text_lower = stripped.lower()
    has_marker = any(marker in text_lower for marker in _BACKEND_ERROR_MARKERS)
    if not has_marker:
        return False
    # 以解释性词语开头 → 是技术回答，不是错误（任何长度）
    if any(text_lower.startswith(p) for p in _NOT_ERROR_PREFIXES):
        return False
    # 很短的文本(<=80字符)含错误关键词 → 几乎肯定是错误消息
    if len(stripped) <= 80:
        return True
    # 80-200字符: 以错误上下文词开头 → 是错误消息
    return any(text_lower.startswith(p) for p in _ERROR_CONTEXT_PREFIXES)
