from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Mapping

FLAG_ENABLED = "SIE_AUTOPPT_AI_FIVE_STAGE_ENABLED"
FLAG_ROLLOUT_PERCENT = "SIE_AUTOPPT_AI_FIVE_STAGE_ROLLOUT_PERCENT"
FLAG_FORCE_LEGACY = "SIE_AUTOPPT_AI_FIVE_STAGE_FORCE_LEGACY"
FLAG_AUTO_ROLLBACK = "SIE_AUTOPPT_AI_FIVE_STAGE_AUTO_ROLLBACK"


@dataclass(frozen=True)
class AiFiveStageRolloutDecision:
    requested: bool
    enabled: bool
    reason: str
    rollout_percent: int
    bucket: int
    auto_rollback: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "requested": self.requested,
            "enabled": self.enabled,
            "reason": self.reason,
            "rollout_percent": self.rollout_percent,
            "bucket": self.bucket,
            "auto_rollback": self.auto_rollback,
        }


def _is_truthy(value: str | None) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _parse_rollout_percent(raw: str | None) -> int:
    try:
        parsed = int(str(raw or "100").strip())
    except ValueError:
        parsed = 100
    return max(0, min(100, parsed))


def _stable_bucket(run_id: str) -> int:
    digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def resolve_ai_five_stage_rollout(
    *,
    run_id: str,
    env: Mapping[str, str] | None = None,
) -> AiFiveStageRolloutDecision:
    source = env if env is not None else os.environ
    requested = _is_truthy(source.get(FLAG_ENABLED))
    force_legacy = _is_truthy(source.get(FLAG_FORCE_LEGACY))
    raw_auto_rollback = source.get(FLAG_AUTO_ROLLBACK)
    auto_rollback = True if raw_auto_rollback is None else _is_truthy(raw_auto_rollback)
    rollout_percent = _parse_rollout_percent(source.get(FLAG_ROLLOUT_PERCENT))
    bucket = _stable_bucket(run_id)

    if force_legacy:
        return AiFiveStageRolloutDecision(
            requested=requested,
            enabled=False,
            reason="force_legacy",
            rollout_percent=rollout_percent,
            bucket=bucket,
            auto_rollback=auto_rollback,
        )
    if not requested:
        return AiFiveStageRolloutDecision(
            requested=False,
            enabled=False,
            reason="flag_disabled",
            rollout_percent=rollout_percent,
            bucket=bucket,
            auto_rollback=auto_rollback,
        )
    if rollout_percent <= 0:
        return AiFiveStageRolloutDecision(
            requested=True,
            enabled=False,
            reason="rollout_zero",
            rollout_percent=rollout_percent,
            bucket=bucket,
            auto_rollback=auto_rollback,
        )
    if rollout_percent >= 100:
        return AiFiveStageRolloutDecision(
            requested=True,
            enabled=True,
            reason="rollout_full",
            rollout_percent=rollout_percent,
            bucket=bucket,
            auto_rollback=auto_rollback,
        )
    enabled = bucket < rollout_percent
    return AiFiveStageRolloutDecision(
        requested=True,
        enabled=enabled,
        reason="rollout_bucket_hit" if enabled else "rollout_bucket_excluded",
        rollout_percent=rollout_percent,
        bucket=bucket,
        auto_rollback=auto_rollback,
    )


__all__ = [
    "AiFiveStageRolloutDecision",
    "FLAG_AUTO_ROLLBACK",
    "FLAG_ENABLED",
    "FLAG_FORCE_LEGACY",
    "FLAG_ROLLOUT_PERCENT",
    "resolve_ai_five_stage_rollout",
]
