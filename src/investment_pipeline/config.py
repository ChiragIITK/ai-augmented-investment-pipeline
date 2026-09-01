"""Project paths and run configuration.

One place to resolve where things live on disk so every stage agrees, and a
single switch (`PIPELINE_OFFLINE`) that forces replay-only behaviour for a
reviewer running without network or keys.
"""

import os
from pathlib import Path

# Repo root = three parents up from this file (src/investment_pipeline/config.py).
ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"  # committed: makes sourcing replayable offline
ANALYSIS_DIR = DATA_DIR / "analysis"
LLM_CACHE_DIR = DATA_DIR / "llm_cache"  # committed: makes analysis replayable
CANDIDATES_PATH = DATA_DIR / "candidates.json"
MEMO_DIR = ROOT / "out" / "memos"


def offline() -> bool:
    """When true, never hit the network: serve from cache or fail loudly.

    This is the mode a reviewer uses to replay committed outputs without a key.
    """
    return os.getenv("PIPELINE_OFFLINE", "").lower() in {"1", "true", "yes"}
