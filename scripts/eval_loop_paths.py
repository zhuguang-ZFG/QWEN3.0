"""Path defaults for optional local-model eval tooling (offline / LM Studio)."""

from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DATA_EVAL = Path(os.environ.get("LIMA_DATA_DIR", _REPO_ROOT / "data")) / "eval"
_BUNDLED_DATASET = Path(__file__).resolve().parent / "eval_loop" / "default_eval_set.json"

EVAL_SET_PATH = os.environ.get("LIMA_EVAL_SET_PATH", str(_DATA_EVAL / "eval_set.json"))
RESULTS_DIR = os.environ.get("LIMA_EVAL_RESULTS_DIR", str(_DATA_EVAL / "results"))
DEFAULT_EVAL_SET_PATH = str(_BUNDLED_DATASET)

LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://localhost:1234/v1/chat/completions")
LM_STUDIO_MODEL = os.environ.get("LM_STUDIO_MODEL", "local-model")

DOMAIN_WEIGHT = 1 / 3
MAX_DOMAIN_DROP = 0.05
