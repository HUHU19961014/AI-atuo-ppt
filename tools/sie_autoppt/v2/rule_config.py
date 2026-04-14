from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_RULES_PATH = Path(__file__).with_name("default_rules.toml")
RULES_PATH_ENV = "SIE_AUTOPPT_V2_RULES_PATH"


@dataclass(frozen=True)
class RewriteRuleConfig:
    filler_patterns: tuple[str, ...]
    filler_safe_phrases: tuple[str, ...]


@dataclass(frozen=True)
class DirectoryStyleRuleConfig:
    exact_titles: frozenset[str]
    suffixes: tuple[str, ...]
    conclusion_markers: tuple[str, ...]


@dataclass(frozen=True)
class ScoringRuleConfig:
    base_score: int
    warning_weight: int
    high_weight: int
    error_weight: int
    baseline_slide_count: int
    excellent_threshold: int
    usable_threshold: int
    review_threshold: int


@dataclass(frozen=True)
class TitleLengthRuleConfig:
    error_threshold: int
    high_threshold: int
    warning_threshold: int


@dataclass(frozen=True)
class BulletRuleConfig:
    min_items: int
    max_items: int
    recommended_min_items: int
    recommended_max_items: int


@dataclass(frozen=True)
class V2RuleConfig:
    rewrite: RewriteRuleConfig
    directory_style: DirectoryStyleRuleConfig
    scoring: ScoringRuleConfig
    title_lengths: TitleLengthRuleConfig
    bullets: BulletRuleConfig


def _load_rule_payload(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"V2 rules config does not exist: {config_path}")
    with config_path.open("rb") as fh:
        payload = tomllib.load(fh)
    if not isinstance(payload, dict):
        raise ValueError("V2 rules config must be a TOML object.")
    return payload


def _list_payload(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    return tuple(str(value).strip() for value in values if str(value).strip())


@lru_cache(maxsize=1)
def load_v2_rule_config() -> V2RuleConfig:
    configured_path = os.environ.get(RULES_PATH_ENV, "").strip()
    config_path = Path(configured_path).expanduser() if configured_path else DEFAULT_RULES_PATH
    payload = _load_rule_payload(config_path)

    rewrite_payload = payload.get("rewrite", {})
    quality_payload = payload.get("quality", {})
    directory_payload = quality_payload.get("directory_style", {})
    scoring_payload = quality_payload.get("scoring", {})
    title_payload = quality_payload.get("titles", {})
    bullet_payload = quality_payload.get("bullets", {})

    return V2RuleConfig(
        rewrite=RewriteRuleConfig(
            filler_patterns=_list_payload(rewrite_payload.get("filler_patterns")),
            filler_safe_phrases=_list_payload(rewrite_payload.get("filler_safe_phrases")),
        ),
        directory_style=DirectoryStyleRuleConfig(
            exact_titles=frozenset(_list_payload(directory_payload.get("exact_titles"))),
            suffixes=_list_payload(directory_payload.get("suffixes")),
            conclusion_markers=_list_payload(directory_payload.get("conclusion_markers")),
        ),
        scoring=ScoringRuleConfig(
            base_score=int(scoring_payload.get("base_score", 100)),
            warning_weight=int(scoring_payload.get("warning_weight", 2)),
            high_weight=int(scoring_payload.get("high_weight", 6)),
            error_weight=int(scoring_payload.get("error_weight", 20)),
            baseline_slide_count=max(1, int(scoring_payload.get("baseline_slide_count", 6))),
            excellent_threshold=int(scoring_payload.get("excellent_threshold", 90)),
            usable_threshold=int(scoring_payload.get("usable_threshold", 75)),
            review_threshold=int(scoring_payload.get("review_threshold", 60)),
        ),
        title_lengths=TitleLengthRuleConfig(
            error_threshold=int(title_payload.get("error_threshold", 28)),
            high_threshold=int(title_payload.get("high_threshold", 24)),
            warning_threshold=int(title_payload.get("warning_threshold", 20)),
        ),
        bullets=BulletRuleConfig(
            min_items=max(1, int(bullet_payload.get("min_items", 1))),
            max_items=max(1, int(bullet_payload.get("max_items", 6))),
            recommended_min_items=max(1, int(bullet_payload.get("recommended_min_items", 2))),
            recommended_max_items=max(1, int(bullet_payload.get("recommended_max_items", 6))),
        ),
    )
