"""Kilo Code free gateway backends (no API key required).

Kilo Code provides a free API gateway for coding-optimised models.
Rate limit: ~200 req/hr. No authentication required.
"""

BACKENDS: dict[str, dict] = {
    'kilo_auto_free': {
        'url': 'https://api.kilo.ai/api/gateway/v1/chat/completions',
        'key': '',
        'model': 'kilo-auto/free',
        'fmt': 'openai',
        'timeout': 60,
        'caps': ['tool_calls'],
    },
    'kilo_laguna_m1': {
        'url': 'https://api.kilo.ai/api/gateway/v1/chat/completions',
        'key': '',
        'model': 'poolside/laguna-m.1:free',
        'fmt': 'openai',
        'timeout': 45,
        'caps': ['tool_calls', 'code'],
    },
    'kilo_stepfun_flash': {
        'url': 'https://api.kilo.ai/api/gateway/v1/chat/completions',
        'key': '',
        'model': 'stepfun/step-3.7-flash:free',
        'fmt': 'openai',
        'timeout': 60,
        'caps': ['tool_calls'],
    },
}
