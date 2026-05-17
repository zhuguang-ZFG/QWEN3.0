#!/usr/bin/env python3
"""
External API tools for red V1-Flash Router.
Model can call these tools when it needs real-time data.
"""

import json, urllib.request, urllib.parse

# ============================================================
# TOOL DEFINITIONS (OpenAI function calling format)
# ============================================================
TOOLS = [
    {
        "name": "search_github_issues",
        "description": "在GitHub仓库中搜索Issue，用于排查CNC/3D打印固件的问题",
        "parameters": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "仓库名，如 grbl/grbl"},
                "query": {"type": "string", "description": "搜索关键词，如 homing error"}
            }
        }
    },
    {
        "name": "get_weather",
        "description": "查询城市天气，判断CNC车间环境（湿度影响加工精度）",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名，如 shenzhen"}
            }
        }
    },
    {
        "name": "convert_currency",
        "description": "汇率转换，计算购买元器件的外币价格",
        "parameters": {
            "type": "object",
            "properties": {
                "from_currency": {"type": "string", "description": "源货币，如 USD"},
                "to_currency": {"type": "string", "description": "目标货币，如 CNY"},
                "amount": {"type": "number", "description": "金额"}
            }
        }
    },
    {
        "name": "get_exchange_rate",
        "description": "查询实时汇率，用于元器件采购比价",
        "parameters": {
            "type": "object",
            "properties": {
                "base": {"type": "string", "description": "基准货币，如 USD"}
            }
        }
    },
    {
        "name": "search_datasheet",
        "description": "搜索芯片/元器件数据手册",
        "parameters": {
            "type": "object",
            "properties": {
                "part_number": {"type": "string", "description": "型号，如 STM32F407"}
            }
        }
    },
    {
        "name": "convert_vector",
        "description": "转换矢量文件格式（SVG/DXF/EPS等）",
        "parameters": {
            "type": "object",
            "properties": {
                "from_format": {"type": "string", "description": "源格式"},
                "to_format": {"type": "string", "description": "目标格式"}
            }
        }
    },
]


# ============================================================
# TOOL IMPLEMENTATIONS
# ============================================================

def search_github_issues(repo: str, query: str) -> str:
    """Search GitHub issues."""
    url = f"https://api.github.com/search/issues?q={urllib.parse.quote(query)}+repo:{repo}+type:issue&per_page=5"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "redv1-flash"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = data.get("items", [])
            if not items:
                return f"在 {repo} 中未找到关于 '{query}' 的Issue"
            lines = []
            for i, item in enumerate(items[:5]):
                lines.append(f"#{item['number']} | {item['state']} | {item['title']} | {item['html_url']}")
            return "\n".join(lines)
    except Exception as e:
        return f"GitHub搜索失败: {e}"


def get_weather(city: str) -> str:
    """Get weather using wttr.in (free, no key)."""
    # wttr.in is free and requires no API key
    url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
    req = urllib.request.Request(url, headers={"User-Agent": "curl"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            current = data["current_condition"][0]
            return (f"城市: {city}\n"
                    f"温度: {current['temp_C']}°C\n"
                    f"湿度: {current['humidity']}%\n"
                    f"天气: {current['weatherDesc'][0]['value']}\n"
                    f"风速: {current['windspeedKmph']} km/h")
    except Exception as e:
        return f"天气查询失败: {e}"


def get_exchange_rate(base: str = "USD") -> str:
    """Get exchange rates (free, no key)."""
    url = f"https://open.er-api.com/v6/latest/{urllib.parse.quote(base)}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rates = data.get("rates", {})
            important = ["CNY", "EUR", "JPY", "TWD", "HKD"]
            lines = [f"{c}: {rates.get(c, 'N/A')}" for c in important if c in rates]
            return f"基准货币 {base}:\n" + "\n".join(lines)
    except Exception as e:
        return f"汇率查询失败: {e}"


def convert_currency(from_curr: str, to_curr: str, amount: float) -> str:
    """Convert currency."""
    url = f"https://open.er-api.com/v6/latest/{from_curr}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rate = data["rates"].get(to_curr.upper())
            if rate:
                result = amount * rate
                return f"{amount} {from_curr.upper()} = {result:.2f} {to_curr.upper()} (汇率: {rate})"
            return f"不支持 {from_curr} -> {to_curr}"
    except Exception as e:
        return f"汇率转换失败: {e}"


def search_datasheet(part_number: str) -> str:
    """Search for datasheet via Octopart or similar."""
    # Use a public search proxy
    search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(part_number + ' datasheet PDF')}"
    req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            import re
            links = re.findall(r'<a[^>]*?href="([^"]*\.pdf[^"]*)"[^>]*?>([^<]*)</a>', html)
            if links:
                return f"关于 {part_number} 的数据手册:\n" + "\n".join(f"- {text.strip()}: {href[:80]}" for href, text in links[:5])
            return f"未找到 {part_number} 的数据手册"
    except Exception as e:
        return f"搜索失败: {e}"


def convert_vector(from_fmt: str, to_fmt: str) -> str:
    """Vector format conversion info."""
    # Vector Express API is free but we provide guidance
    return (f"矢量格式转换 {from_fmt} -> {to_fmt}:\n"
            f"- 推荐工具: vpype (Python CLI, 已安装在你的环境中)\n"
            f"- 在线转换: Vector Express API (https://vector.express)\n"
            f"- 本地命令: vpype read input.{from_fmt} write output.{to_fmt}")


# ============================================================
# TOOL DISPATCHER
# ============================================================
TOOL_MAP = {
    "search_github_issues": search_github_issues,
    "get_weather": get_weather,
    "get_exchange_rate": get_exchange_rate,
    "convert_currency": convert_currency,
    "search_datasheet": search_datasheet,
    "convert_vector": convert_vector,
}


def execute_tool(tool_name: str, tool_args: dict) -> str:
    """Execute a tool and return its result."""
    func = TOOL_MAP.get(tool_name)
    if not func:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        result = func(**tool_args)
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Tool execution failed: {e}"})


# ============================================================
# TEST
# ============================================================
if __name__ == "__main__":
    print("Testing APIs...\n")

    print("1. Weather (Shenzhen):")
    print(get_weather("shenzhen"))

    print("\n2. Exchange Rate (USD):")
    print(get_exchange_rate("USD"))

    print("\n3. GitHub Issues (grbl homing):")
    print(search_github_issues("grbl/grbl", "homing error"))

    print("\n4. Datasheet (WS2812B):")
    print(search_datasheet("WS2812B"))
