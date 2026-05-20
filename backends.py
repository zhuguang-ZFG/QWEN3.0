"""LiMa backend definitions -- model registry, routing table, and auto-detection helpers."""
import os, sys
from dotenv import load_dotenv
load_dotenv()

LM_URL = 'http://localhost:1234/v1/chat/completions'

BACKENDS = {
    'claude': {
        'url': 'https://right.codes/claude-aws/v1/messages',
        'key': 'sk-8838ce42deaf4d8e82c7f364cf6d963e',
        'model': 'claude-sonnet-4-6',
        'fmt': 'anthropic',
        'auth': 'x-api-key',
    },
    'longcat_lite': {
        'url': 'https://api.longcat.chat/anthropic/v1/messages',
        'key': 'ak_2Ra7Py0fN6PT3Ul5Dj8OZ0D88iY2Q',
        'model': 'LongCat-Flash-Lite',
        'fmt': 'anthropic',
        'auth': 'bearer',
    },
    'longcat_chat': {
        'url': 'https://api.longcat.chat/anthropic/v1/messages',
        'key': 'ak_2Ra7Py0fN6PT3Ul5Dj8OZ0D88iY2Q',
        'model': 'LongCat-Flash-Chat',
        'fmt': 'anthropic',
        'auth': 'bearer',
    },
    'longcat_thinking': {
        'url': 'https://api.longcat.chat/anthropic/v1/messages',
        'key': 'ak_2Ra7Py0fN6PT3Ul5Dj8OZ0D88iY2Q',
        'model': 'LongCat-Flash-Thinking-2601',
        'fmt': 'anthropic',
        'auth': 'bearer',
    },
    'longcat_omni': {
        'url': 'https://api.longcat.chat/anthropic/v1/messages',
        'key': 'ak_2Ra7Py0fN6PT3Ul5Dj8OZ0D88iY2Q',
        'model': 'LongCat-Flash-Omni-2603',
        'fmt': 'anthropic',
        'auth': 'bearer',
        'no_system': True,
    },
    'longcat': {
        'url': 'https://api.longcat.chat/anthropic/v1/messages',
        'key': 'ak_2Ra7Py0fN6PT3Ul5Dj8OZ0D88iY2Q',
        'model': 'LongCat-2.0-Preview',
        'fmt': 'anthropic',
        'auth': 'bearer',
    },
    'deepseek_pro': {
        'url': 'https://api.deepseek.com/anthropic/v1/messages',
        'key': 'sk-639fd931aa1846318b6ff12704ee98ec',
        'model': 'deepseek-v4-pro',
        'fmt': 'anthropic',
    },
    'deepseek_flash': {
        'url': 'https://api.deepseek.com/anthropic/v1/messages',
        'key': 'sk-639fd931aa1846318b6ff12704ee98ec',
        'model': 'deepseek-v4-flash',
        'fmt': 'anthropic',
    },
    'nvidia_nemotron': {
        'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
        'key': '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',
        'model': 'nvidia/llama-3.3-nemotron-super-49b-v1',
        'fmt': 'openai',
    },
    'nvidia_llama70b': {
        'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
        'key': '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',
        'model': 'meta/llama-3.3-70b-instruct',
        'fmt': 'openai',
    },
    'nvidia_qwen_coder': {
        'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
        'key': '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',
        'model': 'qwen/qwen3-coder-480b-a35b-instruct',
        'fmt': 'openai',
    },
    'nvidia_llama4': {
        'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
        'key': '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',
        'model': 'meta/llama-4-maverick-17b-128e-instruct',
        'fmt': 'openai',
    },
    'nvidia_mistral': {
        'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
        'key': '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',
        'model': 'mistralai/mistral-large-3-675b-instruct-2512',
        'fmt': 'openai',
    },
    'nvidia_phi4': {
        'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
        'key': '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',
        'model': 'microsoft/phi-4-mini-instruct',
        'fmt': 'openai',
    },
    'chinamobile': {
        'url': 'https://maas.gd.chinamobile.com:36007/ai/uifm/open/v1/chat/completions',
        'key': 'sk-OHBZecLa0FtcjjSVnVRI5fhHohnNAV3mldYjSGBwXBR3H',
        'model': 'minimax-m25',
        'fmt': 'openai',
    },
    'or_deepseek_r1': {
        'url': 'https://openrouter.ai/api/v1/chat/completions',
        'key': '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',
        'model': 'deepseek/deepseek-v4-flash:free',
        'fmt': 'openai',
        'timeout': 60,
    },
    'or_qwen3_coder': {
        'url': 'https://openrouter.ai/api/v1/chat/completions',
        'key': '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',
        'model': 'qwen/qwen3-coder:free',
        'fmt': 'openai',
        'timeout': 60,
    },
    'or_llama70b': {
        'url': 'https://openrouter.ai/api/v1/chat/completions',
        'key': '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',
        'model': 'meta-llama/llama-3.3-70b-instruct:free',
        'fmt': 'openai',
        'timeout': 45,
    },
    'or_nemotron': {
        'url': 'https://openrouter.ai/api/v1/chat/completions',
        'key': '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',
        'model': 'nvidia/llama-3.3-nemotron-super-49b-v1:free',
        'fmt': 'openai',
        'timeout': 60,
    },
    'or_qwen3_80b': {
        'url': 'https://openrouter.ai/api/v1/chat/completions',
        'key': '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',
        'model': 'qwen/qwen3-next-80b-a3b-instruct:free',
        'fmt': 'openai',
        'timeout': 30,
    },
    'or_nemotron120b': {
        'url': 'https://openrouter.ai/api/v1/chat/completions',
        'key': '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',
        'model': 'nvidia/nemotron-3-super-120b-a12b:free',
        'fmt': 'openai',
        'timeout': 60,
    },
    'or_gptoss_120b': {
        'url': 'https://openrouter.ai/api/v1/chat/completions',
        'key': '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',
        'model': 'openai/gpt-oss-120b:free',
        'fmt': 'openai',
        'timeout': 60,
    },
    'or_glm45': {
        'url': 'https://openrouter.ai/api/v1/chat/completions',
        'key': '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',
        'model': 'z-ai/glm-4.5-air:free',
        'fmt': 'openai',
        'timeout': 30,
    },
    'or_minimax': {
        'url': 'https://openrouter.ai/api/v1/chat/completions',
        'key': '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',
        'model': 'minimax/minimax-m2.5:free',
        'fmt': 'openai',
        'timeout': 30,
    },
    'or_gemma4': {
        'url': 'https://openrouter.ai/api/v1/chat/completions',
        'key': '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',
        'model': 'google/gemma-4-31b-it:free',
        'fmt': 'openai',
        'timeout': 30,
    },
    'unclose_hermes': {
        'url': 'https://hermes.ai.unturf.com/v1/chat/completions',
        'key': 'none',
        'model': 'adamo1139/Hermes-3-Llama-3.1-8B-FP8-Dynamic',
        'fmt': 'openai',
        'timeout': 15,
    },
    'unclose_qwen': {
        'url': 'https://qwen.ai.unturf.com/v1/chat/completions',
        'key': 'none',
        'model': 'Qwen3.6-27B-UD-Q4_K_XL.gguf',
        'fmt': 'openai',
        'timeout': 30,
    },
    'groq_llama70b': {
        'url': 'https://api.groq.com/openai/v1/chat/completions',
        'key': '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',
        'model': 'llama-3.3-70b-versatile',
        'fmt': 'openai',
        'timeout': 15,
    },
    'groq_gptoss': {
        'url': 'https://api.groq.com/openai/v1/chat/completions',
        'key': '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',
        'model': 'openai/gpt-oss-120b',
        'fmt': 'openai',
        'timeout': 15,
    },
    'groq_gptoss_20b': {
        'url': 'https://api.groq.com/openai/v1/chat/completions',
        'key': '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',
        'model': 'openai/gpt-oss-20b',
        'fmt': 'openai',
        'timeout': 10,
    },
    'groq_qwen32b': {
        'url': 'https://api.groq.com/openai/v1/chat/completions',
        'key': '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',
        'model': 'qwen/qwen3-32b',
        'fmt': 'openai',
        'timeout': 15,
    },
    'groq_llama4': {
        'url': 'https://api.groq.com/openai/v1/chat/completions',
        'key': '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',
        'model': 'meta-llama/llama-4-scout-17b-16e-instruct',
        'fmt': 'openai',
        'timeout': 15,
    },
    'groq_llama8b': {
        'url': 'https://api.groq.com/openai/v1/chat/completions',
        'key': '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',
        'model': 'llama-3.1-8b-instant',
        'fmt': 'openai',
        'timeout': 10,
    },
    'cerebras_qwen235b': {
        'url': 'https://api.cerebras.ai/v1/chat/completions',
        'key': 'csk-2r6wt6hwr2phk5n3effx28cc624kdwvve9kfthtfdm9c42x3',
        'model': 'qwen-3-235b-a22b-instruct-2507',
        'fmt': 'openai',
        'timeout': 30,
    },
    'cerebras_llama8b': {
        'url': 'https://api.cerebras.ai/v1/chat/completions',
        'key': 'csk-2r6wt6hwr2phk5n3effx28cc624kdwvve9kfthtfdm9c42x3',
        'model': 'llama3.1-8b',
        'fmt': 'openai',
        'timeout': 15,
    },
    'cerebras_gptoss': {
        'url': 'https://api.cerebras.ai/v1/chat/completions',
        'key': 'csk-2r6wt6hwr2phk5n3effx28cc624kdwvve9kfthtfdm9c42x3',
        'model': 'gpt-oss-120b',
        'fmt': 'openai',
        'timeout': 20,
    },
    'github_gpt4o': {
        'url': 'https://models.inference.ai.azure.com/chat/completions',
        'key': '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',
        'model': 'gpt-4o',
        'fmt': 'openai',
        'timeout': 15,
    },
    'github_gpt4o_mini': {
        'url': 'https://models.inference.ai.azure.com/chat/completions',
        'key': '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',
        'model': 'gpt-4o-mini',
        'fmt': 'openai',
        'timeout': 15,
    },
    'github_gpt5': {
        'url': 'https://models.inference.ai.azure.com/chat/completions',
        'key': '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',
        'model': 'gpt-5',
        'fmt': 'openai',
        'timeout': 30,
    },
    'github_o3_mini': {
        'url': 'https://models.inference.ai.azure.com/chat/completions',
        'key': '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',
        'model': 'o3-mini',
        'fmt': 'openai',
        'timeout': 30,
    },
    'github_o4_mini': {
        'url': 'https://models.inference.ai.azure.com/chat/completions',
        'key': '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',
        'model': 'o4-mini',
        'fmt': 'openai',
        'timeout': 30,
    },
    'github_deepseek_r1': {
        'url': 'https://models.inference.ai.azure.com/chat/completions',
        'key': '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',
        'model': 'DeepSeek-R1',
        'fmt': 'openai',
        'timeout': 60,
    },
    'github_llama70b': {
        'url': 'https://models.inference.ai.azure.com/chat/completions',
        'key': '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',
        'model': 'Llama-3.3-70B-Instruct',
        'fmt': 'openai',
        'timeout': 15,
    },
    'github_codestral': {
        'url': 'https://models.inference.ai.azure.com/chat/completions',
        'key': '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',
        'model': 'Codestral-2501',
        'fmt': 'openai',
        'timeout': 15,
    },
    'google_flash_lite': {
        'url': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
        'key': 'AIzaSyDF4BJhyIC2e6QIcSUXbDNDZs90ZaTvoQI',
        'model': 'gemini-3.1-flash-lite',
        'fmt': 'openai',
        'timeout': 15,
    },
    'google_flash': {
        'url': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
        'key': 'AIzaSyDF4BJhyIC2e6QIcSUXbDNDZs90ZaTvoQI',
        'model': 'gemini-2.5-flash',
        'fmt': 'openai',
        'timeout': 20,
    },
    'google_gemini3': {
        'url': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
        'key': 'AIzaSyDF4BJhyIC2e6QIcSUXbDNDZs90ZaTvoQI',
        'model': 'gemini-3-flash',
        'fmt': 'openai',
        'timeout': 20,
    },
    'google_gemma4': {
        'url': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
        'key': 'AIzaSyDF4BJhyIC2e6QIcSUXbDNDZs90ZaTvoQI',
        'model': 'gemma-3-27b-it',
        'fmt': 'openai',
        'timeout': 15,
    },
    'cf_llama70b': {
        'url': 'https://api.cloudflare.com/client/v4/accounts/3e8dfc378deaf1a6f39fda85ceaca32b/ai/v1/chat/completions',
        'key': 'cfut_de3IJemNLIVZMm6MCoWN7WUnbDIa8k1LoURbvjBc09dd9840',
        'model': '@cf/meta/llama-3.3-70b-instruct-fp8-fast',
        'fmt': 'openai',
        'timeout': 15,
    },
    'cf_llama4': {
        'url': 'https://api.cloudflare.com/client/v4/accounts/3e8dfc378deaf1a6f39fda85ceaca32b/ai/v1/chat/completions',
        'key': 'cfut_de3IJemNLIVZMm6MCoWN7WUnbDIa8k1LoURbvjBc09dd9840',
        'model': '@cf/meta/llama-4-scout-17b-16e-instruct',
        'fmt': 'openai',
        'timeout': 15,
    },
    'cf_qwen_coder': {
        'url': 'https://api.cloudflare.com/client/v4/accounts/3e8dfc378deaf1a6f39fda85ceaca32b/ai/v1/chat/completions',
        'key': 'cfut_de3IJemNLIVZMm6MCoWN7WUnbDIa8k1LoURbvjBc09dd9840',
        'model': '@cf/qwen/qwen2.5-coder-32b-instruct',
        'fmt': 'openai',
        'timeout': 15,
    },
    'cf_mistral': {
        'url': 'https://api.cloudflare.com/client/v4/accounts/3e8dfc378deaf1a6f39fda85ceaca32b/ai/v1/chat/completions',
        'key': 'cfut_de3IJemNLIVZMm6MCoWN7WUnbDIa8k1LoURbvjBc09dd9840',
        'model': '@cf/mistralai/mistral-small-3.1-24b-instruct',
        'fmt': 'openai',
        'timeout': 15,
    },
    'cf_vision': {
        'url': 'https://api.cloudflare.com/client/v4/accounts/3e8dfc378deaf1a6f39fda85ceaca32b/ai/v1/chat/completions',
        'key': 'cfut_de3IJemNLIVZMm6MCoWN7WUnbDIa8k1LoURbvjBc09dd9840',
        'model': '@cf/meta/llama-3.2-11b-vision-instruct',
        'fmt': 'openai',
        'timeout': 15,
    },
    'mistral_large': {
        'url': 'https://api.mistral.ai/v1/chat/completions',
        'key': 'ERkNT70M5PsCKCUQGs6rEPu2qc47xyTg',
        'model': 'mistral-large-latest',
        'fmt': 'openai',
        'timeout': 20,
    },
    'mistral_small': {
        'url': 'https://api.mistral.ai/v1/chat/completions',
        'key': 'ERkNT70M5PsCKCUQGs6rEPu2qc47xyTg',
        'model': 'mistral-small-latest',
        'fmt': 'openai',
        'timeout': 15,
    },
    'mistral_medium': {
        'url': 'https://api.mistral.ai/v1/chat/completions',
        'key': 'ERkNT70M5PsCKCUQGs6rEPu2qc47xyTg',
        'model': 'mistral-medium-latest',
        'fmt': 'openai',
        'timeout': 15,
    },
    'mistral_codestral': {
        'url': 'https://codestral.mistral.ai/v1/chat/completions',
        'key': 'ERkNT70M5PsCKCUQGs6rEPu2qc47xyTg',
        'model': 'codestral-latest',
        'fmt': 'openai',
        'timeout': 15,
    },
    'mistral_devstral': {
        'url': 'https://api.mistral.ai/v1/chat/completions',
        'key': 'ERkNT70M5PsCKCUQGs6rEPu2qc47xyTg',
        'model': 'devstral-small-latest',
        'fmt': 'openai',
        'timeout': 20,
    },
    'mistral_pixtral': {
        'url': 'https://api.mistral.ai/v1/chat/completions',
        'key': 'ERkNT70M5PsCKCUQGs6rEPu2qc47xyTg',
        'model': 'pixtral-large-latest',
        'fmt': 'openai',
        'timeout': 20,
    },
    'local': {
        'url': 'http://localhost:1234/v1/chat/completions',
        'key': '',
        'model': 'local-model',
        'fmt': 'openai',
        'auth': 'bearer',
    },
    'zhipu_flash': {
        'url': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
        'key': 'b1507e110d3c493ebcc7fa819e8515a3.5I7IiGIFJ4tJYhbR',
        'model': 'glm-4-flash',
        'fmt': 'openai',
        'timeout': 10,
    },
    'zhipu_flash7': {
        'url': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
        'key': 'b1507e110d3c493ebcc7fa819e8515a3.5I7IiGIFJ4tJYhbR',
        'model': 'glm-4.7-flash',
        'fmt': 'openai',
        'timeout': 10,
    },
    'silicon_qwen8b': {
        'url': 'https://api.siliconflow.cn/v1/chat/completions',
        'key': 'sk-owrkbtvlwvzxcgpoehnminlrszmjyksuqarusjhlnnaormop',
        'model': 'Qwen/Qwen3-8B',
        'fmt': 'openai',
        'timeout': 10,
    },
    'silicon_glm9b': {
        'url': 'https://api.siliconflow.cn/v1/chat/completions',
        'key': 'sk-owrkbtvlwvzxcgpoehnminlrszmjyksuqarusjhlnnaormop',
        'model': 'THUDM/glm-4-9b-chat',
        'fmt': 'openai',
        'timeout': 10,
    },
    'silicon_deepseek': {
        'url': 'https://api.siliconflow.cn/v1/chat/completions',
        'key': 'sk-owrkbtvlwvzxcgpoehnminlrszmjyksuqarusjhlnnaormop',
        'model': 'deepseek-ai/DeepSeek-R1-Distill-Qwen-7B',
        'fmt': 'openai',
        'timeout': 15,
    },
    'baidu_ernie': {
        'url': 'https://qianfan.baidubce.com/v2/chat/completions',
        'key': 'bce-v3/ALTAK-TBS1FqErvp8KrI5QtegFL/6cb341ad50b09a475e384437a6d848facc11c649',
        'model': 'ernie-3.5-8k',
        'fmt': 'openai',
        'auth': 'bearer',
        'timeout': 10,
    },
    'baidu_speed': {
        'url': 'https://qianfan.baidubce.com/v2/chat/completions',
        'key': 'bce-v3/ALTAK-TBS1FqErvp8KrI5QtegFL/6cb341ad50b09a475e384437a6d848facc11c649',
        'model': 'ernie-speed-8k',
        'fmt': 'openai',
        'auth': 'bearer',
        'timeout': 8,
    },
    'volcengine_doubao': {
        'url': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
        'key': 'ark-70b27768-13f2-4641-b57b-ffdb22e51633-d15d1',
        'model': 'doubao-1-5-pro-256k',
        'fmt': 'openai',
        'timeout': 15,
    },
    'aliyun_qwen3': {
        'url': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
        'key': 'sk-c5173b8fece54c5bb81ad92b75a3e193',
        'model': 'qwen3-8b',
        'fmt': 'openai',
        'timeout': 10,
    },
    'aliyun_coder': {
        'url': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
        'key': 'sk-c5173b8fece54c5bb81ad92b75a3e193',
        'model': 'qwen-3-coder-plus',
        'fmt': 'openai',
        'timeout': 15,
    },
    'tencent_hunyuan': {
        'url': 'https://api.hunyuan.cloud.tencent.com/v1/chat/completions',
        'key': 'ak-20260501-da4f353b8eaeb218dd80d89b2a1ef9f5',
        'model': 'hunyuan-lite',
        'fmt': 'openai',
        'timeout': 10,
    },
    'chat_ubi': {
        'url': 'https://ch.at/v1/chat/completions',
        'key': 'none',
        'model': 'gpt-3',
        'fmt': 'openai',
        'timeout': 20,
    },
    'llm7': {
        'url': 'https://api.llm7.io/v1/chat/completions',
        'key': 'none',
        'model': 'auto',
        'fmt': 'openai',
        'timeout': 20,
    },
    'pollinations': {
        'url': 'https://text.pollinations.ai/openai',
        'key': 'none',
        'model': 'openai',
        'fmt': 'openai',
        'timeout': 30,
    },
    'naga_llama70b': {
        'url': 'https://api.naga.ai/v1/chat/completions',
        'key': 'ng-Zb0uc8FPh3H7afSRufjxE8FxJFSGh5vI',
        'model': 'llama-3.3-70b',
        'fmt': 'openai',
        'timeout': 20,
    },
    'naga_gpt41mini': {
        'url': 'https://api.naga.ai/v1/chat/completions',
        'key': 'ng-Zb0uc8FPh3H7afSRufjxE8FxJFSGh5vI',
        'model': 'gpt-4.1-mini',
        'fmt': 'openai',
        'timeout': 20,
    },
    'freetheai_ds': {
        'url': 'https://api.freetheai.xyz/v1/chat/completions',
        'key': 'sta_b36ec902e88c79ced726ed7e69305aefd624076bcf8625a0',
        'model': 'yng/gemini-3-1-pro',
        'fmt': 'openai',
        'timeout': 20,
    },
    'zuki_codestral': {
        'url': 'https://zukijourney.com/v1/chat/completions',
        'key': 'zu-bb1fd8ad182e9e16a68cb03e95c3a75f',
        'model': 'codestral-latest',
        'fmt': 'openai',
        'timeout': 20,
    },
}

PUBLIC_MODEL_NAME = 'red V1flash'

THINKING_BACKENDS = ['or_deepseek_r1', 'longcat_thinking', 'deepseek_pro']

VISION_BACKENDS = ['longcat_omni', 'or_deepseek_r1']
VISION_SYSTEM_PROMPT = '你是一位耐心的老师。用户上传了一道题目的图片。请：1. 识别题目内容 2. 分步骤解答 3. 给出最终答案。如果是选择题，明确指出正确选项。'

IDE_SOURCES = {
    'Claude Code',
    'claude-code',
    'Cursor',
    'You are Cursor',
    'GitHub Copilot',
    'Windsurf',
    'Codex',
    'Continue',
    'Cline',
}

ROUTE = {
    'trivial': 'nvidia_phi4',
    'cnc_trouble': 'longcat_thinking',
    'grbl_config': 'local',
    'gcode_help': 'local',
    'embedded_dev': 'nvidia_nemotron',
    'code_generation': 'nvidia_qwen_coder',
    'architecture': 'longcat',
    'general_cnc': 'longcat_lite',
    'tool_task': 'llm7',
    'image_gen': 'pollinations',
    'complex_theory': 'longcat_thinking',
    'thinking': 'or_deepseek_r1',
    'unknown': 'longcat_chat',
}

_backend_enabled: dict[str, bool] = {}

def is_enabled(name: str) -> bool:
    """Return whether a backend is enabled (default True)."""
    return _backend_enabled.get(name, True)

def set_enabled(name: str, enabled: bool) -> None:
    _backend_enabled[name] = enabled

def get_enabled_dict() -> dict:
    return dict(_backend_enabled)


def detect_vendor(url: str) -> str:
    """Auto-detect vendor from URL."""
    if 'longcat' in url: return 'LongCat'
    if 'nvidia' in url: return 'NVIDIA'
    if 'openrouter' in url: return 'OpenRouter'
    if 'deepseek' in url: return 'DeepSeek'
    if 'chinamobile' in url: return 'China Mobile'
    if 'right.codes' in url: return 'Claude (AWS)'
    if 'localhost' in url or '127.0.0.1' in url: return 'Local'
    if 'groq.com' in url: return 'Groq'
    if 'cerebras' in url: return 'Cerebras'
    if 'models.inference.ai.azure.com' in url: return 'GitHub Models'
    if 'generativelanguage.googleapis.com' in url: return 'Google Gemini'
    if 'cloudflare.com' in url: return 'Cloudflare'
    if 'mistral.ai' in url or 'codestral.mistral' in url: return 'Mistral'
    if 'bigmodel.cn' in url: return 'Zhipu'
    if 'siliconflow.cn' in url: return 'SiliconFlow'
    if 'baidubce.com' in url: return 'Baidu'
    if 'volces.com' in url: return 'Volcengine'
    if 'aliyuncs.com' in url: return 'Alibaba'
    if 'tencent.com' in url or 'hunyuan' in url: return 'Tencent'
    if 'unturf.com' in url: return 'UncloseAI'
    if 'ch.at' in url: return 'ChatUbi'
    if 'llm7.io' in url: return 'LLM7'
    if 'pollinations' in url: return 'Pollinations'
    return 'Unknown'

def detect_tier(url: str, name: str = "") -> str:
    """Auto-detect pricing tier from URL and name."""
    if 'localhost' in url or '127.0.0.1' in url: return 'L0 Local'
    if 'longcat' in url or 'chinamobile' in url: return 'L1 Free Unlimited'
    if 'nvidia' in url: return 'L2 Free Quota'
    if 'openrouter' in url: return 'L3 Free Limited'
    if 'deepseek.com' in url or 'right.codes' in url: return 'L4 Paid'
    return 'L3 Free Limited'

def detect_protocol(fmt: str) -> str:
    """Map format to protocol name."""
    return 'Anthropic' if fmt == 'anthropic' else 'OpenAI'

def detect_caps(name: str, fmt: str = "", cfg: dict = None) -> list:
    """Auto-detect backend capabilities from name and config."""
    caps = []
    if cfg and cfg.get('caps'):
        return cfg['caps']
    if name in ('claude', 'or_deepseek_r1', 'or_qwen3_coder', 'deepseek_pro', 'deepseek_flash'):
        caps.append('tool_calls')
    if name in ('claude', 'longcat_omni'):
        caps.append('vision')
    if 'thinking' in name or 'r1' in name:
        caps.append('deep_reasoning')
    if not caps:
        caps.append('text_only')
    return caps


def get_configured_backends() -> list:
    """Return list of backends that have API keys configured."""
    return [k for k, v in BACKENDS.items() if v.get('key') and k != 'local']


def startup_check():
    """Validate backend configuration at startup."""
    configured = get_configured_backends()
    unconfigured = [k for k, v in BACKENDS.items() if not v.get("key") and k != "local"]
    if configured:
        print(f'[LiMa] {len(configured)} backends configured', file=sys.stderr)
    if not configured:
        print('[LiMa] WARNING: No backends have API keys!', file=sys.stderr)
