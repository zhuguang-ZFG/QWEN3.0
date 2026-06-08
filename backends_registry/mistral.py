"""Mistral AI 后端定义"""
import os

BACKENDS = {
    'mistral_large': {'url': 'https://api.mistral.ai/v1/chat/completions', 'key': os.environ.get('MISTRAL_API_KEY', ''), 'model': 'mistral-large-latest', 'fmt': 'openai', 'timeout': 20, 'caps': ['tool_calls']},
    'mistral_small': {'url': 'https://api.mistral.ai/v1/chat/completions', 'key': os.environ.get('MISTRAL_API_KEY', ''), 'model': 'mistral-small-latest', 'fmt': 'openai', 'timeout': 15, 'caps': ['tool_calls']},
    'mistral_medium': {'url': 'https://api.mistral.ai/v1/chat/completions', 'key': os.environ.get('MISTRAL_API_KEY', ''), 'model': 'mistral-medium-latest', 'fmt': 'openai', 'timeout': 15, 'caps': ['tool_calls']},
    'mistral_codestral': {'url': 'https://codestral.mistral.ai/v1/chat/completions', 'key': os.environ.get('MISTRAL_API_KEY', ''), 'model': 'codestral-latest', 'fmt': 'openai', 'timeout': 15, 'caps': ['tool_calls']},
    'mistral_devstral': {'url': 'https://api.mistral.ai/v1/chat/completions', 'key': os.environ.get('MISTRAL_API_KEY', ''), 'model': 'devstral-small-latest', 'fmt': 'openai', 'timeout': 20, 'caps': ['tool_calls']},
    'mistral_pixtral': {'url': 'https://api.mistral.ai/v1/chat/completions', 'key': os.environ.get('MISTRAL_API_KEY', ''), 'model': 'pixtral-large-latest', 'fmt': 'openai', 'timeout': 20},
}
