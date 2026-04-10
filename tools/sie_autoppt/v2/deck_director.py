from __future__ import annotations

"""
Backward-compatible facade for semantic deck compilation.

The implementation is split across dedicated modules:
- semantic_schema_builder.py: JSON schema and supported semantic enums
- semantic_router.py: feature extraction and layout routing
- semantic_compiler.py: payload normalization and deck compilation
"""

from .semantic_compiler import compile_semantic_deck_payload
from .semantic_router import SemanticLayoutPlan, SemanticSlideFeatures, plan_semantic_slide_layout
from .semantic_schema_builder import SUPPORTED_BLOCK_KINDS, SUPPORTED_SLIDE_INTENTS, build_semantic_deck_schema

__all__ = [
    "SUPPORTED_BLOCK_KINDS",
    "SUPPORTED_SLIDE_INTENTS",
    "SemanticLayoutPlan",
    "SemanticSlideFeatures",
    "build_semantic_deck_schema",
    "compile_semantic_deck_payload",
    "plan_semantic_slide_layout",
]
