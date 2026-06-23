"""Central brand, identity, and capability configuration for LiMa prompts and replies.

Values can be overridden via environment variables to avoid hard-coding
brand details across prompt strings and identity guard answers.
"""

from config.settings import BRAND

# ── Identity ─────────────────────────────────────────────────────────────────
PUBLIC_MODEL_NAME = BRAND.public_model_name
PUBLIC_MODEL_NAME_CN = BRAND.public_model_name_cn

COMPANY_NAME_CN = BRAND.company_name_cn
COMPANY_NAME_EN = BRAND.company_name_en
COMPANY_SHORT_CN = BRAND.company_short_cn

# ── HTTP User-Agent ───────────────────────────────────────────────────────────
USER_AGENT = BRAND.user_agent

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
    "realtime": "Internet access: real-time weather, news, trends, exchange rates, stocks, earthquakes",
    "programming": f"Programming: {', '.join(_PROGRAMMING_LANGUAGES)} and more",
    "voice": "Voice: speech-to-text and text-to-speech",
    "translation": "Translation: Chinese, English, Japanese, Korean, French, German",
    "tools": "Tools: calculator, unit conversion, QR codes, URL shortening",
}

CAPABILITY_SUMMARY_CN = "、".join(["天气", "新闻", "汇率", "热搜", "股票"]) + "等信息"
CAPABILITY_SUMMARY_EN = "weather, news, exchange rates, stocks, and more"
