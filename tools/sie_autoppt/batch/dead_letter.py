from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_dead_letter(*, run_dir: Path, payload: dict[str, Any]) -> Path:
    target = run_dir / "dead_letter.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
