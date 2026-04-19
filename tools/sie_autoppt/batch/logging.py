from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .state import BatchState
from .workspace import BatchWorkspace


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def mark_state(workspace: BatchWorkspace, state: BatchState, detail: str, *, attempt: int = 1) -> None:
    append_jsonl(
        workspace.logs_dir / "spans.jsonl",
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": state.value,
            "detail": detail,
            "attempt": attempt,
        },
    )


def log_error(
    workspace: BatchWorkspace,
    *,
    stage: BatchState,
    error_code: str,
    message: str,
    attempt: int = 1,
) -> None:
    append_jsonl(
        workspace.logs_dir / "errors.jsonl",
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage.value,
            "error_code": error_code,
            "message": message,
            "attempt": attempt,
        },
    )


def log_usage(workspace: BatchWorkspace, *, stage: BatchState, payload: dict[str, Any] | None = None) -> None:
    append_jsonl(
        workspace.logs_dir / "usage.jsonl",
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage.value,
            "payload": payload or {},
        },
    )
