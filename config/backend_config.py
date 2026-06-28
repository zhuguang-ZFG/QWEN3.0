"""Backend credential centralization (P1-2 phase 2).

Provider-specific credentials are grouped here so backend definitions and
automation code do not repeat ``os.environ.get()`` calls. All values are read
once at module import time; tests should patch the module-level singletons.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CloudflareCredentials:
    """Cloudflare Workers AI account credentials."""

    account_id: str = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    token: str = os.environ.get("CLOUDFLARE_TOKEN", "")

    @property
    def configured(self) -> bool:
        return bool(self.account_id and self.token)

    def chat_url(self) -> str:
        return f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/v1/chat/completions"

    def search_url(self) -> str:
        return f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/models/search"


CLOUDFLARE = CloudflareCredentials()

# Provider API keys used across backend definitions. Read once at import time.
GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
MISTRAL_API_KEY: str = os.environ.get("MISTRAL_API_KEY", "")
OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")
GITHUB_TOKEN: str = os.environ.get("GITHUB_TOKEN", "")
GOOGLE_AI_KEY: str = os.environ.get("GOOGLE_AI_KEY", "")
NVIDIA_API_KEY: str = os.environ.get("NVIDIA_API_KEY", "")
MODELSCOPE_API_KEY: str = os.environ.get("MODELSCOPE_API_KEY", "")

# Chinese commercial providers
ZHIPU_API_KEY: str = os.environ.get("ZHIPU_API_KEY", "")
SILICONFLOW_API_KEY: str = os.environ.get("SILICONFLOW_API_KEY", "")
BAIDU_API_KEY: str = os.environ.get("BAIDU_API_KEY", "")
VOLCENGINE_API_KEY: str = os.environ.get("VOLCENGINE_API_KEY", "")
ALIYUN_API_KEY: str = os.environ.get("ALIYUN_API_KEY", "")
TENCENT_API_KEY: str = os.environ.get("TENCENT_API_KEY", "")
CHINAMOBILE_API_KEY: str = os.environ.get("CHINAMOBILE_API_KEY", "")
TOKENROUTER_API_KEY: str = os.environ.get("TOKENROUTER_API_KEY", "")

# Community / free backends
FREE_OPENAI_NEXT_KEY: str = os.environ.get("FREE_OPENAI_NEXT_KEY", "")
FREE_CENTOS_KEY: str = os.environ.get("FREE_CENTOS_KEY", "")
FREE_MUYUAN_KEY: str = os.environ.get("FREE_MUYUAN_KEY", "")
FREE_AJIAKESI_KEY: str = os.environ.get("FREE_AJIAKESI_KEY", "")
FREE_TEAM_SPEED_KEY: str = os.environ.get("FREE_TEAM_SPEED_KEY", "")
LLM7_API_KEY: str = os.environ.get("LLM7_API_KEY", "")

# Tunnel / proxy URLs
DDG_TUNNEL_URL: str = os.environ.get("DDG_TUNNEL_URL", "http://localhost:4500")
OLLAMA_TUNNEL_URL: str = os.environ.get("OLLAMA_TUNNEL_URL", "http://localhost:11434")
VPS_HOST: str = os.environ.get("VPS_HOST", "47.112.162.80")

# Commercial platform keys
CEREBRAS_API_KEY: str = os.environ.get("CEREBRAS_API_KEY", "")
NAGA_API_KEY: str = os.environ.get("NAGA_API_KEY", "")
FREETHEAI_API_KEY: str = os.environ.get("FREETHEAI_API_KEY", "")
ZUKI_API_KEY: str = os.environ.get("ZUKI_API_KEY", "")
FEATHERLESS_API_KEY: str = os.environ.get("FEATHERLESS_API_KEY", "")
GLHF_API_KEY: str = os.environ.get("GLHF_API_KEY", "")
AGENTROUTER_API_KEY: str = os.environ.get("AGENTROUTER_API_KEY", "")
FREEMODEL_API_KEY: str = os.environ.get("FREEMODEL_API_KEY", "")
FIREWORKS_API_KEY: str = os.environ.get("FIREWORKS_API_KEY", "")
COHERE_API_KEY: str = os.environ.get("COHERE_API_KEY", "")
SAMBANOVA_API_KEY: str = os.environ.get("SAMBANOVA_API_KEY", "")
DEEPINFRA_API_KEY: str = os.environ.get("DEEPINFRA_API_KEY", "")
TOGETHER_API_KEY: str = os.environ.get("TOGETHER_API_KEY", "")
AGNES_AI_API_KEY: str = os.environ.get("AGNES_AI_API_KEY", "")
OPENGATEWAY_API_KEY: str = os.environ.get("OPENGATEWAY_API_KEY", "")

# VPS proxy / specific keys
LONGCAT_API_KEY: str = os.environ.get("LONGCAT_API_KEY", "")
MIMO_TTS_KEY: str = os.environ.get("MIMO_TTS_KEY", "")
MIMO_V2_PRO_KEY: str = os.environ.get("MIMO_V2_PRO_KEY", "")
XMIAOM_API_KEY: str = os.environ.get("XMIAOM_API_KEY", "")

# Coding-pool specific keys
XFYUN_API_KEY: str = os.environ.get("XFYUN_API_KEY", "")
DASHSCOPE_CODING_KEY: str = os.environ.get("DASHSCOPE_CODING_KEY", "")
ZHIHU_API_KEY: str = os.environ.get("ZHIHU_API_KEY", "")

# Gitee AI (provider automation)
GITEE_AI_ENABLED: bool = os.environ.get("GITEE_AI_ENABLED", "0") == "1"
GITEE_AI_TOKEN: str = os.environ.get("GITEE_AI_TOKEN", "")
GITEE_AI_BASE_URL: str = os.environ.get("GITEE_AI_BASE_URL", "https://ai.gitee.com/v1")
