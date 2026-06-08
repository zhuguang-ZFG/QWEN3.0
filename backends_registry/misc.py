"""杂项后端定义（local、hermes_agent 等）"""
import os

# LM_URL 从 __init__.py 导入
BACKENDS = {
    'local': {'url': 'http://localhost:1234/v1/chat/completions', 'key': '', 'model': 'local-model', 'fmt': 'openai', 'auth': 'bearer'},
    'hermes_agent': {'url': 'http://127.0.0.1:8699/v1/chat/completions', 'key': 'none', 'model': 'hermes-agent', 'fmt': 'openai', 'timeout': 120, 'caps': ['tool_calls']},
}
