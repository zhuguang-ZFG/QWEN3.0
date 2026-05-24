import json
from collections import Counter
from pathlib import Path

import pytest

import lima_fc_tools.information_tools as information_tools
import mimo_tts
import tool_dispatcher


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_TOOL_NAMES = [
    "get_weather",
    "get_air_quality",
    "get_ip_info",
    "get_exchange_rate",
    "get_holiday",
    "get_hot_search",
    "get_news",
    "translate_text",
    "get_gold_price",
    "get_oil_price",
    "get_express_tracking",
    "get_phone_info",
    "get_history_today",
    "get_idiom",
    "generate_qrcode",
    "shorten_url",
    "get_recipe",
    "get_lunar_date",
    "get_constellation",
    "get_joke",
    "get_poetry",
    "get_train_info",
    "get_random_quote",
    "get_bmi",
    "get_domain_info",
    "check_website",
    "generate_uuid",
    "hash_text",
    "encode_decode",
    "regex_test",
    "json_format",
    "get_crypto_price",
    "get_stock_price",
    "calculate",
    "convert_timezone",
    "convert_units",
    "get_random_image",
    "get_douyin_video",
    "get_music_search",
    "get_movie_top",
    "get_weibo_content",
    "text_to_pinyin",
    "word_count",
    "morse_code",
    "get_current_time",
    "random_number",
    "get_weather_forecast",
    "search_music",
    "search_cocktail",
    "get_random_poetry",
    "get_earthquake",
    "get_nasa_apod",
    "get_spacex_launch",
    "search_tv_show",
    "get_cat_fact",
    "get_random_activity",
    "get_random_dog",
    "get_astronomy",
    "get_sunrise_sunset",
    "lookup_word",
    "get_country_info",
    "get_github_user",
    "get_npm_package",
    "get_pypi_package",
    "get_trivia",
    "get_advice",
    "get_random_fact",
    "get_iss_location",
    "get_people_in_space",
    "predict_name_info",
    "get_ip_details",
]


def test_tool_schema_names_are_unique():
    names = [tool["function"]["name"] for tool in tool_dispatcher.get_tools_schema()]

    duplicates = [name for name, count in Counter(names).items() if count > 1]

    assert duplicates == []


def test_tool_schema_names_are_preserved():
    names = [tool["function"]["name"] for tool in tool_dispatcher.get_tools_schema()]

    assert names == EXPECTED_TOOL_NAMES


def test_tool_schema_text_is_ascii():
    schema_text = json.dumps(tool_dispatcher.get_tools_schema(), ensure_ascii=False)

    assert schema_text.isascii()


def test_local_tool_runtime_files_are_focused_and_ascii():
    package_dir = ROOT / "lima_fc_tools"
    runtime_files = [
        ROOT / "tool_dispatcher.py",
        ROOT / "fc_caller.py",
        ROOT / "mimo_tts.py",
    ] + sorted(package_dir.glob("*.py"))

    assert package_dir.exists()
    assert runtime_files

    for path in runtime_files:
        text = path.read_text(encoding="utf-8")
        line_count = len(text.splitlines())

        assert line_count <= 300, f"{path} has {line_count} lines"
        assert text.isascii(), f"{path} contains non-ASCII text"


@pytest.mark.asyncio
async def test_news_tool_requires_env_key_without_network(monkeypatch):
    monkeypatch.delenv("GNEWS_API_KEY", raising=False)

    async def fail_get(*_args, **_kwargs):
        raise AssertionError("network should not be called without GNEWS_API_KEY")

    monkeypatch.setattr(information_tools, "_get", fail_get)

    raw = await tool_dispatcher.execute_tool("get_news", {})
    result = json.loads(raw)

    assert result == {"error": "missing_gnews_api_key"}


@pytest.mark.asyncio
async def test_mimo_tts_requires_env_key_without_network(monkeypatch):
    monkeypatch.delenv("MIMO_TTS_KEY", raising=False)
    monkeypatch.setattr(mimo_tts, "API_KEY", "")
    called = False

    class FailClient:
        def __init__(self, *_args, **_kwargs):
            nonlocal called
            called = True
            raise AssertionError("network should not be called without MIMO_TTS_KEY")

    monkeypatch.setattr(mimo_tts.httpx, "AsyncClient", FailClient)

    assert await mimo_tts.tts("hello") is None
    assert called is False
