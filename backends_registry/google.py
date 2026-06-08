"""Google AI 后端定义"""
import os

BACKENDS = {
    'google_flash_lite': {'url': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions', 'key': os.environ.get('GOOGLE_AI_KEY', ''), 'model': 'gemini-3.1-flash-lite', 'fmt': 'openai', 'timeout': 15, 'caps': ['tool_calls']},
    'google_flash': {'url': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions', 'key': os.environ.get('GOOGLE_AI_KEY', ''), 'model': 'gemini-2.5-flash', 'fmt': 'openai', 'timeout': 20, 'caps': ['tool_calls']},
    'google_pro': {'url': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions', 'key': os.environ.get('GOOGLE_AI_KEY', ''), 'model': 'gemini-2.5-pro', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},
}
