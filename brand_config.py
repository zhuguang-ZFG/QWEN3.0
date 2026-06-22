"""Central brand, identity, and capability configuration for LiMa prompts and replies.

Values can be overridden via environment variables to avoid hard-coding
brand details across prompt strings and identity guard answers.
"""

import os

# ── Identity ─────────────────────────────────────────────────────────────────
PUBLIC_MODEL_NAME = os.environ.get("PUBLIC_MODEL_NAME", "LiMa")
PUBLIC_MODEL_NAME_CN = os.environ.get("PUBLIC_MODEL_NAME_CN", "力码")

COMPANY_NAME_CN = os.environ.get("COMPANY_NAME_CN", "深圳市动力巢科技有限公司")
COMPANY_NAME_EN = os.environ.get("COMPANY_NAME_EN", "DongLiCao Technology (Shenzhen)")
COMPANY_SHORT_CN = os.environ.get("COMPANY_SHORT_CN", "动力巢科技")

# ── HTTP User-Agent ───────────────────────────────────────────────────────────
USER_AGENT = os.environ.get("LIMA_USER_AGENT", "LiMa/2.0")

# ── Capability statements ────────────────────────────────────────────────────
# Used by identity_guard and prompt role layers. Keep in sync with actual tools.
_REALTIME_TOOLS = ["天气", "新闻", "热搜", "汇率", "股票", "快递", "地震"]
_PROGRAMMING_LANGUAGES = ["Python", "JavaScript", "Go", "Rust", "C/C++"]
_TRANSLATION_LANGUAGES = ["中英日韩法德"]
_UTILITY_TOOLS = ["计算", "单位换算", "二维码", "短链接"]

CAPABILITY_BULLETS_CN = {
    "realtime": f"联网查询：{', '.join(_REALTIME_TOOLS)}等实时数据",
    "programming": f"编程开发：{', '.join(_PROGRAMMING_LANGUAGES)} 等",
    "voice": "语音交互：语音转文字、文字转语音",
    "translation": f"翻译：支持{_TRANSLATION_LANGUAGES[0]}等多语言",
    "tools": f"工具调用：{', '.join(_UTILITY_TOOLS)}等",
}

CAPABILITY_BULLETS_EN = {
    "realtime": f"Internet access: real-time weather, news, trends, exchange rates, stocks, earthquakes",
    "programming": f"Programming: {', '.join(_PROGRAMMING_LANGUAGES)} and more",
    "voice": "Voice: speech-to-text and text-to-speech",
    "translation": "Translation: Chinese, English, Japanese, Korean, French, German",
    "tools": "Tools: calculator, unit conversion, QR codes, URL shortening",
}

CAPABILITY_SUMMARY_CN = "、".join(["天气", "新闻", "汇率", "热搜", "股票"]) + "等信息"
CAPABILITY_SUMMARY_EN = "weather, news, exchange rates, stocks, and more"
