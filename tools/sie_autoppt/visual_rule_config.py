from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_VISUAL_RULES_PATH = Path(__file__).with_name("visual_default_rules.toml")
VISUAL_RULES_PATH_ENV = "SIE_AUTOPPT_VISUAL_RULES_PATH"


@dataclass(frozen=True)
class VisualScoringThresholds:
    pass_threshold: int
    pass_with_notes_threshold: int
    auto_revise_threshold: int


@dataclass(frozen=True)
class VisualLimits:
    max_cards: int
    max_detail_chars: int
    min_font_px: int
    max_colors: int


@dataclass(frozen=True)
class VisualPenalties:
    missing_headline: int
    missing_claim: int
    too_many_cards: int
    detail_too_long: int
    unsupported_component: int
    missing_slide_root: int
    missing_overflow_hidden: int
    external_assets: int
    unknown_layout: int
    missing_screenshot: int
    too_small_font: int
    too_many_colors: int
    safe_area_violation: int
    safe_area_uncheckable: int


@dataclass(frozen=True)
class VisualRuleConfig:
    scoring: VisualScoringThresholds
    limits: VisualLimits
    penalties: VisualPenalties


def _load_rule_payload(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"visual rules config does not exist: {config_path}")
    with config_path.open("rb") as fh:
        payload = tomllib.load(fh)
    if not isinstance(payload, dict):
        raise ValueError("visual rules config must be a TOML object.")
    return payload


def _load_visual_rule_config(config_path: Path) -> VisualRuleConfig:
    payload = _load_rule_payload(config_path)
    scoring = payload.get("scoring", {})
    limits = payload.get("limits", {})
    penalties = payload.get("penalties", {})
    return VisualRuleConfig(
        scoring=VisualScoringThresholds(
            pass_threshold=int(scoring.get("pass_threshold", 85)),
            pass_with_notes_threshold=int(scoring.get("pass_with_notes_threshold", 75)),
            auto_revise_threshold=int(scoring.get("auto_revise_threshold", 75)),
        ),
        limits=VisualLimits(
            max_cards=max(1, int(limits.get("max_cards", 8))),
            max_detail_chars=max(1, int(limits.get("max_detail_chars", 90))),
            min_font_px=max(1, int(limits.get("min_font_px", 12))),
            max_colors=max(1, int(limits.get("max_colors", 8))),
        ),
        penalties=VisualPenalties(
            missing_headline=int(penalties.get("missing_headline", 20)),
            missing_claim=int(penalties.get("missing_claim", 15)),
            too_many_cards=int(penalties.get("too_many_cards", 20)),
            detail_too_long=int(penalties.get("detail_too_long", 8)),
            unsupported_component=int(penalties.get("unsupported_component", 20)),
            missing_slide_root=int(penalties.get("missing_slide_root", 25)),
            missing_overflow_hidden=int(penalties.get("missing_overflow_hidden", 12)),
            external_assets=int(penalties.get("external_assets", 20)),
            unknown_layout=int(penalties.get("unknown_layout", 20)),
            missing_screenshot=int(penalties.get("missing_screenshot", 8)),
            too_small_font=int(penalties.get("too_small_font", 10)),
            too_many_colors=int(penalties.get("too_many_colors", 8)),
            safe_area_violation=int(penalties.get("safe_area_violation", 12)),
            safe_area_uncheckable=int(penalties.get("safe_area_uncheckable", 6)),
        ),
    )


@lru_cache(maxsize=1)
def load_visual_rule_config() -> VisualRuleConfig:
    configured_path = os.environ.get(VISUAL_RULES_PATH_ENV, "").strip()
    config_path = Path(configured_path).expanduser() if configured_path else DEFAULT_VISUAL_RULES_PATH
    return _load_visual_rule_config(config_path)


def load_visual_rule_config_from_path(config_path: str | Path | None) -> VisualRuleConfig:
    if not config_path:
        return load_visual_rule_config()
    return _load_visual_rule_config(Path(config_path).expanduser())
