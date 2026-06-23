"""Module-level singletons for centralized application settings.

Dataclass definitions live in config.settings_core so this file stays small and
import order remains predictable. Consumers import from here: e.g.
``from config import settings`` or ``from config.settings import DB``.
"""

from config.settings_core import (
    BackendOpsConfig,
    BrandConfig,
    DatabaseConfig,
    DeviceConfig,
    DigitalHumanConfig,
    EmbeddingConfig,
    EvalConfig,
    FeatureFlags,
    FleetConfig,
    GeminiConfig,
    IntegrationsConfig,
    MonitoringConfig,
    ObservabilityConfig,
    OtaConfig,
    OutcomeConfig,
    PathsConfig,
    RedisConfig,
    SecurityConfig,
    SessionMemoryConfig,
    UploadConfig,
    get_env,
    get_key_pool_raw,
    resolve_backend_key,
)
from config.voice_settings import VOICE, VOICEPRINT, VOICE_PROVIDERS

DB = DatabaseConfig()
REDIS = RedisConfig()
SECURITY = SecurityConfig()
PATHS = PathsConfig()
FLAGS = FeatureFlags()
EVAL = EvalConfig()
BACKEND_OPS = BackendOpsConfig()
BRAND = BrandConfig()
EMBEDDING = EmbeddingConfig()
DEVICE = DeviceConfig()
SESSION_MEMORY = SessionMemoryConfig()
DIGITAL_HUMAN = DigitalHumanConfig()
GEMINI = GeminiConfig()
OUTCOME = OutcomeConfig()
OTA = OtaConfig()
UPLOAD = UploadConfig()
OBSERVABILITY = ObservabilityConfig()
MONITORING = MonitoringConfig()
INTEGRATIONS = IntegrationsConfig()
FLEET = FleetConfig()

__all__ = [
    "BACKEND_OPS",
    "BRAND",
    "DB",
    "DEVICE",
    "DIGITAL_HUMAN",
    "EMBEDDING",
    "EVAL",
    "FLAGS",
    "FLEET",
    "GEMINI",
    "INTEGRATIONS",
    "MONITORING",
    "OBSERVABILITY",
    "OTA",
    "OUTCOME",
    "PATHS",
    "REDIS",
    "SECURITY",
    "SESSION_MEMORY",
    "UPLOAD",
    "VOICE",
    "VOICEPRINT",
    "VOICE_PROVIDERS",
    "BackendOpsConfig",
    "BrandConfig",
    "DatabaseConfig",
    "DeviceConfig",
    "DigitalHumanConfig",
    "EmbeddingConfig",
    "EvalConfig",
    "FeatureFlags",
    "FleetConfig",
    "GeminiConfig",
    "IntegrationsConfig",
    "MonitoringConfig",
    "ObservabilityConfig",
    "OtaConfig",
    "OutcomeConfig",
    "PathsConfig",
    "RedisConfig",
    "SecurityConfig",
    "SessionMemoryConfig",
    "UploadConfig",
    "get_env",
    "get_key_pool_raw",
    "resolve_backend_key",
]
