from __future__ import annotations

from pathlib import Path
from typing import Any

from .schema import DeckDocument
from .visual_review import SingleReviewArtifacts, apply_patch_set, generate_blocker_patches, review_deck_once


def review_once(
    *,
    deck_path: Path,
    output_dir: Path,
    model: str | None = None,
    theme_name: str | None = None,
) -> SingleReviewArtifacts:
    return review_deck_once(
        deck_path=deck_path,
        output_dir=output_dir,
        model=model,
        theme_name=theme_name,
    )


def generate_patch(
    deck: DeckDocument,
    review_result: dict[str, Any],
    *,
    model: str | None = None,
    provider: Any = None,
) -> dict[str, Any]:
    return generate_blocker_patches(deck, review_result, model=model, provider=provider)


def apply_patch(deck: DeckDocument, patch_set: dict[str, Any]) -> DeckDocument:
    return apply_patch_set(deck, patch_set)


__all__ = ["review_once", "generate_patch", "apply_patch", "SingleReviewArtifacts"]
