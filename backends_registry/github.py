"""GitHub Models 后端定义"""
import os

BACKENDS = {
    'github_gpt4o': {'url': 'https://models.inference.ai.azure.com/chat/completions', 'key': os.environ.get('GITHUB_TOKEN', ''), 'model': 'gpt-4o', 'fmt': 'openai', 'timeout': 15, 'caps': ['tool_calls']},
    'github_gpt4o_mini': {'url': 'https://models.inference.ai.azure.com/chat/completions', 'key': os.environ.get('GITHUB_TOKEN', ''), 'model': 'gpt-4o-mini', 'fmt': 'openai', 'timeout': 15, 'caps': ['tool_calls']},
    'github_gpt5': {'url': 'https://models.inference.ai.azure.com/chat/completions', 'key': os.environ.get('GITHUB_TOKEN', ''), 'model': 'gpt-5', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},
    'github_o3_mini': {'url': 'https://models.inference.ai.azure.com/chat/completions', 'key': os.environ.get('GITHUB_TOKEN', ''), 'model': 'o3-mini', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},
    'github_o4_mini': {'url': 'https://models.inference.ai.azure.com/chat/completions', 'key': os.environ.get('GITHUB_TOKEN', ''), 'model': 'o4-mini', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},
    'github_deepseek_r1': {'url': 'https://models.inference.ai.azure.com/chat/completions', 'key': os.environ.get('GITHUB_TOKEN', ''), 'model': 'DeepSeek-R1', 'fmt': 'openai', 'timeout': 60},
    'github_codellama': {'url': 'https://models.inference.ai.azure.com/chat/completions', 'key': os.environ.get('GITHUB_TOKEN', ''), 'model': 'CodeLlama-70b-Instruct-hf', 'fmt': 'openai', 'timeout': 30, 'caps': ['tool_calls']},
    'github_starcoder2': {'url': 'https://models.inference.ai.azure.com/chat/completions', 'key': os.environ.get('GITHUB_TOKEN', ''), 'model': 'starcoder2-15b', 'fmt': 'openai', 'timeout': 20, 'caps': ['tool_calls']},
    'github_llama70b': {'url': 'https://models.inference.ai.azure.com/chat/completions', 'key': os.environ.get('GITHUB_TOKEN', ''), 'model': 'Llama-3.3-70B-Instruct', 'fmt': 'openai', 'timeout': 15},
    'github_codestral': {'url': 'https://models.inference.ai.azure.com/chat/completions', 'key': os.environ.get('GITHUB_TOKEN', ''), 'model': 'Codestral-2501', 'fmt': 'openai', 'timeout': 15, 'caps': ['tool_calls']},
}
