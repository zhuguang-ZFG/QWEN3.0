"""社区免费 API 后端定义（free_* 系列）"""
import os

BACKENDS = {
    # ── free_openai_next (社区分享, 500刀额度) ──
    'free_openai_next_gpt4': {'url': 'https://api.openai-next.com/v1/chat/completions', 'key': os.environ.get('FREE_OPENAI_NEXT_KEY', ''), 'model': 'gpt-4', 'fmt': 'openai', 'timeout': 60, 'caps': ['tool_calls'], 'headers': {'User-Agent': 'Mozilla/5.0'}},
    'free_openai_next_claude': {'url': 'https://api.openai-next.com/v1/chat/completions', 'key': os.environ.get('FREE_OPENAI_NEXT_KEY', ''), 'model': 'claude-3-5-sonnet-20241022', 'fmt': 'openai', 'timeout': 60, 'caps': ['tool_calls'], 'headers': {'User-Agent': 'Mozilla/5.0'}},
    'free_openai_next_deepseek': {'url': 'https://api.openai-next.com/v1/chat/completions', 'key': os.environ.get('FREE_OPENAI_NEXT_KEY', ''), 'model': 'deepseek-r1', 'fmt': 'openai', 'timeout': 90, 'headers': {'User-Agent': 'Mozilla/5.0'}},

    # ── free_centos (ai.centos.hk) ──
    'free_centos_gpt54': {'url': 'https://ai.centos.hk/v1/chat/completions', 'key': os.environ.get('FREE_CENTOS_KEY', ''), 'model': 'gpt-5.4', 'fmt': 'openai', 'timeout': 60, 'caps': ['tool_calls'], 'headers': {'User-Agent': 'Mozilla/5.0'}},
    'free_centos_gpt55': {'url': 'https://ai.centos.hk/v1/chat/completions', 'key': os.environ.get('FREE_CENTOS_KEY', ''), 'model': 'gpt-5.5', 'fmt': 'openai', 'timeout': 90, 'caps': ['tool_calls'], 'headers': {'User-Agent': 'Mozilla/5.0'}},

    # ── free_muyuan (muyuan.do, 同 centos.hk 服务) ──
    'free_muyuan_gpt54': {'url': 'https://muyuan.do/v1/chat/completions', 'key': os.environ.get('FREE_MUYUAN_KEY', ''), 'model': 'gpt-5.4', 'fmt': 'openai', 'timeout': 60, 'caps': ['tool_calls'], 'headers': {'User-Agent': 'Mozilla/5.0'}},
    'free_muyuan_gpt55': {'url': 'https://muyuan.do/v1/chat/completions', 'key': os.environ.get('FREE_MUYUAN_KEY', ''), 'model': 'gpt-5.5', 'fmt': 'openai', 'timeout': 90, 'caps': ['tool_calls'], 'headers': {'User-Agent': 'Mozilla/5.0'}},
    'free_muyuan_gpt54_mini': {'url': 'https://muyuan.do/v1/chat/completions', 'key': os.environ.get('FREE_MUYUAN_KEY', ''), 'model': 'gpt-5.4-mini', 'fmt': 'openai', 'timeout': 30, 'headers': {'User-Agent': 'Mozilla/5.0'}},
    'free_muyuan_codex': {'url': 'https://muyuan.do/v1/chat/completions', 'key': os.environ.get('FREE_MUYUAN_KEY', ''), 'model': 'codex-auto-review', 'fmt': 'openai', 'timeout': 60, 'caps': ['tool_calls'], 'headers': {'User-Agent': 'Mozilla/5.0'}},
    'free_muyuan_gpt55_compact': {'url': 'https://muyuan.do/v1/chat/completions', 'key': os.environ.get('FREE_MUYUAN_KEY', ''), 'model': 'gpt-5.5-openai-compact', 'fmt': 'openai', 'timeout': 60, 'headers': {'User-Agent': 'Mozilla/5.0'}},
    'free_muyuan_gpt54_compact': {'url': 'https://muyuan.do/v1/chat/completions', 'key': os.environ.get('FREE_MUYUAN_KEY', ''), 'model': 'gpt-5.4-openai-compact', 'fmt': 'openai', 'timeout': 60, 'headers': {'User-Agent': 'Mozilla/5.0'}},

    # ── free_ajiakesi (codehub.ajiakesi.cn) ──
    'free_ajiakesi_gpt54': {'url': 'http://codehub.ajiakesi.cn/v1/chat/completions', 'key': os.environ.get('FREE_AJIAKESI_KEY', ''), 'model': 'gpt-5.4', 'fmt': 'openai', 'timeout': 60, 'caps': ['tool_calls'], 'headers': {'User-Agent': 'Mozilla/5.0'}},
    'free_ajiakesi_gpt55': {'url': 'http://codehub.ajiakesi.cn/v1/chat/completions', 'key': os.environ.get('FREE_AJIAKESI_KEY', ''), 'model': 'gpt-5.5', 'fmt': 'openai', 'timeout': 90, 'caps': ['tool_calls'], 'headers': {'User-Agent': 'Mozilla/5.0'}},
    'free_ajiakesi_gpt54_mini': {'url': 'http://codehub.ajiakesi.cn/v1/chat/completions', 'key': os.environ.get('FREE_AJIAKESI_KEY', ''), 'model': 'gpt-5.4-mini', 'fmt': 'openai', 'timeout': 30, 'headers': {'User-Agent': 'Mozilla/5.0'}},
    'free_ajiakesi_gpt55_compact': {'url': 'http://codehub.ajiakesi.cn/v1/chat/completions', 'key': os.environ.get('FREE_AJIAKESI_KEY', ''), 'model': 'gpt-5.5-openai-compact', 'fmt': 'openai', 'timeout': 60, 'headers': {'User-Agent': 'Mozilla/5.0'}},

    # ── free_team_speed (Team 速登, ChatGPT Team 账号) ──
    'free_team_speed_gpt55': {'url': 'http://156.239.47.88:8080/v1/chat/completions', 'key': os.environ.get('FREE_TEAM_SPEED_KEY', ''), 'model': 'gpt-5.5', 'fmt': 'openai', 'timeout': 90, 'caps': ['tool_calls'], 'headers': {'User-Agent': 'Mozilla/5.0'}},
    'free_team_speed_gpt54_mini': {'url': 'http://156.239.47.88:8080/v1/chat/completions', 'key': os.environ.get('FREE_TEAM_SPEED_KEY', ''), 'model': 'gpt-5.4-mini', 'fmt': 'openai', 'timeout': 30, 'headers': {'User-Agent': 'Mozilla/5.0'}},
}
