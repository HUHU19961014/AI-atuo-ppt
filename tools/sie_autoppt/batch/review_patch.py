from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..v2 import compile_semantic_deck_payload
from ..v2.io import load_deck_document, write_deck_document
from ..v2.review_patch import apply_patch, review_once
from .workspace import BatchWorkspace


def run_batch_review_patch_once(
    *,
    workspace: BatchWorkspace,
    bundle: dict[str, Any],
    model: str | None = None,
    theme_name: str | None = None,
    output_dir: Path | None = None,
) -> dict[str, str]:
    review_dir = output_dir or (workspace.qa_dir / "review_patch")
    review_dir.mkdir(parents=True, exist_ok=True)

    deck = _compile_bundle_deck(bundle)
    review_input_path = write_deck_document(deck, review_dir / "review_input.deck.json")
    artifacts = review_once(
        deck_path=review_input_path,
        output_dir=review_dir,
        model=model,
        theme_name=theme_name or str(bundle.get("theme") or "").strip() or None,
    )

    reviewed_deck = load_deck_document(artifacts.deck_path)
    patch_payload = json.loads(artifacts.patch_path.read_text(encoding="utf-8-sig"))
    if not isinstance(patch_payload, dict):
        raise RuntimeError("review patch payload must be a JSON object with top-level 'patches'.")

    if patch_payload.get("patches"):
        try:
            patched_deck = apply_patch(reviewed_deck, patch_payload)
        except ValueError as exc:
            raise RuntimeError(f"review patch apply failed: {exc}") from exc
    else:
        patched_deck = reviewed_deck

    patched_deck_path = write_deck_document(patched_deck, review_dir / "patched.deck.json")
    return {
        "review_path": _to_run_relative(workspace.run_dir, artifacts.review_path),
        "patch_path": _to_run_relative(workspace.run_dir, artifacts.patch_path),
        "patched_deck_path": _to_run_relative(workspace.run_dir, patched_deck_path),
    }


def _compile_bundle_deck(bundle: dict[str, Any]):
    semantic_payload = dict(bundle.get("semantic_payload") or {})
    meta = semantic_payload.get("meta") or {}
    return compile_semantic_deck_payload(
        semantic_payload,
        default_title=str(bundle.get("topic") or meta.get("title") or "Untitled"),
        default_theme=str(bundle.get("theme") or meta.get("theme") or "sie_consulting_fixed"),
        default_language=str(bundle.get("language") or meta.get("language") or "zh-CN"),
        default_author=str(meta.get("author") or "AI Auto PPT"),
    ).deck


def _to_run_relative(run_dir: Path, path: Path) -> str:
    try:
        return path.relative_to(run_dir).as_posix()
    except ValueError:
        return path.as_posix()
