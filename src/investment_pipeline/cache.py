"""A fetch-through disk cache for raw HTTP responses.

Cached files are stored under data/raw/<namespace>/<key>.json with
human-readable keys (not opaque hashes) so a reviewer can open them and see
exactly what a source returned. Committing this directory is what lets the
sourcing stage replay without the network.
"""

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import config


def _slug(key: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")
    return slug[:120] or "key"


def get_or_fetch(
    namespace: str,
    key: str,
    fetch: Callable[[], Any],
    *,
    refresh: bool = False,
) -> Any:
    """Return cached JSON for (namespace, key), else call `fetch` and store it.

    - refresh=True forces a live fetch (used to rebuild committed snapshots).
    - In offline mode a cache miss raises, rather than silently hitting the net.
    """
    path: Path = config.RAW_DIR / namespace / f"{_slug(key)}.json"

    if not refresh and path.exists():
        return json.loads(path.read_text())

    if config.offline():
        raise FileNotFoundError(
            f"offline mode: no cached response for {namespace}/{key} at {path}. "
            "Re-run without PIPELINE_OFFLINE to fetch it live."
        )

    data = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data
