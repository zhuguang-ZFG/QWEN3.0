"""VPS 代理后端定义（Kimi、MiMo、SCNet Large、LongCat Web）"""
import os

BACKENDS = {
    # ── LongCat (已于 2026-05-29 下线官方端点，保留 VPS 代理) ──
    'longcat': {'url': 'https://api.longcat.chat/anthropic/v1/messages', 'key': os.environ.get('LONGCAT_API_KEY', ''), 'model': 'LongCat-2.0-Preview', 'fmt': 'anthropic', 'auth': 'bearer', 'caps': ['tool_calls']},
    'longcat_lite': {'url': 'https://api.longcat.chat/anthropic/v1/messages', 'key': os.environ.get('LONGCAT_API_KEY', ''), 'model': 'LongCat-2.0-Preview', 'fmt': 'anthropic', 'auth': 'bearer', 'caps': ['tool_calls'], 'alias_for': 'longcat'},
    'longcat_openai': {'url': 'https://api.longcat.chat/openai/v1/chat/completions', 'key': os.environ.get('LONGCAT_API_KEY', ''), 'model': 'LongCat-2.0-Preview', 'fmt': 'openai', 'timeout': 90, 'caps': ['tool_calls']},
    'longcat_web': {'url': 'http://localhost:4506/v1/chat/completions', 'key': 'local', 'model': 'longcat-web', 'fmt': 'openai', 'timeout': 60, 'force_stream_param': True, 'admission': 'code_floor_candidate', 'private_code_allowed': True},
    'longcat_web_think': {'url': 'http://localhost:4506/v1/chat/completions', 'key': 'local', 'model': 'longcat-web-think', 'fmt': 'openai', 'timeout': 120, 'force_stream_param': True},
    'longcat_web_research': {'url': 'http://localhost:4506/v1/chat/completions', 'key': 'local', 'model': 'longcat-web-research', 'fmt': 'openai', 'timeout': 180, 'force_stream_param': True},

    # ── Kimi (moonshot.cn VPS 代理, K2.6 模型, 3 种模式) ──
    'kimi': {'url': 'http://localhost:4504/v1/chat/completions', 'key': 'none', 'model': 'kimi', 'fmt': 'openai', 'timeout': 45, 'private_code_allowed': True, 'admission': 'code_medium_candidate', 'caps': ['tool_calls']},
    'kimi_thinking': {'url': 'http://localhost:4504/v1/chat/completions', 'key': 'none', 'model': 'kimi-thinking', 'fmt': 'openai', 'timeout': 45, 'private_code_allowed': True, 'admission': 'code_medium_candidate', 'caps': ['tool_calls']},
    'kimi_search': {'url': 'http://localhost:4504/v1/chat/completions', 'key': 'none', 'model': 'kimi-search', 'fmt': 'openai', 'timeout': 60, 'private_code_allowed': True, 'admission': 'code_medium_candidate'},

    # ── MiMo Web (VPS 代理, 网页逆向) ──
    'mimo_web': {'url': f"http://{os.environ.get('VPS_HOST', '47.112.162.80')}:4507/v1/chat/completions", 'key': 'none', 'model': 'mimo-web', 'fmt': 'openai', 'timeout': 60, 'force_stream_param': True, 'admission': 'sandbox_only', 'private_code_allowed': False, 'caps': ['tool_calls']},
    'mimo_web_think': {'url': f"http://{os.environ.get('VPS_HOST', '47.112.162.80')}:4507/v1/chat/completions", 'key': 'none', 'model': 'mimo-web-think', 'fmt': 'openai', 'timeout': 120, 'force_stream_param': True, 'admission': 'sandbox_only', 'private_code_allowed': False, 'caps': ['tool_calls']},
    'mimo_web_flash': {'url': f"http://{os.environ.get('VPS_HOST', '47.112.162.80')}:4507/v1/chat/completions", 'key': 'none', 'model': 'mimo-web-flash', 'fmt': 'openai', 'timeout': 30, 'force_stream_param': True, 'admission': 'sandbox_only', 'private_code_allowed': False, 'caps': ['tool_calls']},

    # ── MiMo TTS (官方 API, 限时免费) ──
    'mimo_tts': {'url': 'https://api.xiaomimimo.com/v1/chat/completions', 'key': os.environ.get('MIMO_TTS_KEY', ''), 'model': 'mimo-v2.5-tts', 'fmt': 'openai', 'timeout': 30},
    'mimo_tts_v2': {'url': 'https://api.xiaomimimo.com/v1/chat/completions', 'key': os.environ.get('MIMO_TTS_KEY', ''), 'model': 'mimo-v2-tts', 'fmt': 'openai', 'timeout': 30},
    # MiMo STT (voice input via chat/completions, not routing pool)
    'mimo_stt': {'url': 'https://api.xiaomimimo.com/v1/chat/completions', 'key': os.environ.get('MIMO_TTS_KEY', ''), 'model': 'mimo-v2-omni', 'fmt': 'openai', 'timeout': 45},

    # ── MiMo v2 Pro (Token Plan, 38B tokens) ──
    'mimo_v2_pro': {'url': 'https://token-plan-cn.xiaomimimo.com/v1/chat/completions', 'key': os.environ.get('MIMO_V2_PRO_KEY', ''), 'model': 'mimo-v2-pro', 'fmt': 'openai', 'timeout': 30, 'force_stream_param': True, 'caps': ['tool_calls']},
    'mimo_v2_5_pro': {'url': 'https://token-plan-cn.xiaomimimo.com/v1/chat/completions', 'key': os.environ.get('MIMO_V2_PRO_KEY', ''), 'model': 'mimo-v2.5-pro', 'fmt': 'openai', 'timeout': 30, 'force_stream_param': True, 'caps': ['tool_calls']},
    'mimo_v2_5': {'url': 'https://token-plan-cn.xiaomimimo.com/v1/chat/completions', 'key': os.environ.get('MIMO_V2_PRO_KEY', ''), 'model': 'mimo-v2.5', 'fmt': 'openai', 'timeout': 30, 'force_stream_param': True, 'caps': ['tool_calls']},
    'mimo_v2_omni': {'url': 'https://token-plan-cn.xiaomimimo.com/v1/chat/completions', 'key': os.environ.get('MIMO_V2_PRO_KEY', ''), 'model': 'mimo-v2-omni', 'fmt': 'openai', 'timeout': 30, 'force_stream_param': True, 'caps': ['tool_calls']},
    'mimo_v2_pro_anthropic': {'url': 'https://token-plan-cn.xiaomimimo.com/anthropic/v1/messages', 'key': os.environ.get('MIMO_V2_PRO_KEY', ''), 'model': 'mimo-v2-pro', 'fmt': 'anthropic', 'auth': 'x-api-key', 'timeout': 30, 'caps': ['tool_calls']},

    # ── SCNet Large (VPS 代理, 大上下文, 文件上传) ──
    'scnet_large_ds_flash': {'url': 'http://localhost:4505/v1/chat/completions', 'key': 'none', 'model': 'deepseek-v4-flash', 'fmt': 'openai', 'timeout': 60, 'admission': 'code_medium_candidate', 'private_code_allowed': True, 'caps': ['tool_calls']},
    'scnet_large_ds_pro': {'url': 'http://localhost:4505/v1/chat/completions', 'key': 'none', 'model': 'deepseek-v4-pro', 'fmt': 'openai', 'timeout': 90, 'caps': ['tool_calls']},
}
