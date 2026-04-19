import os

from tools.sie_autoppt.batch.rollout import resolve_ai_five_stage_rollout


def test_rollout_defaults_to_legacy_when_flag_is_unset():
    env = {}
    decision = resolve_ai_five_stage_rollout(run_id="run-001", env=env)
    assert decision.enabled is False
    assert decision.requested is False
    assert decision.reason == "flag_disabled"


def test_rollout_respects_rollout_percent_and_bucket():
    env = {
        "SIE_AUTOPPT_AI_FIVE_STAGE_ENABLED": "1",
        "SIE_AUTOPPT_AI_FIVE_STAGE_ROLLOUT_PERCENT": "100",
    }
    decision = resolve_ai_five_stage_rollout(run_id="run-002", env=env)
    assert decision.enabled is True
    assert decision.requested is True
    assert decision.rollout_percent == 100
    assert 0 <= decision.bucket <= 99
    assert decision.reason == "rollout_full"


def test_rollout_force_legacy_overrides_enabled_flag():
    env = {
        "SIE_AUTOPPT_AI_FIVE_STAGE_ENABLED": "1",
        "SIE_AUTOPPT_AI_FIVE_STAGE_ROLLOUT_PERCENT": "100",
        "SIE_AUTOPPT_AI_FIVE_STAGE_FORCE_LEGACY": "1",
    }
    decision = resolve_ai_five_stage_rollout(run_id="run-003", env=env)
    assert decision.enabled is False
    assert decision.reason == "force_legacy"


def test_rollout_excludes_run_when_percent_is_zero():
    env = {
        "SIE_AUTOPPT_AI_FIVE_STAGE_ENABLED": "1",
        "SIE_AUTOPPT_AI_FIVE_STAGE_ROLLOUT_PERCENT": "0",
    }
    decision = resolve_ai_five_stage_rollout(run_id="run-004", env=env)
    assert decision.enabled is False
    assert decision.reason == "rollout_zero"


def test_rollout_auto_rollback_defaults_to_true():
    env = {
        "SIE_AUTOPPT_AI_FIVE_STAGE_ENABLED": "1",
    }
    decision = resolve_ai_five_stage_rollout(run_id="run-005", env=env)
    assert decision.auto_rollback is True
    env["SIE_AUTOPPT_AI_FIVE_STAGE_AUTO_ROLLBACK"] = "0"
    decision_disabled = resolve_ai_five_stage_rollout(run_id="run-005", env=env)
    assert decision_disabled.auto_rollback is False
