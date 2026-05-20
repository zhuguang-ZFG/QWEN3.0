#!/usr/bin/env python3
"""LiMa Smart Router (LEGACY — 逐步迁移到新模块)

迁移状态:
  BACKENDS 字典       → backends.py         (已提取，此处保留供 server.py 兼容)
  detect_vision_request → vision_handler.py  (已提取)
  convert_openai_vision_to_anthropic → vision_handler.py (已提取)
  路由逻辑             → routing_engine.py   (V4 五层路由)
  响应构建             → response_builder.py (已提取)
  Fallback             → fallback_chain.py   (已提取)
  统计收集             → stats_collector.py  (已提取)
  Tool Call            → tool_handler.py     (已提取)
  Skills 注入          → skills_injector.py  (已提取)

仍在 smart_router.py 保留(server.py 直接依赖):
  - call_api / call_api_stream
  - 熔断器 (cb_allow/cb_record/cb_status)
  - analyze / route / select_backend
  - thinking/vision/image 检测
  - clean_response / qa_check
  - 本地模型路由
"""
import json, os, sys, re, time, urllib.request
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from dotenv import load_dotenv
load_dotenv()

# ── Local Router Model (Qwen3-1.7B, trained Round 12) ───────────────────────
LOCAL_ROUTER_MODEL = os.environ.get('LIMA_ROUTER_MODEL', 'D:/GIT/my_code_model_qwen3_r13/final')
_local_model = None
_local_tokenizer = None
_local_model_failed = False  # 标记模型加载是否失败过，避免重复尝试

DEBUG = os.environ.get('LIMA_DEBUG', '') == '1'

# ── Startup validation ─────────────────────────────────────────────────────
def _startup_check():
    configured = [k for k, v in BACKENDS.items() if v.get('key')]
    unconfigured = [k for k, v in BACKENDS.items() if not v.get('key') and k != 'local']
    if configured:
        print(f'[LiMa] {len(configured)} backends configured: {", ".join(configured[:5])}{"..." if len(configured) > 5 else ""}', file=sys.stderr)
    if unconfigured and DEBUG:
        print(f'[LiMa] {len(unconfigured)} backends missing keys: {", ".join(unconfigured[:5])}', file=sys.stderr)
    if not configured:
        print('[LiMa] WARNING: No backends have API keys configured!', file=sys.stderr)

# ── Config ──────────────────────────────────────────────────────────────────
LM_URL = 'http://localhost:1234/v1/chat/completions'

# ═══ BACKENDS 定义 (已提取 → backends.py) ═══════════════════════════════════════
BACKENDS = {
    'claude':  {'url': 'https://right.codes/claude-aws/v1/messages',
                'key': os.environ.get('CLAUDE_API_KEY', ''),
                'model': 'claude-sonnet-4-6', 'fmt': 'anthropic', 'auth': 'x-api-key'},
    # LongCat 系列 - 按复杂度分层（使用 /anthropic/v1/messages 路径 + Bearer 认证）
    'longcat_lite':     {'url': 'https://api.longcat.chat/anthropic/v1/messages',
                         'key': os.environ.get('LONGCAT_API_KEY', ''),
                         'model': 'LongCat-Flash-Lite', 'fmt': 'anthropic', 'auth': 'bearer'},
    'longcat_chat':     {'url': 'https://api.longcat.chat/anthropic/v1/messages',
                         'key': os.environ.get('LONGCAT_API_KEY', ''),
                         'model': 'LongCat-Flash-Chat', 'fmt': 'anthropic', 'auth': 'bearer'},
    'longcat_thinking': {'url': 'https://api.longcat.chat/anthropic/v1/messages',
                         'key': os.environ.get('LONGCAT_API_KEY', ''),
                         'model': 'LongCat-Flash-Thinking-2601', 'fmt': 'anthropic', 'auth': 'bearer'},
    'longcat_omni':     {'url': 'https://api.longcat.chat/anthropic/v1/messages',
                         'key': os.environ.get('LONGCAT_API_KEY', ''),
                         'model': 'LongCat-Flash-Omni-2603', 'fmt': 'anthropic',
                         'auth': 'bearer', 'no_system': True},
    'longcat':          {'url': 'https://api.longcat.chat/anthropic/v1/messages',
                         'key': os.environ.get('LONGCAT_API_KEY', ''),
                         'model': 'LongCat-2.0-Preview', 'fmt': 'anthropic', 'auth': 'bearer'},
    # DeepSeek 系列
    'deepseek_pro':    {'url': 'https://api.deepseek.com/anthropic/v1/messages',
                        'key': os.environ.get('DEEPSEEK_API_KEY', ''),
                        'model': 'deepseek-v4-pro', 'fmt': 'anthropic'},
    'deepseek_flash':  {'url': 'https://api.deepseek.com/anthropic/v1/messages',
                        'key': os.environ.get('DEEPSEEK_API_KEY', ''),
                        'model': 'deepseek-v4-flash', 'fmt': 'anthropic'},
    # Nvidia NIM 系列 - 免费额度，OpenAI 兼容
    'nvidia_nemotron':  {'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
                         'key': os.environ.get('NVIDIA_API_KEY', ''),
                         'model': 'nvidia/llama-3.3-nemotron-super-49b-v1', 'fmt': 'openai'},
    'nvidia_llama70b':  {'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
                         'key': os.environ.get('NVIDIA_API_KEY', ''),
                         'model': 'meta/llama-3.3-70b-instruct', 'fmt': 'openai'},
    'nvidia_qwen_coder':{'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
                         'key': os.environ.get('NVIDIA_API_KEY', ''),
                         'model': 'qwen/qwen3-coder-480b-a35b-instruct', 'fmt': 'openai'},
    'nvidia_llama4':    {'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
                         'key': os.environ.get('NVIDIA_API_KEY', ''),
                         'model': 'meta/llama-4-maverick-17b-128e-instruct', 'fmt': 'openai'},
    'nvidia_mistral':   {'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
                         'key': os.environ.get('NVIDIA_API_KEY', ''),
                         'model': 'mistralai/mistral-large-3-675b-instruct-2512', 'fmt': 'openai'},
    'nvidia_phi4':      {'url': 'https://integrate.api.nvidia.com/v1/chat/completions',
                         'key': os.environ.get('NVIDIA_API_KEY', ''),
                         'model': 'microsoft/phi-4-mini-instruct', 'fmt': 'openai'},
    # 中国移动 MaaS
    'chinamobile': {'url': 'https://maas.gd.chinamobile.com:36007/ai/uifm/open/v1/chat/completions',
                    'key': os.environ.get('CHINAMOBILE_API_KEY', ''),
                    'model': 'minimax-m25', 'fmt': 'openai'},
    # OpenRouter 免费模型（20次/分钟，200次/天，不稳定需熔断保护）
    'or_deepseek_r1':  {'url': 'https://openrouter.ai/api/v1/chat/completions',
                        'key': os.environ.get('OPENROUTER_API_KEY', ''),
                        'model': 'deepseek/deepseek-v4-flash:free', 'fmt': 'openai',
                        'timeout': 60},
    'or_qwen3_coder':  {'url': 'https://openrouter.ai/api/v1/chat/completions',
                        'key': os.environ.get('OPENROUTER_API_KEY', ''),
                        'model': 'qwen/qwen3-coder:free', 'fmt': 'openai',
                        'timeout': 60},
    'or_llama70b':     {'url': 'https://openrouter.ai/api/v1/chat/completions',
                        'key': os.environ.get('OPENROUTER_API_KEY', ''),
                        'model': 'meta-llama/llama-3.3-70b-instruct:free', 'fmt': 'openai',
                        'timeout': 45},
    'or_nemotron':     {'url': 'https://openrouter.ai/api/v1/chat/completions',
                        'key': os.environ.get('OPENROUTER_API_KEY', ''),
                        'model': 'nvidia/llama-3.3-nemotron-super-49b-v1:free', 'fmt': 'openai',
                        'timeout': 60},
    'or_qwen3_80b':    {'url': 'https://openrouter.ai/api/v1/chat/completions',
                        'key': os.environ.get('OPENROUTER_API_KEY', ''),
                        'model': 'qwen/qwen3-next-80b-a3b-instruct:free', 'fmt': 'openai',
                        'timeout': 30},
    'or_nemotron120b': {'url': 'https://openrouter.ai/api/v1/chat/completions',
                        'key': os.environ.get('OPENROUTER_API_KEY', ''),
                        'model': 'nvidia/nemotron-3-super-120b-a12b:free', 'fmt': 'openai',
                        'timeout': 60},
    'or_gptoss_120b':  {'url': 'https://openrouter.ai/api/v1/chat/completions',
                        'key': os.environ.get('OPENROUTER_API_KEY', ''),
                        'model': 'openai/gpt-oss-120b:free', 'fmt': 'openai',
                        'timeout': 60},
    'or_glm45':        {'url': 'https://openrouter.ai/api/v1/chat/completions',
                        'key': os.environ.get('OPENROUTER_API_KEY', ''),
                        'model': 'z-ai/glm-4.5-air:free', 'fmt': 'openai',
                        'timeout': 30},
    'or_minimax':      {'url': 'https://openrouter.ai/api/v1/chat/completions',
                        'key': os.environ.get('OPENROUTER_API_KEY', ''),
                        'model': 'minimax/minimax-m2.5:free', 'fmt': 'openai',
                        'timeout': 30},
    'or_gemma4':       {'url': 'https://openrouter.ai/api/v1/chat/completions',
                        'key': os.environ.get('OPENROUTER_API_KEY', ''),
                        'model': 'google/gemma-4-31b-it:free', 'fmt': 'openai',
                        'timeout': 30},
    # UncloseAI 免费后端（无需 API Key，无限额度）
    'unclose_hermes':  {'url': 'https://hermes.ai.unturf.com/v1/chat/completions',
                        'key': 'none', 'model': 'adamo1139/Hermes-3-Llama-3.1-8B-FP8-Dynamic',
                        'fmt': 'openai', 'timeout': 15},
    'unclose_qwen':    {'url': 'https://qwen.ai.unturf.com/v1/chat/completions',
                        'key': 'none', 'model': 'Qwen3.6-27B-UD-Q4_K_XL.gguf',
                        'fmt': 'openai', 'timeout': 30},
    # Groq 免费推理（极速，1000 req/5min，需 Key）
    'groq_llama70b':   {'url': 'https://api.groq.com/openai/v1/chat/completions',
                        'key': os.environ.get('GROQ_API_KEY', ''),
                        'model': 'llama-3.3-70b-versatile', 'fmt': 'openai', 'timeout': 15},
    'groq_gptoss':     {'url': 'https://api.groq.com/openai/v1/chat/completions',
                        'key': os.environ.get('GROQ_API_KEY', ''),
                        'model': 'openai/gpt-oss-120b', 'fmt': 'openai', 'timeout': 15},
    'groq_gptoss_20b': {'url': 'https://api.groq.com/openai/v1/chat/completions',
                        'key': os.environ.get('GROQ_API_KEY', ''),
                        'model': 'openai/gpt-oss-20b', 'fmt': 'openai', 'timeout': 10},
    'groq_qwen32b':    {'url': 'https://api.groq.com/openai/v1/chat/completions',
                        'key': os.environ.get('GROQ_API_KEY', ''),
                        'model': 'qwen/qwen3-32b', 'fmt': 'openai', 'timeout': 15},
    'groq_llama4':     {'url': 'https://api.groq.com/openai/v1/chat/completions',
                        'key': os.environ.get('GROQ_API_KEY', ''),
                        'model': 'meta-llama/llama-4-scout-17b-16e-instruct', 'fmt': 'openai', 'timeout': 15},
    'groq_llama8b':    {'url': 'https://api.groq.com/openai/v1/chat/completions',
                        'key': os.environ.get('GROQ_API_KEY', ''),
                        'model': 'llama-3.1-8b-instant', 'fmt': 'openai', 'timeout': 10},
    # Cerebras 免费推理（超大模型，极速，需 Key）
    'cerebras_qwen235b': {'url': 'https://api.cerebras.ai/v1/chat/completions',
                          'key': os.environ.get('CEREBRAS_API_KEY', ''),
                          'model': 'qwen-3-235b-a22b-instruct-2507', 'fmt': 'openai', 'timeout': 30},
    'cerebras_llama8b':  {'url': 'https://api.cerebras.ai/v1/chat/completions',
                          'key': os.environ.get('CEREBRAS_API_KEY', ''),
                          'model': 'llama3.1-8b', 'fmt': 'openai', 'timeout': 15},
    'cerebras_gptoss':   {'url': 'https://api.cerebras.ai/v1/chat/completions',
                          'key': os.environ.get('CEREBRAS_API_KEY', ''),
                          'model': 'gpt-oss-120b', 'fmt': 'openai', 'timeout': 20},
    # GitHub Models 免费推理（20000 req/min，极宽松，需 GitHub Token）
    'github_gpt4o':      {'url': 'https://models.inference.ai.azure.com/chat/completions',
                          'key': os.environ.get('GITHUB_TOKEN', ''),
                          'model': 'gpt-4o', 'fmt': 'openai', 'timeout': 15},
    'github_gpt4o_mini': {'url': 'https://models.inference.ai.azure.com/chat/completions',
                          'key': os.environ.get('GITHUB_TOKEN', ''),
                          'model': 'gpt-4o-mini', 'fmt': 'openai', 'timeout': 15},
    'github_gpt5':       {'url': 'https://models.inference.ai.azure.com/chat/completions',
                          'key': os.environ.get('GITHUB_TOKEN', ''),
                          'model': 'gpt-5', 'fmt': 'openai', 'timeout': 30},
    'github_o3_mini':    {'url': 'https://models.inference.ai.azure.com/chat/completions',
                          'key': os.environ.get('GITHUB_TOKEN', ''),
                          'model': 'o3-mini', 'fmt': 'openai', 'timeout': 30},
    'github_o4_mini':    {'url': 'https://models.inference.ai.azure.com/chat/completions',
                          'key': os.environ.get('GITHUB_TOKEN', ''),
                          'model': 'o4-mini', 'fmt': 'openai', 'timeout': 30},
    'github_deepseek_r1':{'url': 'https://models.inference.ai.azure.com/chat/completions',
                          'key': os.environ.get('GITHUB_TOKEN', ''),
                          'model': 'DeepSeek-R1', 'fmt': 'openai', 'timeout': 60},
    'github_llama70b':   {'url': 'https://models.inference.ai.azure.com/chat/completions',
                          'key': os.environ.get('GITHUB_TOKEN', ''),
                          'model': 'Llama-3.3-70B-Instruct', 'fmt': 'openai', 'timeout': 15},
    'github_codestral':  {'url': 'https://models.inference.ai.azure.com/chat/completions',
                          'key': os.environ.get('GITHUB_TOKEN', ''),
                          'model': 'Codestral-2501', 'fmt': 'openai', 'timeout': 15},
    # Google Gemini 免费推理（OpenAI 兼容端点，需 Key）
    'google_flash_lite': {'url': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
                          'key': os.environ.get('GOOGLE_AI_KEY', ''),
                          'model': 'gemini-3.1-flash-lite', 'fmt': 'openai', 'timeout': 15},
    'google_flash':      {'url': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
                          'key': os.environ.get('GOOGLE_AI_KEY', ''),
                          'model': 'gemini-2.5-flash', 'fmt': 'openai', 'timeout': 20},
    'google_gemini3':    {'url': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
                          'key': os.environ.get('GOOGLE_AI_KEY', ''),
                          'model': 'gemini-3-flash', 'fmt': 'openai', 'timeout': 20},
    'google_gemma4':     {'url': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
                          'key': os.environ.get('GOOGLE_AI_KEY', ''),
                          'model': 'gemma-3-27b-it', 'fmt': 'openai', 'timeout': 15},
    # Cloudflare Workers AI（37 模型，OpenAI 兼容，免费 10k neurons/day）
    'cf_llama70b':       {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions",
                          'key': os.environ.get('CLOUDFLARE_TOKEN', ''),
                          'model': '@cf/meta/llama-3.3-70b-instruct-fp8-fast', 'fmt': 'openai', 'timeout': 15},
    'cf_llama4':         {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions",
                          'key': os.environ.get('CLOUDFLARE_TOKEN', ''),
                          'model': '@cf/meta/llama-4-scout-17b-16e-instruct', 'fmt': 'openai', 'timeout': 15},
    'cf_qwen_coder':     {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions",
                          'key': os.environ.get('CLOUDFLARE_TOKEN', ''),
                          'model': '@cf/qwen/qwen2.5-coder-32b-instruct', 'fmt': 'openai', 'timeout': 15},
    'cf_mistral':        {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions",
                          'key': os.environ.get('CLOUDFLARE_TOKEN', ''),
                          'model': '@cf/mistralai/mistral-small-3.1-24b-instruct', 'fmt': 'openai', 'timeout': 15},
    'cf_vision':         {'url': f"https://api.cloudflare.com/client/v4/accounts/{os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions",
                          'key': os.environ.get('CLOUDFLARE_TOKEN', ''),
                          'model': '@cf/meta/llama-3.2-11b-vision-instruct', 'fmt': 'openai', 'timeout': 15},
    # Mistral 免费额度（OpenAI 兼容，需 Key）— 10亿token/月
    'mistral_large':     {'url': 'https://api.mistral.ai/v1/chat/completions',
                          'key': os.environ.get('MISTRAL_API_KEY', ''),
                          'model': 'mistral-large-latest', 'fmt': 'openai', 'timeout': 20},
    'mistral_small':     {'url': 'https://api.mistral.ai/v1/chat/completions',
                          'key': os.environ.get('MISTRAL_API_KEY', ''),
                          'model': 'mistral-small-latest', 'fmt': 'openai', 'timeout': 15},
    'mistral_medium':    {'url': 'https://api.mistral.ai/v1/chat/completions',
                          'key': os.environ.get('MISTRAL_API_KEY', ''),
                          'model': 'mistral-medium-latest', 'fmt': 'openai', 'timeout': 15},
    'mistral_codestral': {'url': 'https://codestral.mistral.ai/v1/chat/completions',
                          'key': os.environ.get('MISTRAL_API_KEY', ''),
                          'model': 'codestral-latest', 'fmt': 'openai', 'timeout': 15},
    'mistral_devstral':  {'url': 'https://api.mistral.ai/v1/chat/completions',
                          'key': os.environ.get('MISTRAL_API_KEY', ''),
                          'model': 'devstral-small-latest', 'fmt': 'openai', 'timeout': 20},
    'mistral_pixtral':   {'url': 'https://api.mistral.ai/v1/chat/completions',
                          'key': os.environ.get('MISTRAL_API_KEY', ''),
                          'model': 'pixtral-large-latest', 'fmt': 'openai', 'timeout': 20},
    'local':   {'url': LM_URL, 'key': '', 'model': 'local-model', 'fmt': 'openai', 'auth': 'bearer'},
    # ── 国内直连厂商（无需翻墙，低延迟）──────────────────────────────────────
    # 智谱 AI (GLM) — GLM-4.7-Flash 200K, 永久免费, 30 QPS
    'zhipu_flash':     {'url': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
                        'key': os.environ.get('ZHIPU_API_KEY', ''),
                        'model': 'glm-4-flash', 'fmt': 'openai', 'timeout': 10},
    'zhipu_flash7':    {'url': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
                        'key': os.environ.get('ZHIPU_API_KEY', ''),
                        'model': 'glm-4.7-flash', 'fmt': 'openai', 'timeout': 10},
    # 硅基流动 (SiliconFlow) — 1000 RPM, <100ms, 永久免费
    'silicon_qwen8b':  {'url': 'https://api.siliconflow.cn/v1/chat/completions',
                        'key': os.environ.get('SILICONFLOW_API_KEY', ''),
                        'model': 'Qwen/Qwen3-8B', 'fmt': 'openai', 'timeout': 10},
    'silicon_glm9b':   {'url': 'https://api.siliconflow.cn/v1/chat/completions',
                        'key': os.environ.get('SILICONFLOW_API_KEY', ''),
                        'model': 'THUDM/glm-4-9b-chat', 'fmt': 'openai', 'timeout': 10},
    'silicon_deepseek':{'url': 'https://api.siliconflow.cn/v1/chat/completions',
                        'key': os.environ.get('SILICONFLOW_API_KEY', ''),
                        'model': 'deepseek-ai/DeepSeek-R1-Distill-Qwen-7B', 'fmt': 'openai', 'timeout': 15},
    # 百度千帆 (ERNIE) — 永久免费不限量, 50 QPS
    'baidu_ernie':     {'url': 'https://qianfan.baidubce.com/v2/chat/completions',
                        'key': os.environ.get('BAIDU_API_KEY', ''),
                        'model': 'ernie-3.5-8k', 'fmt': 'openai', 'auth': 'bearer', 'timeout': 10},
    'baidu_speed':     {'url': 'https://qianfan.baidubce.com/v2/chat/completions',
                        'key': os.environ.get('BAIDU_API_KEY', ''),
                        'model': 'ernie-speed-8k', 'fmt': 'openai', 'auth': 'bearer', 'timeout': 8},
    # 火山引擎/豆包 — 每天200万Token
    'volcengine_doubao':{'url': 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
                         'key': os.environ.get('VOLCENGINE_API_KEY', ''),
                         'model': 'doubao-1-5-pro-256k', 'fmt': 'openai', 'timeout': 15},
    # 阿里云百炼 (DashScope) — 每模型100万Token, OpenAI兼容
    'aliyun_qwen3':    {'url': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
                        'key': os.environ.get('ALIYUN_API_KEY', ''),
                        'model': 'qwen3-8b', 'fmt': 'openai', 'timeout': 10},
    'aliyun_coder':    {'url': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
                        'key': os.environ.get('ALIYUN_API_KEY', ''),
                        'model': 'qwen-3-coder-plus', 'fmt': 'openai', 'timeout': 15},
    # 腾讯混元 — 100万Token
    'tencent_hunyuan': {'url': 'https://api.hunyuan.cloud.tencent.com/v1/chat/completions',
                        'key': os.environ.get('TENCENT_API_KEY', ''),
                        'model': 'hunyuan-lite', 'fmt': 'openai', 'timeout': 10},
    # ── 零 Key 端点（无需注册，无限额度）──
    'chat_ubi':        {'url': 'https://ch.at/v1/chat/completions',
                        'key': 'none', 'model': 'gpt-3', 'fmt': 'openai', 'timeout': 20},
    'llm7':            {'url': 'https://api.llm7.io/v1/chat/completions',
                        'key': 'none', 'model': 'auto', 'fmt': 'openai', 'timeout': 20},
    'pollinations':    {'url': 'https://text.pollinations.ai/openai',
                        'key': 'none', 'model': 'openai', 'fmt': 'openai', 'timeout': 30},
    # ── NagaAI 免费 (Discord 注册, 13 模型, ng-* key) ──
    'naga_llama70b':   {'url': 'https://api.naga.ai/v1/chat/completions',
                        'key': os.environ.get('NAGA_API_KEY', ''),
                        'model': 'llama-3.3-70b', 'fmt': 'openai', 'timeout': 20},
    'naga_gpt41mini':  {'url': 'https://api.naga.ai/v1/chat/completions',
                        'key': os.environ.get('NAGA_API_KEY', ''),
                        'model': 'gpt-4.1-mini', 'fmt': 'openai', 'timeout': 20},
    # ── FreeTheAi (Discord 注册, 16000+ 模型, sta_* key) ──
    'freetheai_ds':    {'url': 'https://api.freetheai.xyz/v1/chat/completions',
                        'key': os.environ.get('FREETHEAI_API_KEY', ''),
                        'model': 'yng/gemini-3-1-pro', 'fmt': 'openai', 'timeout': 20},
    # ── ZukiJourney (Discord 注册, Mistral 系列, zu-* key) ──
    'zuki_codestral':  {'url': 'https://zukijourney.com/v1/chat/completions',
                        'key': os.environ.get('ZUKI_API_KEY', ''),
                        'model': 'codestral-latest', 'fmt': 'openai', 'timeout': 20},
    # ── OpenCode Zen (零Key零注册, Big Pickle Stealth 72% SWE-bench) ──
    'opencode_stealth': {'url': 'https://opencode.ai/zen/v1/chat/completions',
                        'key': 'none', 'model': 'big-pickle', 'fmt': 'openai', 'timeout': 45},
    'opencode_ds_flash': {'url': 'https://opencode.ai/zen/v1/chat/completions',
                        'key': 'none', 'model': 'deepseek-v4-flash-free', 'fmt': 'openai', 'timeout': 30},
    'opencode_qwen':    {'url': 'https://opencode.ai/zen/v1/chat/completions',
                        'key': 'none', 'model': 'qwen3.6-plus-free', 'fmt': 'openai', 'timeout': 30},
    'opencode_nemotron': {'url': 'https://opencode.ai/zen/v1/chat/completions',
                        'key': 'none', 'model': 'nemotron-3-super-free', 'fmt': 'openai', 'timeout': 30},
    # ── Fireworks AI (Llama 3.1 405B 独家) ──
    'fireworks_llama405b': {'url': 'https://api.fireworks.ai/inference/v1/chat/completions',
                        'key': os.environ.get('FIREWORKS_API_KEY', ''),
                        'model': 'accounts/fireworks/models/llama-v3p1-405b-instruct', 'fmt': 'openai', 'timeout': 45},
    # ── OVHcloud (欧洲直连, 零注册) ──
    'ovh_llama70b':    {'url': 'https://llama-3-3-70b-instruct.endpoints.ai.cloud.ovh.net/v1/chat/completions',
                        'key': 'none', 'model': 'Llama-3.3-70B-Instruct', 'fmt': 'openai', 'timeout': 30},
    # ── Cohere (Command A 111B, Mamba+Transformer) ──
    'cohere_command':  {'url': 'https://api.cohere.com/v2/chat',
                        'key': os.environ.get('COHERE_API_KEY', ''),
                        'model': 'command-a-03-2025', 'fmt': 'openai', 'timeout': 30},
    # ── SambaNova Cloud (芯片级加速) ──
    'sambanova_llama4': {'url': 'https://api.sambanova.ai/v1/chat/completions',
                        'key': os.environ.get('SAMBANOVA_API_KEY', ''),
                        'model': 'Meta-Llama-4-Maverick-17B-128E-Instruct', 'fmt': 'openai', 'timeout': 20},
    # ── DeepInfra (200并发, 高吞吐) ──
    'deepinfra_llama4': {'url': 'https://api.deepinfra.com/v1/openai/chat/completions',
                        'key': os.environ.get('DEEPINFRA_API_KEY', ''),
                        'model': 'meta-llama/Llama-4-Maverick-17B-128E-Instruct', 'fmt': 'openai', 'timeout': 20},
    'deepinfra_qwen235b': {'url': 'https://api.deepinfra.com/v1/openai/chat/completions',
                        'key': os.environ.get('DEEPINFRA_API_KEY', ''),
                        'model': 'Qwen/Qwen3-235B-A22B-Instruct', 'fmt': 'openai', 'timeout': 30},
}

# 对外暴露的统一模型名（用户永远看不到真实模型名）
PUBLIC_MODEL_NAME = os.environ.get('PUBLIC_MODEL_NAME', 'LiMa')

# 启动时校验后端配置
_startup_check()

# Intent -> backend
# 路由策略：免费模型优先，按层级榨取，付费模型最后兜底
# L0=本地零成本 | L1=LongCat/中国移动免费无限 | L2=Nvidia免费额度 | L3=OpenRouter免费额度 | L4=付费兜底
ROUTE = {
    'trivial':        'nvidia_phi4',       # L2: 最快模型（1-2秒），简单问候/元问题
    'cnc_trouble':    'longcat_thinking',  # L1: LongCat推理（免费，故障诊断）
    'grbl_config':    'local',             # L0: 本地直答，零成本
    'gcode_help':     'local',             # L0: 本地直答，零成本
    'embedded_dev':   'nvidia_nemotron',   # L2: Nvidia免费额度，嵌入式强
    'code_generation':'nvidia_qwen_coder', # L2: Nvidia免费额度，代码最强
    'architecture':   'longcat',           # L1: LongCat免费，综合最强
    'general_cnc':    'longcat_lite',      # L1: LongCat免费，快速
    'tool_task':      'llm7',             # L0: DevToolBox/LLM7 工具型任务
    'image_gen':      'pollinations',     # L0: Pollinations 图片生成
    'complex_theory': 'longcat_thinking',  # L1: LongCat免费推理
    'thinking':       'or_deepseek_r1',    # L3: Deep Thinking Mode（深度推理）
    'unknown':        'longcat_chat',      # L1: LongCat免费，通用
}

# ── one-api 渠道管理层 ────────────────────────────────────────────────────────
ONEAPI_BASE = os.environ.get('ONEAPI_BASE', 'http://127.0.0.1:3001/v1')
ONEAPI_ENABLED = os.environ.get('ONEAPI_ENABLED', 'true').lower() == 'true'

ONEAPI_GROUP_TOKENS = {
    'trivial':  os.environ.get('ONEAPI_TOKEN_TRIVIAL', 'sk-jutfJuQ8xmWHTn2h87B2C5661a1e497cAb6f5b8d0b396e2b'),
    'code':     os.environ.get('ONEAPI_TOKEN_CODE', 'sk-jutfJuQ8xmWHTn2h87B2C5661a1e497cAb6f5b8d0b396e2b'),
    'general':  os.environ.get('ONEAPI_TOKEN_GENERAL', 'sk-jutfJuQ8xmWHTn2h87B2C5661a1e497cAb6f5b8d0b396e2b'),
    'thinking': os.environ.get('ONEAPI_TOKEN_THINKING', 'sk-jutfJuQ8xmWHTn2h87B2C5661a1e497cAb6f5b8d0b396e2b'),
    'vision':   os.environ.get('ONEAPI_TOKEN_VISION', 'sk-jutfJuQ8xmWHTn2h87B2C5661a1e497cAb6f5b8d0b396e2b'),
}

INTENT_TO_GROUP = {
    'trivial': 'trivial',
    'code_generation': 'code',
    'tool_task': 'code',
    'thinking': 'thinking',
    'architecture': 'thinking',
    'cnc_trouble': 'thinking',
    'vision': 'vision',
    'image_gen': 'general',
    'general_cnc': 'general',
    'grbl_config': 'general',
    'gcode_help': 'general',
    'embedded_dev': 'general',
    'unknown': 'general',
}

ONEAPI_GROUP_MODELS = {
    'trivial': 'glm-4-flash',
    'code': 'codestral-latest',
    'general': 'glm-4.7-flash',
    'thinking': 'gpt-5',
    'vision': 'gpt-4o',
}

def call_oneapi(group, msgs, mt=1024, model_override=None):
    """通过 one-api 调用指定分组的后端。one-api 自动负载均衡和故障转移。"""
    token = ONEAPI_GROUP_TOKENS.get(group)
    if not token:
        return None
    model = model_override or ONEAPI_GROUP_MODELS.get(group, 'glm-4-flash')
    body = json.dumps({
        'model': model,
        'max_tokens': mt,
        'messages': [{'role': 'system', 'content': SYS}] + msgs,
    }).encode()
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}',
    }
    try:
        req = urllib.request.Request(
            f'{ONEAPI_BASE}/chat/completions', data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.loads(resp.read().decode())
        msg = d['choices'][0]['message']
        answer = msg.get('content') or msg.get('reasoning_content') or ''
        return answer
    except Exception as e:
        if DEBUG:
            print(f'[ONEAPI] {group}/{model} error: {e}', file=sys.stderr)
        return None
GFW_PROXY_URL = os.environ.get('GFW_PROXY', 'http://127.0.0.1:7897')
GFW_BACKENDS = {'google_flash', 'google_flash_lite', 'google_gemini3', 'google_gemma4',
                'mistral_large', 'mistral_small', 'mistral_medium',
                'mistral_codestral', 'mistral_devstral', 'mistral_pixtral', 'devtoolbox'}

def _get_opener(name):
    """被墙后端使用代理 opener，其他直连。"""
    if name in GFW_BACKENDS:
        proxy = urllib.request.ProxyHandler({'http': GFW_PROXY_URL, 'https': GFW_PROXY_URL})
        return urllib.request.build_opener(proxy)
    return None

# ── Circuit Breaker ──────────────────────────────────────────────────────────
import threading

_cb_lock = threading.Lock()
_cb_state = {}  # backend_name -> state dict

CB_FAILURE_THRESHOLD = 3    # 连续失败 N 次后熔断
CB_RECOVERY_TIMEOUT  = 60   # 熔断后 N 秒尝试恢复（half-open）
CB_SUCCESS_THRESHOLD = 2    # half-open 状态下连续成功 N 次才关闭熔断

def _cb_get(name):
    with _cb_lock:
        if name not in _cb_state:
            _cb_state[name] = {
                'state': 'closed',   # closed / open / half-open
                'failures': 0,
                'successes': 0,
                'opened_at': 0,
                'total_calls': 0,
                'total_errors': 0,
                'total_latency_ms': 0,
            }
        return dict(_cb_state[name])

def cb_allow(name):
    """返回 True 表示允许调用，False 表示熔断中。"""
    s = _cb_get(name)
    if s['state'] == 'closed':
        return True
    if s['state'] == 'open':
        if time.time() - s['opened_at'] > CB_RECOVERY_TIMEOUT:
            with _cb_lock:
                _cb_state[name]['state'] = 'half-open'
                _cb_state[name]['successes'] = 0
            return True
        return False
    # half-open: 允许一次试探
    return True

def cb_record(name, success, latency_ms=0):
    """记录调用结果，更新熔断器状态。"""
    with _cb_lock:
        s = _cb_state.setdefault(name, {
            'state': 'closed', 'failures': 0, 'successes': 0,
            'opened_at': 0, 'total_calls': 0, 'total_errors': 0, 'total_latency_ms': 0,
        })
        s['total_calls'] += 1
        s['total_latency_ms'] += latency_ms
        if success:
            s['total_errors'] = max(0, s['total_errors'])
            if s['state'] == 'half-open':
                s['successes'] += 1
                if s['successes'] >= CB_SUCCESS_THRESHOLD:
                    s['state'] = 'closed'
                    s['failures'] = 0
                    if DEBUG:
                        print(f'[CB] {name}: half-open -> closed', file=sys.stderr)
            else:
                s['failures'] = 0
        else:
            s['total_errors'] += 1
            s['failures'] += 1
            if s['state'] in ('closed', 'half-open') and s['failures'] >= CB_FAILURE_THRESHOLD:
                s['state'] = 'open'
                s['opened_at'] = time.time()
                print(f'[CB] {name}: OPEN (circuit breaker tripped after {s["failures"]} failures)', file=sys.stderr)

def cb_status():
    """返回所有后端的熔断器状态摘要。"""
    result = {}
    with _cb_lock:
        for name, s in _cb_state.items():
            total = s['total_calls']
            err_rate = s['total_errors'] / total if total > 0 else 0
            avg_lat = s['total_latency_ms'] / total if total > 0 else 0
            result[name] = {
                'state': s['state'],
                'failures': s['failures'],
                'error_rate': f'{err_rate:.1%}',
                'avg_latency_ms': int(avg_lat),
                'total_calls': total,
            }
    return result

# ── Fallback Chains ──────────────────────────────────────────────────────────
# 降级顺序严格按层级：L1免费无限 -> L2Nvidia免费额度 -> L3OpenRouter免费额度 -> L4付费兜底
FALLBACK_CHAINS = {
    'trivial': [
        'groq_llama4',        # L0.5: Groq极速（376ms）
        'silicon_qwen8b',     # L0: 硅基流动（<100ms，国内直连）
        'baidu_speed',        # L0: 百度ERNIE-Speed（永久免费，50QPS）
        'chat_ubi',           # L0: ch.at 零Key（2.8s，最佳通用对话）
        'zhipu_flash',        # L0: 智谱GLM-4-Flash（永久免费，30QPS）
        'unclose_hermes',     # L1: UncloseAI（免费无限，1.2s）
        'nvidia_phi4',        # L2: 最快（1-2秒）
        'nvidia_llama4',      # L2: 快速备选
        'longcat_lite',       # L1: 免费兜底
    ],
    'cnc_trouble': [
        'groq_llama70b',      # L0.5: Groq 70B极速（694ms）
        'unclose_hermes',     # L1: UncloseAI（免费无限，1.4s）
        'longcat_thinking',   # L1: LongCat推理（免费）
        'longcat',            # L1: LongCat最强（免费）
        'chinamobile',        # L1: 中国移动（免费）
        'nvidia_nemotron',    # L2: Nvidia推理（免费额度）
        'or_nemotron',        # L3: OpenRouter Nemotron（免费额度）
        'or_deepseek_r1',     # L3: OpenRouter DeepSeek（免费额度）
        'deepseek_pro',       # L4: 付费兜底
        'claude',             # L4: 付费最终兜底
    ],
    'grbl_config': [
        'local',              # L0: 本地直答
        'unclose_hermes',     # L1: UncloseAI（免费无限，1.4s）
        'longcat_lite',       # L1: LongCat（免费）
        'chinamobile',        # L1: 中国移动（免费）
        'nvidia_llama4',      # L2: Nvidia（免费额度）
        'or_llama70b',        # L3: OpenRouter（免费额度）
        'deepseek_flash',     # L4: 付费兜底
    ],
    'gcode_help': [
        'local',              # L0: 本地直答
        'unclose_hermes',     # L1: UncloseAI（免费无限，1.4s）
        'longcat_lite',       # L1: LongCat（免费）
        'chinamobile',        # L1: 中国移动（免费）
        'nvidia_llama4',      # L2: Nvidia（免费额度）
        'or_llama70b',        # L3: OpenRouter（免费额度）
        'deepseek_flash',     # L4: 付费兜底
    ],
    'embedded_dev': [
        'groq_llama70b',      # L0.5: Groq 70B极速
        'unclose_hermes',     # L1: UncloseAI（免费无限，1.4s）
        'google_flash_lite',  # L0.5: Gemini 3.1 Flash Lite（1.1s）
        'nvidia_nemotron',    # L2: Nvidia嵌入式（免费额度）
        'longcat_thinking',   # L1: LongCat推理（免费）
        'longcat',            # L1: LongCat最强（免费）
        'or_nemotron',        # L3: OpenRouter Nemotron（免费额度）
        'or_deepseek_r1',     # L3: OpenRouter DeepSeek（免费额度）
        'deepseek_pro',       # L4: 付费兜底
        'claude',             # L4: 付费最终兜底
    ],
    'code_generation': [
        'groq_gptoss',        # L0.5: Groq GPT-OSS 120B极速（520ms，代码强）
        'mistral_codestral',  # L0.5: Mistral Codestral（586ms，S级代码，10亿token/月）
        'mistral_devstral',   # L0.5: Mistral Devstral（agent coding，最新）
        'nvidia_qwen_coder',  # L2: Qwen Coder 480B（免费额度，代码最强）
        'github_codestral',   # L0.5: GitHub Codestral（免费）
        'unclose_qwen',       # L1: UncloseAI Qwen3 27B（免费无限，3s）
        'groq_qwen32b',       # L0.5: Groq Qwen3 32B（447ms）
        'github_gpt4o_mini',  # L0.5: GitHub GPT-4o-mini（3s，高质量）
        'or_qwen3_coder',     # L3: OpenRouter Qwen3（免费额度）
        'cerebras_gptoss',    # L0.5: Cerebras GPT-OSS 120B（极速）
        'llm7',               # L0: 零Key自动路由
        'longcat_chat',       # L1: LongCat（免费）
        'nvidia_llama70b',    # L2: Nvidia（免费额度）
        'or_llama70b',        # L3: OpenRouter（免费额度）
        'pollinations',       # L0: 零Key终极兜底
        'deepseek_flash',     # L4: 付费兜底
    ],
    'architecture': [
        'github_gpt5',        # L0.5: GitHub GPT-5（最强综合推理）
        'mistral_large',      # L0.5: Mistral Large（旗舰，10亿token/月）
        'groq_gptoss',        # L0.5: Groq GPT-OSS 120B极速（520ms）
        'groq_llama70b',      # L0.5: Groq 70B（694ms）
        'cerebras_qwen235b',  # L0.5: Cerebras Qwen 235B（1.9s，最强免费）
        'github_gpt4o',       # L0.5: GitHub GPT-4o（2.2s，最强通用）
        'google_gemini3',     # L0.5: Gemini 3 Flash（1M上下文）
        'or_nemotron120b',    # L3: OpenRouter Nemotron 120B（免费）
        'longcat',            # L1: LongCat最强（免费）
        'longcat_thinking',   # L1: LongCat推理（免费）
        'nvidia_nemotron',    # L2: Nvidia（免费额度）
        'or_deepseek_r1',     # L3: OpenRouter DeepSeek（免费额度）
        'deepseek_pro',       # L4: 付费兜底
        'claude',             # L4: 付费最终兜底
    ],
    'general_cnc': [
        'groq_llama4',        # L0.5: Groq Llama4极速（376ms）
        'unclose_hermes',     # L1: UncloseAI（免费无限，1.2s）
        'longcat_lite',       # L1: LongCat快速（免费）
        'chinamobile',        # L1: 中国移动（免费）
        'nvidia_llama4',      # L2: Nvidia快速（免费额度）
        'or_qwen3_80b',       # L3: OpenRouter快速（免费额度）
        'llm7',               # L0: 零Key自动路由
        'or_llama70b',        # L3: OpenRouter通用（免费额度）
        'pollinations',       # L0: 零Key终极兜底
        'deepseek_flash',     # L4: 付费兜底
    ],
    'complex_theory': [
        'longcat_thinking',   # L1: LongCat推理（免费）
        'longcat',            # L1: LongCat最强（免费）
        'nvidia_nemotron',    # L2: Nvidia推理（免费额度）
        'or_nemotron',        # L3: OpenRouter Nemotron（免费额度）
        'or_deepseek_r1',     # L3: OpenRouter DeepSeek（免费额度）
        'deepseek_pro',       # L4: 付费兜底
        'claude',             # L4: 付费最终兜底
    ],
    'thinking': [
        'or_deepseek_r1',     # L3: DeepSeek R1（深度推理首选）
        'github_deepseek_r1', # L0.5: GitHub DeepSeek R1（免费）
        'github_o3_mini',     # L0.5: GitHub o3-mini（推理强）
        'longcat_thinking',   # L1: LongCat推理（免费）
        'mistral_large',      # L0.5: Mistral Large（旗舰，10亿token/月）
        'deepseek_pro',       # L4: DeepSeek Pro（付费兜底）
        'longcat',            # L1: LongCat最强（免费）
        'claude',             # L4: 付费最终兜底
    ],
    'unknown': [
        'silicon_qwen8b',     # L0: 硅基流动（<100ms，国内直连）
        'zhipu_flash7',       # L0: 智谱GLM-4.7-Flash（200K，永久免费）
        'chat_ubi',           # L0: ch.at 零Key（2.8s，最佳通用对话）
        'baidu_ernie',        # L0: 百度ERNIE（永久免费不限量）
        'longcat_chat',       # L1: LongCat通用（免费）
        'chinamobile',        # L1: 中国移动（免费）
        'volcengine_doubao',  # L0: 火山豆包（每天200万Token）
        'nvidia_llama70b',    # L2: Nvidia通用（免费额度）
        'or_llama70b',        # L3: OpenRouter通用（免费额度）
        'or_qwen3_80b',       # L3: OpenRouter快速（免费额度）
        'llm7',               # L0: 零Key自动路由（2.7s）
        'longcat',            # L1: LongCat最强（免费，最终免费兜底）
        'pollinations',       # L0: 零Key终极兜底（4.2s，无限）
        'deepseek_flash',     # L4: 付费兜底
    ],
    'vision': [
        'cf_vision',          # Cloudflare Llama Vision 11B（867ms，最快，原生端点）
        'mistral_pixtral',    # Mistral Pixtral Large（796ms，高质量视觉）
        'github_gpt4o',       # GPT-4o（4.6s，最强视觉）
        'google_flash',       # Gemini 2.5 Flash（1.5s，快速视觉）
        'google_flash_lite',  # Gemini 3.1 Flash Lite（11s，兜底）
    ],
    'tool_task': [
        'llm7',               # L0: 零Key自动路由（2.7s，工具型首选）
        'groq_gptoss',        # L0.5: Groq GPT-OSS 120B（520ms，代码强）
        'nvidia_qwen_coder',  # L2: Qwen Coder 480B（代码最强）
        'pollinations',       # L0: 零Key终极兜底
        'deepseek_flash',     # L4: 付费兜底
    ],
}

def get_fallback_chain(intent_name, prefer=None):
    """获取意图对应的降级链，过滤掉没有 key 的后端。"""
    chain = list(FALLBACK_CHAINS.get(intent_name, ['groq_llama70b', 'unclose_hermes', 'nvidia_llama70b', 'longcat', 'claude']))
    # 如果有偏好后端，插到最前面
    if prefer and prefer in BACKENDS and prefer not in chain:
        chain.insert(0, prefer)
    elif prefer and prefer in chain:
        chain.remove(prefer)
        chain.insert(0, prefer)
    # 过滤掉没有 key 的后端
    chain = [b for b in chain if b in BACKENDS and (BACKENDS[b]['key'] or b == 'local')]
    return chain


def get_fallback_chain_sorted(intent_name, prefer=None):
    """获取降级链并按实时延迟排序——同优先级内快的优先。"""
    chain = get_fallback_chain(intent_name, prefer=prefer)
    # 按延迟排序：有数据的按延迟，没数据的排最前（探索优先）
    def _latency_sort_key(name):
        s = cb_status().get(name)
        if s and s['total_calls'] >= 3:
            return s.get('avg_latency_ms', 9999)
        return 0  # 新后端优先尝试
    chain.sort(key=_latency_sort_key)
    return chain


# ── Fast Backend Predictor ────────────────────────────────────────────────────
# 投机调用：在路由分析完成前，基于关键词快速预测最可能的后端
_FAST_PREDICT_RULES = [
    (re.compile(r'代码|code|函数|function|bug|error|def\s|class\s|import\s|写.*程序|编程', re.IGNORECASE), 'nvidia_qwen_coder'),
    (re.compile(r'翻译|translate|解释|定义|what is|who is|how to|explain', re.IGNORECASE), 'longcat_chat'),
    (re.compile(r'设计|架构|architect|system design|重构|refactor', re.IGNORECASE), 'longcat'),
    (re.compile(r'数学|计算|solve|equation|公式|推理', re.IGNORECASE), 'longcat_thinking'),
    (re.compile(r'图片|图像|画|logo|image|draw|picture', re.IGNORECASE), 'longcat_omni'),
]


def _has_vision_content(messages):
    """检测消息中是否包含图片（image_url 类型 content）。"""
    if not messages:
        return False
    for msg in messages:
        content = msg.get('content')
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'image_url':
                    return True
    return False


def predict_fast_backend(query: str) -> str:
    """快速预测最可能的后端（<1ms，基于正则）。
    用于投机调用：路由分析的同时先发请求到预测后端。
    """
    for pattern, backend in _FAST_PREDICT_RULES:
        if pattern.search(query):
            if backend in BACKENDS and BACKENDS[backend].get('key'):
                return backend
    # 默认：Groq 最快（376-694ms），作为投机首选
    return 'groq_llama4'

# ── Prompt Assembly (fragment-based, cache-friendly) ─────────────────────────
FRAGMENT_DIR = os.path.join(os.path.dirname(__file__), 'fragments')

def _load_fragment(name):
    """加载 prompt 片段文件。"""
    path = os.path.join(FRAGMENT_DIR, f'{name}.md')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return ''

def assemble_prompt(features=None):
    """从片段文件组装系统提示词。功能开关控制加载哪些片段。

    features 可为 None（加载全部）或 set（指定加载的片段名）。
    """
    if features is None:
        features = {'identity', 'capabilities', 'constraints', 'safety'}
    parts = []
    for name in ['identity', 'capabilities', 'constraints', 'safety']:
        if name in features:
            chunk = _load_fragment(name)
            if chunk:
                parts.append(chunk)
    return '\n\n'.join(parts) if parts else ''

# 默认 SYS 从片段组装（可缓存：完全静态，不含动态数据）
SYS = assemble_prompt()

# ── Deep Thinking Mode Detection ─────────────────────────────────────────────
_THINKING_PATTERNS = [
    # Chinese triggers
    re.compile(r'仔细想想|深度分析|深入分析|深度思考|仔细分析|认真想|好好想|慢慢想', re.IGNORECASE),
    re.compile(r'逐步推理|一步一步|分步骤|详细推导|严格证明|严谨分析', re.IGNORECASE),
    re.compile(r'证明.*(?:定理|公式|等式|不等式|无理数|收敛|存在)', re.IGNORECASE),
    re.compile(r'数学证明|形式化证明|逻辑推导|归纳证明|反证法', re.IGNORECASE),
    re.compile(r'复杂度分析|时间复杂度|空间复杂度|算法.*证明', re.IGNORECASE),
    re.compile(r'系统架构.*设计|分布式.*设计|微服务.*拆分', re.IGNORECASE),
    # English triggers
    re.compile(r'think carefully|think step by step|step by step|think harder', re.IGNORECASE),
    re.compile(r'prove that|formal proof|mathematical proof|rigorous proof', re.IGNORECASE),
    re.compile(r'deep analysis|in-depth analysis|thorough analysis', re.IGNORECASE),
    re.compile(r'multi.?step.*(?:reason|logic|problem)', re.IGNORECASE),
    re.compile(r'code architecture.*design|system design.*from scratch', re.IGNORECASE),
    # Math proof patterns
    re.compile(r'证明.*根号|证明.*√|prove.*sqrt|prove.*irrational', re.IGNORECASE),
    re.compile(r'求证|证明如下|请证明|帮我证明', re.IGNORECASE),
]

# Thinking-capable backends in priority order
THINKING_BACKENDS = ['or_deepseek_r1', 'longcat_thinking', 'deepseek_pro']


def detect_thinking_intent(query: str) -> bool:
    """Detect if a query requires deep reasoning / thinking mode.
    Returns True when the query matches patterns for math proofs,
    complex analysis, multi-step logic, or explicit thinking requests.
    """
    if not query:
        return False
    for pattern in _THINKING_PATTERNS:
        if pattern.search(query):
            return True
    return False


def get_thinking_backend() -> str:
    """Get the best available thinking-capable backend.
    Priority: or_deepseek_r1 > longcat_thinking > deepseek_pro > fallback.
    """
    for name in THINKING_BACKENDS:
        if name in BACKENDS and BACKENDS[name].get('key') and cb_allow(name):
            return name
    # Ultimate fallback
    return 'longcat_thinking'


# ── Layer 1: Fast keyword rules ──────────────────────────────────────────────
RULES = [
    # (pattern, intent, confidence)
    # ── 快速直答（trivial，走最快模型）──
    (r'你是什么|什么模型|who are you|what model|你好|hello|hi$|hey$', 'trivial', 0.95),
    (r'^.{1,5}$', 'trivial', 0.90),  # 5字以内的超短问题
    # ── CNC/嵌入式领域 ──
    (r'\$\d+|步数.*mm|steps.*mm|steps_per_mm', 'grbl_config', 0.95),
    (r'归零|homing|\$22|\$23|\$24|\$25|\$26|\$27', 'grbl_config', 0.95),
    (r'G0|G1|G2|G3|G28|G38|G54|G92|M3|M5|M8|圆弧|插补|进给', 'gcode_help', 0.90),
    (r'error:\d+|alarm:\d+|ALARM|报警|错误码', 'grbl_config', 0.90),
    (r'失步|抖动|噪音|异响|卡顿|不动|乱走|偏移', 'cnc_trouble', 0.85),
    (r'限位|limit switch|触发|短路|接线', 'cnc_trouble', 0.85),
    (r'ESP32|WiFi|蓝牙|WebUI|OTA|FreeRTOS|RTOS', 'embedded_dev', 0.85),
    (r'STM32|HAL|CubeMX|定时器|中断|DMA|寄存器', 'embedded_dev', 0.85),
    (r'写.*代码|生成.*代码|实现.*函数|代码示例', 'code_generation', 0.85),
    (r'架构|设计|方案|选型|对比|哪个好', 'architecture', 0.80),
    # ── 工具型任务（DevToolBox 专精）──
    (r'写.*SQL|生成.*SQL|查询.*语句|SELECT|INSERT|UPDATE|DELETE.*FROM', 'tool_task', 0.90),
    (r'正则|regex|匹配.*模式|pattern', 'tool_task', 0.85),
    (r'修复.*代码|fix.*code|debug.*this|帮我改.*bug', 'tool_task', 0.80),
    (r'JSON.*Schema|生成.*schema|转换.*JSON', 'tool_task', 0.85),
    (r'翻译.*代码|convert.*to.*python|改写.*成', 'tool_task', 0.80),
    # ── 图片生成 ──
    (r'画一[个张只幅]|画.*图|生成.*图片|draw|generate.*image|create.*image|画.*picture', 'image_gen', 0.92),
    (r'图片.*生成|AI.*画|AI.*绘|文生图|text.to.image|帮我画|给我画', 'image_gen', 0.90),
    (r'FOC|PID|闭环|编码器|伺服|变频器|VFD', 'complex_theory', 0.85),
    (r'PCB|雕刻|激光|切割|主轴|转速|RPM', 'general_cnc', 0.80),
]

# ── Layer 1.1: Signal Dictionary Classifier (V2) ─────────────────────────────
SIGNAL_DICT = {
    "code_generation": {
        "identity": ["写代码", "实现", "开发", "编写", "create", "implement", "write a"],
        "tools": ["python", "javascript", "typescript", "react", "vue", "rust", "go"],
        "complexity": ["算法", "架构", "设计模式", "重构", "优化"],
    },
    "debugging": {
        "identity": ["报错", "bug", "修复", "error", "fix", "crash", "失败"],
        "tools": ["traceback", "stack trace", "exception", "TypeError", "undefined"],
        "context": ["为什么", "不工作", "怎么解决"],
    },
    "explanation": {
        "identity": ["解释", "什么是", "怎么理解", "原理", "区别", "对比"],
        "context": ["为什么要", "有什么用", "怎么选"],
    },
    "hardware": {
        "identity": ["esp32", "stm32", "arduino", "grbl", "gpio", "固件"],
        "tools": ["串口", "i2c", "spi", "pwm", "adc", "uart"],
        "config": ["\\$\\d+", "参数", "配置", "烧录"],
    },
    "trivial": {
        "identity": ["你好", "hello", "hi", "谢谢", "再见", "在吗"],
    },
}

SIGNAL_WEIGHTS = {
    "identity": 3.0,
    "tools": 2.0,
    "complexity": 1.5,
    "context": 1.5,
    "config": 1.0,
}

def signal_classify(query):
    """Layer 1.1: 信号字典加权评分分类器。返回 (intent_dict, confidence) 或 None。"""
    q = query[:800].lower()
    scores = {}
    evidence = {}
    for intent, dimensions in SIGNAL_DICT.items():
        score = 0.0
        hits = []
        for dim, keywords in dimensions.items():
            weight = SIGNAL_WEIGHTS.get(dim, 1.0)
            for kw in keywords:
                if re.search(kw, q, re.IGNORECASE):
                    score += weight
                    hits.append(f"{dim}:{kw}")
        if score > 0:
            scores[intent] = score
            evidence[intent] = hits

    if not scores:
        return None

    best_intent = max(scores, key=scores.get)
    best_score = scores[best_intent]

    if best_score >= 8.0:
        confidence = 0.95
    elif best_score >= 5.0:
        confidence = 0.90
    elif best_score >= 3.0:
        confidence = 0.75
    else:
        return None

    return {
        'intent': best_intent,
        'complexity': 0.7 if best_intent == 'code_generation' else 0.3,
        'needs_code': best_intent in ('code_generation', 'debugging'),
        'domain_keywords': evidence.get(best_intent, []),
        'cnc_subdomain': 'grbl' if 'grbl' in q else 'general',
        'source': 'signal_v2',
        'confidence': confidence,
    }

def rule_classify(query):
    """Layer 1: fast keyword matching. Returns (intent, confidence) or None."""
    best_intent, best_conf = None, 0.0
    for pattern, intent, conf in RULES:
        if re.search(pattern, query, re.IGNORECASE):
            if conf > best_conf:
                best_intent, best_conf = intent, conf
    if best_conf >= 0.80:
        return {'intent': best_intent, 'complexity': 0.5,
                'needs_code': 'code' in best_intent,
                'domain_keywords': [], 'cnc_subdomain': 'general',
                'source': 'rules', 'confidence': best_conf}
    return None

# ── Layer 1.5: Local Qwen3 Router Model ─────────────────────────────────────
def _load_local_router():
    """懒加载本地路由模型（Qwen3-1.7B R8）。首次调用约 10 秒。"""
    global _local_model, _local_tokenizer, _local_model_failed
    if _local_model is not None or _local_model_failed:
        return
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        import torch
        if DEBUG:
            print('[ROUTER] Loading local Qwen3 router model...', file=sys.stderr)
        _local_tokenizer = AutoTokenizer.from_pretrained(
            LOCAL_ROUTER_MODEL, trust_remote_code=True)
        # 尝试 GPU，显存不够则 fallback 到 CPU
        try:
            _local_model = AutoModelForCausalLM.from_pretrained(
                LOCAL_ROUTER_MODEL, trust_remote_code=True,
                torch_dtype=torch.float16, device_map="auto")
        except Exception:
            if DEBUG:
                print('[ROUTER] GPU failed, falling back to CPU', file=sys.stderr)
            _local_model = AutoModelForCausalLM.from_pretrained(
                LOCAL_ROUTER_MODEL, trust_remote_code=True,
                torch_dtype=torch.float32, device_map="cpu")
        _local_model.eval()
        if DEBUG:
            print('[ROUTER] Local router model loaded OK', file=sys.stderr)
    except Exception as e:
        _local_model_failed = True
        print(f'[ROUTER] Failed to load local model: {e}', file=sys.stderr)


def warmup_router_model():
    """启动时预热本地路由模型，避免首次请求冷启动延迟。
    加载模型到内存 + 跑一次 dummy 推理预热 CUDA kernel。
    """
    global _local_model, _local_tokenizer, _local_model_failed
    try:
        _load_local_router()
        if _local_model is not None and _local_tokenizer is not None:
            # Dummy inference 预热 CUDA kernel / CPU 缓存
            import torch
            dummy = "warmup"
            messages = [
                {"role": "system", "content": "你是LiMa智能路由决策器。"},
                {"role": "user", "content": dummy}
            ]
            text = _local_tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)
            inputs = _local_tokenizer(text, return_tensors="pt").to(_local_model.device)
            with torch.no_grad():
                _local_model.generate(**inputs, max_new_tokens=2, do_sample=False)
            print('[ROUTER] Warmup complete — model ready', file=sys.stderr)
        else:
            print('[ROUTER] Warmup skipped — model not available', file=sys.stderr)
    except Exception as e:
        print(f'[ROUTER] Warmup failed (non-fatal): {e}', file=sys.stderr)


# ── Layer 2: Local model ─────────────────────────────────────────────────────
def call_local(msgs, mt=512, t=0.3):
    """Call LM Studio (OpenAI-compatible)."""
    p = json.dumps({'model': 'local-model', 'messages': msgs,
                    'max_tokens': mt, 'temperature': t}).encode()
    try:
        r = urllib.request.Request(LM_URL, data=p,
                                   headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(r, timeout=30) as resp:
            d = json.loads(resp.read().decode())
        return d['choices'][0]['message']['content']
    except Exception as e:
        return f'[LOCAL_ERR] {e}'

# ── Routing V2: Enhanced Rule Classifier ────────────────────────────────────
_CODE_BLOCK_RE = re.compile(r'```|^\s{4,}\S|def\s+\w+|class\s+\w+|import\s+\w+|from\s+\w+\s+import', re.MULTILINE)
_ENGLISH_TECH_RE = re.compile(r'\b(function|variable|array|object|string|integer|boolean|async|await|promise|callback|interface|generic|type|enum)\b', re.IGNORECASE)

def _enhanced_classify(query, system_prompt="", ide="unknown"):
    """V2 增强规则分类器：正则 + 信号字典 + 上下文信号，覆盖率 95%+。"""
    # Step 1: 正则规则（最高优先级，最快）
    rule_result = rule_classify(query)
    if rule_result and rule_result.get('confidence', 0) >= 0.80:
        return rule_result

    # Step 2: 信号字典分类器（加权评分）
    signal_result = signal_classify(query)
    if signal_result and signal_result.get('confidence', 0) >= 0.70:
        return signal_result

    # Step 3: 上下文增强信号（新增维度）
    ctx_result = _context_signals(query, system_prompt, ide)
    if ctx_result:
        return ctx_result

    # Step 4: 长度启发式
    if len(query.strip()) <= 10:
        return {'intent': 'trivial', 'complexity': 0.1, 'needs_code': False,
                'domain_keywords': [], 'cnc_subdomain': 'general',
                'source': 'length_heuristic', 'confidence': 0.85}

    return None


def _context_signals(query, system_prompt="", ide="unknown"):
    """基于上下文的分类信号：IDE来源、代码块检测、技术术语密度。"""
    q = query[:800]

    # 代码块检测：包含代码的请求直接走 code_generation
    if _CODE_BLOCK_RE.search(q):
        return {'intent': 'code_generation', 'complexity': 0.7, 'needs_code': True,
                'domain_keywords': [], 'cnc_subdomain': 'general',
                'source': 'code_detect', 'confidence': 0.85}

    # IDE 信号：来自 Cursor/VS Code 的请求偏向代码
    if ide.lower() in ('cursor', 'vscode', 'vs code', 'jetbrains', 'idea'):
        tech_density = len(_ENGLISH_TECH_RE.findall(q))
        if tech_density >= 2:
            return {'intent': 'code_generation', 'complexity': 0.6, 'needs_code': True,
                    'domain_keywords': [], 'cnc_subdomain': 'general',
                    'source': 'ide_context', 'confidence': 0.80}

    # 长文本（>300字）且无明确领域信号 → 偏向 architecture/complex
    if len(q) > 300 and not any(re.search(p, q, re.IGNORECASE) for p, _, _ in RULES[:5]):
        return {'intent': 'architecture', 'complexity': 0.7, 'needs_code': False,
                'domain_keywords': [], 'cnc_subdomain': 'general',
                'source': 'length_complexity', 'confidence': 0.72}

    return None


def analyze(query, system_prompt="", ide="unknown", mode="fast"):
    """路由 V2：纯规则分类，零延迟，95%+ 覆盖率。
    不再依赖本地模型或 LLM API。
    """
    # Layer 0: Deep Thinking 检测（优先级最高）
    if detect_thinking_intent(query):
        return {'intent': 'thinking', 'complexity': 0.9, 'needs_code': False,
                'domain_keywords': [], 'cnc_subdomain': 'general',
                'source': 'thinking_detect', 'confidence': 0.95}

    # Layer 1: 增强规则分类（正则 + 信号字典 + 上下文信号）
    result = _enhanced_classify(query, system_prompt, ide)
    if result:
        return result

    # Layer 2: 默认 fallback（不调用任何模型）
    return {'intent': 'unknown', 'complexity': 0.5, 'needs_code': False,
            'domain_keywords': [], 'cnc_subdomain': 'general',
            'source': 'default_fallback', 'confidence': 0.5}

# ── Prompt expansion ─────────────────────────────────────────────────────────
_EXPAND_TEMPLATES = {}
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')

def _load_template(intent_name):
    """按需加载 expand 模板，带缓存。"""
    if intent_name in _EXPAND_TEMPLATES:
        return _EXPAND_TEMPLATES[intent_name]
    mapping = {
        'code_generation': 'expand_code.txt',
        'code_review': 'expand_code.txt',
        'debugging': 'expand_debug.txt',
        'explanation': 'expand_explain.txt',
        'hardware': 'expand_hardware.txt',
        'cnc_operation': 'expand_hardware.txt',
        'grbl_config': 'expand_hardware.txt',
    }
    fname = mapping.get(intent_name, 'expand_default.txt')
    path = os.path.join(_TEMPLATE_DIR, fname)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            tpl = f.read().strip()
    except FileNotFoundError:
        tpl = "Rewrite this query into a detailed technical question.\nUnder 300 chars. Chinese. Output ONLY the expanded question."
    _EXPAND_TEMPLATES[intent_name] = tpl
    return tpl

def expand(query, intent):
    """Expand short query into detailed prompt using intent-specific template."""
    intent_name = intent.get('intent', 'unknown') if isinstance(intent, dict) else str(intent)
    template = _load_template(intent_name)
    prompt = f"{template}\n\nQuery: {query}\nExpanded:"
    resp = call_local([{'role': 'user', 'content': prompt}], mt=200, t=0.3)
    stripped = resp.strip()
    if not stripped or stripped.startswith('[LOCAL_ERR]') or stripped.startswith('{'):
        return query
    return stripped

# ── Response cleaning ────────────────────────────────────────────────────────
CLEAN_PATTERNS = [
    (re.compile(r'claude[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'longcat[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'deepseek[\w\-\.\[\]\/\:]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'gpt-?4[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'gpt-?3[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'chatgpt[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'nvidia[\w\-\.\/]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'nemotron[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'llama[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'mistral[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'qwen[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'\bphi-?4[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'\b(I am |I\'m |made by |created by |developed by )?(anthropic|openai)\b', re.IGNORECASE), ''),
    (re.compile(r'minimax[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'MiniMax[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'deepseek[\w\-\.\/\:]*r1[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'qwen[\w\-\.\/\:]*235[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'openrouter[\w\-\.\/]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'redcode[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'gemini[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'gemma[\w\-\.]*', re.IGNORECASE), PUBLIC_MODEL_NAME),
    (re.compile(r'\bmeta[\s\-]ai\b', re.IGNORECASE), ''),
    (re.compile(r'我是(?:由)?(?:Anthropic|OpenAI|Google|Meta|DeepSeek|阿里|百度|字节)(?:开发|训练|创建|制作)', re.IGNORECASE), f'我是{PUBLIC_MODEL_NAME}'),
    (re.compile(r'作为(?:一个)?(?:AI语言模型|大语言模型|人工智能助手|AI助手)', re.IGNORECASE), f'作为{PUBLIC_MODEL_NAME}'),
    (re.compile(r"I(?:'m| am) (?:an AI (?:language )?model|a large language model|Claude|GPT|Gemini|DeepSeek)", re.IGNORECASE), f'I am {PUBLIC_MODEL_NAME}'),
    (re.compile(r'(?:trained|developed|created|made|built) by (?:Anthropic|OpenAI|Google|Meta|DeepSeek|Alibaba)', re.IGNORECASE), f'developed by DongLiCao'),
]

def clean_response(text, backend_name=''):
    """清洗响应：隐藏底层模型/供应商信息。"""
    if not text or '[ERR]' in text[:15]:
        return '服务暂时不可用，请稍后重试'
    for pattern, repl in CLEAN_PATTERNS:
        text = pattern.sub(repl, text)
    return text

# ── Quality Assurance Layer ──────────────────────────────────────────────────
# GRBL 参数合理范围（防止 AI 编造错误参数值）
GRBL_PARAM_RANGES = {
    '$0': (1, 255),       '$1': (0, 255),       '$2': (0, 7),
    '$3': (0, 7),         '$4': (0, 1),          '$5': (0, 1),
    '$6': (0, 1),         '$10': (0, 255),       '$11': (0.0, 10.0),
    '$12': (0.0, 1.0),    '$13': (0, 1),         '$20': (0, 1),
    '$21': (0, 1),        '$22': (0, 1),         '$23': (0, 7),
    '$24': (1.0, 10000.0),'$25': (1.0, 100000.0),'$26': (0, 255),
    '$27': (0.0, 100.0),  '$30': (1, 100000),    '$31': (0, 100000),
    '$32': (0, 1),
    '$100': (1.0, 10000.0), '$101': (1.0, 10000.0), '$102': (1.0, 10000.0),
    '$110': (1.0, 100000.0),'$111': (1.0, 100000.0),'$112': (1.0, 100000.0),
    '$120': (1.0, 100000.0),'$121': (1.0, 100000.0),'$122': (1.0, 100000.0),
    '$130': (0.0, 100000.0),'$131': (0.0, 100000.0),'$132': (0.0, 100000.0),
}

# 不确定性信号词
UNCERTAINTY_SIGNALS = [
    '我不确定', '可能是', '大概', '也许', '不太清楚', '不确定',
    '需要更多信息', '取决于具体情况', '可能需要', '建议测试',
    'not sure', 'might be', 'possibly', 'uncertain',
]

# 免责声明模式（清洗掉）
DISCLAIMER_PATTERNS = [
    re.compile(r'作为AI.*?[。\n]', re.DOTALL),
    re.compile(r'我无法保证.*?[。\n]', re.DOTALL),
    re.compile(r'建议咨询专业.*?[。\n]', re.DOTALL),
    re.compile(r'请注意.*?安全.*?[。\n]', re.DOTALL),
    re.compile(r'以上仅供参考.*?[。\n]', re.DOTALL),
    re.compile(r'作为.*?语言模型.*?[。\n]', re.DOTALL),
]

def validate_grbl_params(text):
    """检测回答里的 GRBL 参数值是否在合理范围内，返回警告列表。"""
    warnings = []
    for match in re.finditer(r'(\$\d+)\s*[=:]\s*([\d.]+)', text):
        param = match.group(1)
        try:
            value = float(match.group(2))
        except ValueError:
            continue
        if param in GRBL_PARAM_RANGES:
            lo, hi = GRBL_PARAM_RANGES[param]
            if not (lo <= value <= hi):
                warnings.append(f'{param}={value} 超出合理范围 [{lo}, {hi}]')
    return warnings

def is_truncated(text):
    """检测回答是否被截断。"""
    if not text or len(text) < 20:
        return True
    if text.count('```') % 2 != 0:
        return True
    stripped = text.rstrip()
    if stripped and stripped[-1] not in '。！？.!?\n）)】]':
        if len(stripped) > 100 and stripped[-1].isalnum():
            return True
    return False

def detect_uncertainty(text):
    """检测回答是否包含不确定性信号。"""
    if not text:
        return False
    return any(s in text for s in UNCERTAINTY_SIGNALS)

def remove_disclaimers(text):
    """清洗掉常见的 AI 免责声明。"""
    if not text:
        return text or ''
    for pattern in DISCLAIMER_PATTERNS:
        text = pattern.sub('', text)
    return text.strip()

def qa_check(text, intent=None, backend=None):
    """质量检查：验证参数范围、检测截断、清洗免责声明。
    返回 (checked_text, issues) 其中 issues 是问题列表。
    """
    issues = []
    text = remove_disclaimers(text)
    if is_truncated(text):
        issues.append('truncated')
    if len(text.strip()) < 20 and backend != 'local':
        issues.append('low_quality')
    if intent and intent.get('cnc_subdomain') == 'grbl':
        param_warnings = validate_grbl_params(text)
        if param_warnings:
            issues.append('param_warning')
            text += '\n\n⚠️ 参数提示：' + '；'.join(param_warnings) + '，请结合实际硬件验证。'
    return text, issues

# ── API backend calls ────────────────────────────────────────────────────────
def _call_cf_vision(msgs, mt, _t0):
    """Cloudflare Vision 原生端点调用（OpenAI-compat 不支持图片格式）。"""
    cf_token = os.environ.get('CLOUDFLARE_TOKEN', '')
    cf_account = os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')
    if not cf_token or not cf_account:
        return None
    url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account}/ai/run/@cf/meta/llama-3.2-11b-vision-instruct"
    body = json.dumps({'messages': msgs, 'max_tokens': mt}).encode()
    h = {'Content-Type': 'application/json',
         'Authorization': f'Bearer {cf_token}',
         'User-Agent': 'LiMa/2.0'}
    try:
        r = urllib.request.Request(url, data=body, headers=h)
        with urllib.request.urlopen(r, timeout=15) as resp:
            d = json.loads(resp.read().decode())
        answer = d.get('result', {}).get('response', '')
        if answer:
            cb_record('cf_vision', True, int((time.time() - _t0) * 1000))
            return clean_response(answer, 'cf_vision')
        return None
    except Exception as e:
        if DEBUG:
            print(f'[DEBUG] cf_vision error: {e}', file=sys.stderr)
        cb_record('cf_vision', False)
        return None


def call_api(name, msgs, mt=1024, ide="unknown"):
    """Call an external API backend."""
    # 熔断检查
    if not cb_allow(name):
        if DEBUG:
            print(f'[CB] {name}: blocked by circuit breaker', file=sys.stderr)
        return None  # 返回 None 表示熔断，由调用方降级
    _t0 = time.time()
    b = BACKENDS.get(name)
    if not b or not b['key']:
        cb_record(name, False)
        return f'[ERR] Backend {name} unavailable (no key)'
    auth_style = b.get('auth', 'x-api-key')

    # Cloudflare Vision 特殊处理：使用原生 /ai/run/ 端点
    if name == 'cf_vision' and _has_vision_content(msgs):
        return _call_cf_vision(msgs, mt, _t0)

    if b['fmt'] == 'anthropic':
        # no_system 后端（如 Omni）：不传 system，content 用 list 格式
        if b.get('no_system'):
            omni_msgs = [
                {'role': m['role'],
                 'content': [{'type': 'text', 'text': m['content']}]
                             if isinstance(m['content'], str) else m['content']}
                for m in msgs
            ]
            body = {'model': b['model'], 'max_tokens': mt, 'messages': omni_msgs}
        else:
            sys_prompt = SYS
            if ide and ide not in ("unknown", "未知"):
                sys_prompt += f"\n\n[环境] 用户正在 {ide} 中使用你。该IDE具备文件读写、终端执行、代码搜索等工具能力。请正常回应用户的文件操作请求，不要说'无法访问本地文件'。"
            body = {'model': b['model'], 'max_tokens': mt, 'system': sys_prompt, 'messages': msgs}
        p = json.dumps(body).encode()
        if auth_style == 'bearer':
            h = {'Content-Type': 'application/json',
                 'Authorization': f"Bearer {b['key']}",
                 'anthropic-version': '2023-06-01'}
        else:
            h = {'Content-Type': 'application/json',
                 'x-api-key': b['key'], 'anthropic-version': '2023-06-01'}
    else:
        sys_prompt = SYS
        if ide and ide not in ("unknown", "未知"):
            sys_prompt += f"\n\n[环境] 用户正在 {ide} 中使用你。该IDE具备文件读写、终端执行、代码搜索等工具能力。请正常回应用户的文件操作请求，不要说'无法访问本地文件'。"
        p = json.dumps({'model': b['model'], 'max_tokens': mt,
                        'messages': [{'role': 'system', 'content': sys_prompt}] + msgs}).encode()
        h = {'Content-Type': 'application/json',
             'Authorization': f"Bearer {b['key']}",
             'User-Agent': 'LiMa/2.0'}
    try:
        r = urllib.request.Request(b['url'], data=p, headers=h)
        _timeout = b.get('timeout', 60)
        opener = _get_opener(name)
        if opener:
            with opener.open(r, timeout=_timeout) as resp:
                d = json.loads(resp.read().decode())
        else:
            with urllib.request.urlopen(r, timeout=_timeout) as resp:
                d = json.loads(resp.read().decode())
        if b['fmt'] == 'anthropic':
            answer = d['content'][0].get('text', '') or d['content'][0].get('thinking', '') or json.dumps(d, ensure_ascii=False)
        else:
            msg = d['choices'][0]['message']
            # 推理模型（如 minimax-m25, Qwen3）content 可能为 None，回退到 reasoning_content 字段
            answer = msg.get('content') or msg.get('reasoning_content') or msg.get('reasoning') or json.dumps(d, ensure_ascii=False)
        cb_record(name, True, int((time.time() - _t0) * 1000))
        return clean_response(answer, name)
    except Exception as e:
        print(f'[DEBUG] {name} error: {e}', file=sys.stderr)
        cb_record(name, False)
        return '服务暂时不可用，请稍后重试'


# ── DevToolBox API (工具型端点，非 OpenAI 兼容) ──────────────────────────────
DTB_BASE = 'https://devtoolbox-api.devtoolbox-api.workers.dev/ai'
DTB_ENDPOINTS = {
    'sql': {'field': 'description', 'result_key': 'sql'},
    'regex': {'field': 'description', 'result_key': 'regex'},
    'fix-code': {'field': 'code', 'result_key': 'fix'},
    'explain-code': {'field': 'code', 'result_key': 'explanation'},
    'json-schema': {'field': 'json', 'result_key': 'result'},
    'summarize': {'field': 'text', 'result_key': 'result'},
}

def call_devtoolbox(task_type, input_text):
    """调用 DevToolBox 工具型 API。返回结果文本或 None。"""
    ep = DTB_ENDPOINTS.get(task_type)
    if not ep:
        return None
    try:
        payload = json.dumps({ep['field']: input_text}).encode()
        req = urllib.request.Request(
            f'{DTB_BASE}/{task_type}', data=payload,
            headers={'Content-Type': 'application/json', 'User-Agent': 'LiMa/2.0'})
        opener = _get_opener('devtoolbox')
        if opener:
            resp = opener.open(req, timeout=15)
        else:
            resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        return data.get(ep['result_key']) or data.get('result') or json.dumps(data, ensure_ascii=False)
    except Exception as e:
        if DEBUG:
            print(f'[DTB] {task_type} error: {e}', file=sys.stderr)
        return None


def _detect_tool_type(query):
    """检测 tool_task 的具体工具类型，用于路由到 DevToolBox 对应端点。"""
    q = query.lower()
    if re.search(r'sql|查询|select|insert|update|delete.*from|数据库', q):
        return 'sql'
    if re.search(r'正则|regex|pattern|匹配模式', q):
        return 'regex'
    if re.search(r'修复|fix|debug|改.*bug|纠错', q):
        return 'fix-code'
    if re.search(r'解释.*代码|explain.*code|这段代码', q):
        return 'explain-code'
    if re.search(r'json.*schema|schema', q, re.IGNORECASE):
        return 'json-schema'
    if re.search(r'摘要|总结|summarize|概括', q):
        return 'summarize'
    return None


# ── Pollinations Image Generation ────────────────────────────────────────────
def generate_image(prompt, width=512, height=512):
    """调用 Pollinations 图片生成 API，返回图片 URL。"""
    from urllib.parse import quote
    encoded = quote(prompt)
    url = f'https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'LiMa/2.0'})
        resp = urllib.request.urlopen(req, timeout=30)
        if resp.status == 200:
            return url
    except Exception:
        pass
    return url


# ── Streaming API Call ─────────────────────────────────────────────────────────
def _build_request_body(name, msgs, mt=1024, ide="unknown", stream=False):
    """Build request body and headers for a backend call.
    Returns (body_bytes, headers_dict, fmt, timeout_seconds).
    Used by both call_api() and call_api_stream().
    """
    b = BACKENDS.get(name)
    if not b:
        return None, None, None, 60
    auth_style = b.get('auth', 'x-api-key')

    if b['fmt'] == 'anthropic':
        if b.get('no_system'):
            omni_msgs = [
                {'role': m['role'],
                 'content': [{'type': 'text', 'text': m['content']}]
                             if isinstance(m['content'], str) else m['content']}
                for m in msgs
            ]
            body = {'model': b['model'], 'max_tokens': mt, 'messages': omni_msgs}
        else:
            sys_prompt = SYS
            if ide and ide not in ("unknown", "未知"):
                sys_prompt += f"\n\n[环境] 用户正在 {ide} 中使用你。该IDE具备文件读写、终端执行、代码搜索等工具能力。请正常回应用户的文件操作请求，不要说'无法访问本地文件'。"
            body = {'model': b['model'], 'max_tokens': mt, 'system': sys_prompt, 'messages': msgs}
        if stream:
            body['stream'] = True
        p = json.dumps(body).encode()
        if auth_style == 'bearer':
            h = {'Content-Type': 'application/json',
                 'Authorization': f"Bearer {b['key']}",
                 'anthropic-version': '2023-06-01'}
        else:
            h = {'Content-Type': 'application/json',
                 'x-api-key': b['key'], 'anthropic-version': '2023-06-01'}
    else:
        sys_prompt = SYS
        if ide and ide not in ("unknown", "未知"):
            sys_prompt += f"\n\n[环境] 用户正在 {ide} 中使用你。该IDE具备文件读写、终端执行、代码搜索等工具能力。请正常回应用户的文件操作请求，不要说'无法访问本地文件'。"
        body = {'model': b['model'], 'max_tokens': mt,
                'messages': [{'role': 'system', 'content': sys_prompt}] + msgs}
        if stream:
            body['stream'] = True
        # Qwen thinking mode: disable for unclose_qwen to get content directly
        if name == 'unclose_qwen':
            body['chat_template_kwargs'] = {'enable_thinking': False}
        p = json.dumps(body).encode()
        h = {'Content-Type': 'application/json',
             'Authorization': f"Bearer {b['key']}",
             'User-Agent': 'LiMa/2.0'}

    return p, h, b['fmt'], b.get('timeout', 60)


def call_api_stream(name, msgs, mt=1024, ide="unknown"):
    """Stream response chunks from a backend. Synchronous generator.
    Yields text chunks (str) as they arrive from the backend SSE stream.
    """
    if not cb_allow(name):
        if DEBUG:
            print(f'[CB] {name}: blocked by circuit breaker (stream)', file=sys.stderr)
        yield '服务暂时不可用，请稍后重试'
        return
    b = BACKENDS.get(name)
    if not b or not b['key']:
        yield f'[ERR] Backend {name} unavailable (no key)'
        return

    p, h, fmt, timeout = _build_request_body(name, msgs, mt, ide, stream=True)
    if p is None:
        yield f'[ERR] Backend {name} not found'
        return

    _t0 = time.time()
    buffer = b""
    try:
        r = urllib.request.Request(b['url'], data=p, headers=h)
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                buffer += chunk
                # Process complete lines from buffer
                while b'\n' in buffer:
                    line_end = buffer.index(b'\n')
                    line = buffer[:line_end].decode('utf-8', errors='replace').strip()
                    buffer = buffer[line_end + 1:]
                    if not line:
                        continue
                    if fmt == 'openai':
                        if line.startswith('data: '):
                            data_str = line[6:]
                            if data_str == '[DONE]':
                                break
                            try:
                                data = json.loads(data_str)
                                content = data['choices'][0]['delta'].get('content', '')
                                if content:
                                    yield content
                            except (json.JSONDecodeError, KeyError, IndexError):
                                pass
                    else:  # anthropic
                        if line.startswith('data: '):
                            try:
                                data = json.loads(line[6:])
                                if data.get('type') == 'content_block_delta':
                                    delta = data.get('delta', {})
                                    if delta.get('type') == 'text_delta':
                                        text = delta.get('text', '')
                                        if text:
                                            yield text
                            except json.JSONDecodeError:
                                pass
        cb_record(name, True, int((time.time() - _t0) * 1000))
    except Exception as e:
        if DEBUG:
            print(f'[STREAM] {name} error: {e}', file=sys.stderr)
        cb_record(name, False)
        yield '服务暂时不可用，请稍后重试'

# ── IDE metadata routing hints ──────────────────────────────────────────────
def _ide_routing_hint(ide, system_prompt, query):
    """根据 IDE 元数据推断最优后端偏好。"""
    sp_lower = system_prompt.lower() if system_prompt else ''
    q_lower = query.lower()

    # Rust/Go 项目偏好 Claude（强类型推理）
    if any(ext in sp_lower for ext in ['.rs', 'rust', 'cargo']):
        return 'claude'
    if any(ext in sp_lower for ext in ['.go', 'golang', 'go.mod']):
        return 'claude'

    # 嵌入式/硬件项目偏好长上下文模型
    if any(kw in q_lower for kw in ['esp32', 'stm32', 'arduino', 'grbl', 'firmware']):
        return 'longcat'

    # Cursor 用户通常需要快速响应
    if ide == 'cursor':
        return 'deepseek_flash'

    return None

# ── Main router ──────────────────────────────────────────────────────────────
def select_backend(query, prefer=None, system_prompt="", ide="unknown", messages=None):
    """Select best backend WITHOUT making API call. Returns (backend, api_msgs)."""
    intent = analyze(query, system_prompt=system_prompt, ide=ide)
    ide_prefer = _ide_routing_hint(ide, system_prompt, query)
    model_backend = intent.get('backend')
    effective_prefer = prefer or model_backend or ide_prefer
    intent_name = intent.get('intent', 'unknown')
    # 多模态检测：如果消息包含图片，强制使用 vision chain
    if _has_vision_content(messages):
        intent_name = 'vision'
    fallback_chain = get_fallback_chain_sorted(intent_name, prefer=effective_prefer)
    backend = fallback_chain[0] if fallback_chain else 'longcat_chat'

    expanded_q = expand(query, intent)
    if messages and len(messages) > 1:
        api_msgs = [m for m in messages if m.get('role') in ('user', 'assistant')]
    else:
        api_msgs = [{'role': 'user', 'content': expanded_q}]
    return backend, api_msgs


def route(query, prefer=None, system_prompt="", ide="unknown", messages=None):
    """Route a query: analyze intent -> expand -> call best backend.
    messages: 完整对话历史 (list of dicts)，传递给后端保持上下文。
    """
    t0 = time.time()
    result = {'query': query}

    # Intent analysis (two-layer)
    intent = analyze(query, system_prompt=system_prompt, ide=ide)
    result['intent'] = intent
    result['classify_ms'] = int((time.time() - t0) * 1000)

    # IDE 元数据增强路由偏好
    ide_prefer = _ide_routing_hint(ide, system_prompt, query)
    # 优先使用路由模型推荐的 backend，其次 IDE 偏好，最后调用者指定
    model_backend = intent.get('backend')
    effective_prefer = prefer or model_backend or ide_prefer

    # 获取降级链
    intent_name = intent.get('intent', 'unknown')
    # 多模态检测：如果消息包含图片，强制使用 vision chain
    if _has_vision_content(messages):
        intent_name = 'vision'

    # ── 图片生成：直接返回 Pollinations URL ──
    if intent_name == 'image_gen':
        img_url = generate_image(query)
        result['backend'] = 'pollinations_image'
        result['answer'] = f'![生成的图片]({img_url})\n\n图片已生成，点击上方链接查看。'
        result['total_ms'] = int((time.time() - t0) * 1000)
        return result

    # ── 工具型任务：优先 DevToolBox，失败再走 fallback chain ──
    if intent_name == 'tool_task':
        dtb_type = _detect_tool_type(query)
        if dtb_type:
            dtb_result = call_devtoolbox(dtb_type, query)
            if dtb_result:
                result['backend'] = f'devtoolbox_{dtb_type}'
                result['answer'] = dtb_result
                result['total_ms'] = int((time.time() - t0) * 1000)
                return result

    # ── one-api 优先路由（负载均衡 + 额度追踪 + 自动故障转移）──
    if ONEAPI_ENABLED:
        group = INTENT_TO_GROUP.get(intent_name, 'general')
        expanded_q = expand(query, intent)
        if messages and len(messages) > 1:
            api_msgs = [m for m in messages if m.get('role') in ('user', 'assistant')]
        else:
            api_msgs = [{'role': 'user', 'content': expanded_q}]

        oneapi_answer = call_oneapi(group, api_msgs, mt=1024)
        if oneapi_answer:
            result['backend'] = f'oneapi/{group}'
            result['answer'] = clean_response(oneapi_answer, f'oneapi_{group}')
            result['total_ms'] = int((time.time() - t0) * 1000)
            return result
        if DEBUG:
            print(f'[ROUTE] one-api failed for group={group}, falling back to direct', file=sys.stderr)

    # ── 直连 fallback（one-api 不可用时的降级路径）──
    fallback_chain = get_fallback_chain(intent_name, prefer=effective_prefer)
    backend = fallback_chain[0] if fallback_chain else 'longcat'
    result['backend'] = backend
    result['fallback_chain'] = fallback_chain

    # 尝试降级链中的每个后端
    answer = None
    used_backend = backend
    expanded_q = expand(query, intent)
    tried_backends = set()

    # 构建发送给后端的消息：优先使用完整对话历史
    if _has_vision_content(messages):
        # 视觉消息：直接透传原始 messages（保留 image_url）
        api_msgs = [m for m in messages if m.get('role') in ('user', 'assistant')]
    elif messages and len(messages) > 1:
        api_msgs = [m for m in messages if m.get('role') in ('user', 'assistant')]
    else:
        api_msgs = [{'role': 'user', 'content': expanded_q}]

    for attempt_backend in fallback_chain:
        tried_backends.add(attempt_backend)
        if attempt_backend == 'local':
            ans = call_local([
                {'role': 'system', 'content': SYS},
                {'role': 'user', 'content': query},
            ], mt=800)
            if ans and not ans.startswith('[LOCAL_ERR]'):
                answer = ans
                used_backend = 'local'
                break
            continue

        ans = call_api(attempt_backend, api_msgs, ide=ide)
        if ans is not None and not ans.startswith('[ERR]') and '暂时不可用' not in ans:
            answer = ans
            used_backend = attempt_backend
            if attempt_backend != backend and DEBUG:
                print(f'[FALLBACK] {backend} -> {attempt_backend}', file=sys.stderr)
            break

    if answer is None:
        answer = '服务暂时不可用，请稍后重试'

    result['expanded'] = expanded_q
    result['backend'] = used_backend
    result['answer'] = answer

    result['total_ms'] = int((time.time() - t0) * 1000)

    # 质量检查
    answer, issues = qa_check(result['answer'], intent=intent, backend=used_backend)
    result['answer'] = answer

    # 质量不达标时尝试下一个 fallback（仅重试一次）
    if issues and 'low_quality' in issues and used_backend != 'claude':
        remaining = [b for b in fallback_chain if b not in tried_backends and b != 'local']
        if remaining:
            retry_backend = remaining[0]
            retry_ans = call_api(retry_backend, api_msgs, ide=ide)
            if retry_ans and not retry_ans.startswith('[ERR]') and '暂时不可用' not in retry_ans:
                retry_clean = retry_ans
                retry_answer, retry_issues = qa_check(retry_clean, intent=intent, backend=retry_backend)
                if 'low_quality' not in retry_issues:
                    result['answer'] = retry_answer
                    used_backend = retry_backend
                    result['backend'] = used_backend
                    result['quality_retry'] = True
                    if DEBUG:
                        print(f'[QUALITY_RETRY] {result.get("backend")} -> {retry_backend}', file=sys.stderr)

    # 不确定性检测：自动升级到更强模型
    if detect_uncertainty(result['answer']) and used_backend not in ('claude', 'deepseek_pro'):
        upgraded = call_api('deepseek_pro', api_msgs)
        if upgraded and not upgraded.startswith('[ERR]') and '暂时不可用' not in upgraded and not detect_uncertainty(upgraded):
            result['answer'] = clean_response(upgraded, 'deepseek_pro')
            result['upgraded'] = True

    # 截断检测：自动续写（用实际成功的后端）
    if 'truncated' in issues and used_backend != 'local':
        cont_msgs = list(api_msgs) + [
            {'role': 'assistant', 'content': result['answer']},
            {'role': 'user', 'content': '请继续完成上面的回答。'},
        ]
        continuation = call_api(used_backend, cont_msgs, mt=512)
        if continuation and not continuation.startswith('[ERR]'):
            result['answer'] = result['answer'] + '\n' + clean_response(continuation, used_backend)

    # 写入蒸馏队列（失败不影响主流程）
    _log_to_distill_queue(query, result.get('answer', ''), intent, result.get('backend', ''))

    return result

# ── Distill Queue Logger ─────────────────────────────────────────────────────
DISTILL_QUEUE_DIR = os.path.join(os.path.dirname(__file__), 'data', 'distill_queue', 'pending')


def _quick_score(query: str, answer: str) -> float:
    """快速质量评分，纯本地规则，0ms延迟。返回 0.0-1.0。"""
    if not answer:
        return 0.0

    # 长度分（0.3权重）
    length = len(answer)
    if 100 <= length <= 2000:
        len_score = 1.0
    elif length < 50:
        len_score = 0.0
    elif length < 100:
        len_score = (length - 50) / 50
    else:  # > 2000
        len_score = max(0.7, 1.0 - (length - 2000) / 5000)

    # 格式分（0.3权重）
    fmt_score = 0.0
    if '```' in answer and answer.count('```') % 2 == 0:
        fmt_score += 0.4
    if any(c.isdigit() for c in answer):
        fmt_score += 0.3
    if any(marker in answer for marker in ['1.', '2.', '- ', '* ', '步骤']):
        fmt_score += 0.3

    # 完整性分（0.2权重）
    comp_score = 1.0
    bad_markers = ['抱歉', '无法', '不确定', '我不能', '暂时不可用']
    if any(m in answer for m in bad_markers):
        comp_score = 0.3

    # 相关性分（0.2权重）
    query_words = set(query.lower().replace('?', '').replace('？', '').split())
    answer_lower = answer.lower()
    if query_words:
        overlap = sum(1 for w in query_words if w in answer_lower and len(w) > 1)
        rel_score = min(1.0, overlap / max(len(query_words) * 0.3, 1))
    else:
        rel_score = 0.5

    total = len_score * 0.3 + fmt_score * 0.3 + comp_score * 0.2 + rel_score * 0.2
    return round(total, 3)

def _log_to_distill_queue(query: str, answer: str, intent: dict, backend: str) -> None:
    """将路由结果写入蒸馏队列，供 distill_scheduler 使用。

    只记录满足以下条件的条目：
    1. 后端不是 'local'（本地模型回答不需要蒸馏）
    2. 回答不含错误标志
    3. 日志功能已启用（DISTILL_LOG=1 环境变量）
    """
    if os.environ.get('DISTILL_LOG', '0') != '1':
        return
    if backend == 'local':
        return
    if not answer or '暂时不可用' in answer:
        return

    try:
        os.makedirs(DISTILL_QUEUE_DIR, exist_ok=True)
        import hashlib, datetime
        score = _quick_score(query, answer)
        entry = {
            'query': query,
            'answer': answer,
            'intent': intent.get('intent', 'unknown'),
            'complexity': intent.get('complexity', 0.5),
            'source_backend': backend,
            'quality_score': score,
            'routing_correct': score >= 0.7,
            'logged_at': datetime.datetime.now().isoformat(),
        }
        qhash = hashlib.md5(query.encode()).hexdigest()[:8]
        ts = time.strftime('%Y%m%d_%H%M%S')
        fname = os.path.join(DISTILL_QUEUE_DIR, f'{ts}_{qhash}.json')
        with open(fname, 'w', encoding='utf-8') as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)
        if DEBUG:
            print(f'[DISTILL] logged: {query[:30]}... -> {backend}', file=sys.stderr)
    except Exception as e:
        if DEBUG:
            print(f'[DISTILL] log failed: {e}', file=sys.stderr)

# ── Vision (Photo-to-Answer) Detection ────────────────────────────────────────
VISION_BACKENDS = ['longcat_omni', 'or_deepseek_r1']

VISION_SYSTEM_PROMPT = "你是一位耐心的老师。用户上传了一道题目的图片。请：1. 识别题目内容 2. 分步骤解答 3. 给出最终答案。如果是选择题，明确指出正确选项。"


# ═══ Vision 检测/转换 (已提取 → vision_handler.py) ══════════════════════════════
def detect_vision_request(messages: list) -> bool:
    """Detect if any message contains image content (OpenAI vision format).
    OpenAI vision format: content is a list with {"type": "image_url", ...} blocks.
    """
    if not messages:
        return False
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "image_url":
                    return True
    return False


def convert_openai_vision_to_anthropic(messages: list) -> list:
    """Convert OpenAI vision format messages to Anthropic format.
    OpenAI: {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
    Anthropic: {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "..."}}
    """
    converted = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "user")
        content = msg.get("content")
        if isinstance(content, str):
            converted.append({"role": role, "content": [{"type": "text", "text": content}]})
        elif isinstance(content, list):
            new_blocks = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    new_blocks.append({"type": "text", "text": block.get("text", "")})
                elif block.get("type") == "image_url":
                    image_url = block.get("image_url", {})
                    url = image_url.get("url", "")
                    # Parse data URI: data:image/jpeg;base64,<data>
                    if url.startswith("data:"):
                        # Extract media type and base64 data
                        header, _, data = url.partition(",")
                        # header = "data:image/jpeg;base64"
                        media_type = header.split(":")[1].split(";")[0] if ":" in header else "image/jpeg"
                        new_blocks.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": data,
                            }
                        })
                    else:
                        # URL-based image - pass as-is in text form (fallback)
                        new_blocks.append({"type": "text", "text": f"[Image URL: {url}]"})
                else:
                    new_blocks.append(block)
            converted.append({"role": role, "content": new_blocks})
        else:
            converted.append({"role": role, "content": [{"type": "text", "text": str(content)}]})
    return converted


# ── Image Generation Intent Detection ────────────────────────────────────────
_IMAGE_PATTERNS = [
    re.compile(r'画一[个只张幅副]', re.IGNORECASE),
    re.compile(r'画个', re.IGNORECASE),
    re.compile(r'生成.*图', re.IGNORECASE),
    re.compile(r'画.*图', re.IGNORECASE),
    re.compile(r'设计.*logo', re.IGNORECASE),
    re.compile(r'generate.*image', re.IGNORECASE),
    re.compile(r'\bdraw\b', re.IGNORECASE),
    re.compile(r'create.*picture', re.IGNORECASE),
    re.compile(r'画.*画', re.IGNORECASE),
    re.compile(r'帮我画', re.IGNORECASE),
    re.compile(r'给我画', re.IGNORECASE),
    re.compile(r'生成.*照片', re.IGNORECASE),
    re.compile(r'生成.*插画', re.IGNORECASE),
    re.compile(r'make.*image', re.IGNORECASE),
]

# Extraction patterns: strip the "command" prefix to get the description
_IMAGE_STRIP_PATTERNS = [
    re.compile(r'^(请|帮我|给我|帮忙)?(画一[个只张幅副]|画个|画一下|画)'),
    re.compile(r'^(请|帮我|给我)?生成(一[张幅副])?(.*?)(图片?|图像|照片|插画)的?'),
    re.compile(r'^(请|帮我|给我)?设计(一个)?'),
    re.compile(r'^(please\s+)?(generate|draw|create|make)\s+(an?\s+)?(image|picture|photo)\s*(of\s+)?', re.IGNORECASE),
]


def detect_image_intent(query: str) -> tuple:
    """Detect if a query is an image generation request.
    Returns (is_image_request: bool, extracted_prompt: str).
    The extracted prompt is optimized for Pollinations.ai.
    """
    if not query:
        return (False, "")

    is_image = False
    for pattern in _IMAGE_PATTERNS:
        if pattern.search(query):
            is_image = True
            break

    if not is_image:
        return (False, "")

    # Extract the description part
    prompt = query.strip()
    for strip_pat in _IMAGE_STRIP_PATTERNS:
        prompt = strip_pat.sub('', prompt).strip()

    # If stripping removed everything, use original query
    if not prompt or len(prompt) < 2:
        prompt = query.strip()

    # Remove trailing punctuation
    prompt = re.sub(r'[。！？.!?]+$', '', prompt).strip()

    # For Chinese prompts, prepend quality keywords for better generation
    has_chinese = bool(re.search(r'[一-鿿]', prompt))
    if has_chinese:
        prompt = f"high quality, detailed, {prompt}"

    return (True, prompt)

