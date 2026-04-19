import json
from pathlib import Path

import pytest

from tools.sie_autoppt.batch.report_metrics import (
    aggregate_metrics,
    evaluate_thresholds,
    load_baseline_cases,
    load_run_metrics,
)


def _write_success_run(run_dir: Path, *, run_id: str, retries: int, tokens: int, latency_ms: int, degraded: bool) -> None:
    (run_dir / "final").mkdir(parents=True, exist_ok=True)
    (run_dir / "final" / "run_summary.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "final_state": "SUCCEEDED",
                "final_pptx": "final/final.pptx",
                "bundle_hash": "sha256:" + ("a" * 64),
                "export_hash": "sha256:" + ("b" * 64),
                "shape_map_mode": "mapped",
                "degraded_mode": degraded,
                "degraded_reasons": [],
                "retry_attempts_total": retries,
                "llm_total_tokens": tokens,
                "total_latency_ms": latency_ms,
                "ai_five_stage_mode": "ai_five_stage",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_failed_run(run_dir: Path, *, run_id: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "dead_letter.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "stage": "QA_CHECKING",
                "failure_code": "qa_failed",
                "retry_attempts": 1,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_load_run_metrics_and_aggregate(tmp_path: Path):
    runs_root = tmp_path / "runs"
    _write_success_run(runs_root / "run-001", run_id="run-001", retries=1, tokens=1200, latency_ms=1500, degraded=False)
    _write_success_run(runs_root / "run-002", run_id="run-002", retries=0, tokens=800, latency_ms=1100, degraded=True)
    _write_failed_run(runs_root / "run-003", run_id="run-003")

    records = load_run_metrics(runs_root)
    summary = aggregate_metrics(records)

    assert summary["total_runs"] == 3
    assert summary["success_runs"] == 2
    assert summary["success_rate"] == pytest.approx(2 / 3, rel=1e-6)
    assert summary["avg_retry_attempts"] == pytest.approx(0.5, rel=1e-6)
    assert summary["avg_total_tokens"] == pytest.approx(1000.0, rel=1e-6)
    assert summary["avg_total_latency_ms"] == pytest.approx(1300.0, rel=1e-6)
    assert summary["degraded_ratio"] == pytest.approx(0.5, rel=1e-6)


def test_load_run_metrics_respects_run_id_prefix_filter(tmp_path: Path):
    runs_root = tmp_path / "runs"
    _write_success_run(
        runs_root / "ai-five-stage-001",
        run_id="ai-five-stage-001",
        retries=1,
        tokens=1000,
        latency_ms=1400,
        degraded=False,
    )
    _write_success_run(
        runs_root / "legacy-001",
        run_id="legacy-001",
        retries=0,
        tokens=900,
        latency_ms=1200,
        degraded=False,
    )

    records = load_run_metrics(runs_root, run_id_prefix_filter="ai-five-stage-")

    assert len(records) == 1
    assert records[0]["run_id"] == "ai-five-stage-001"


def test_evaluate_thresholds_raises_when_quality_is_below_gate():
    summary = {
        "total_runs": 10,
        "success_rate": 0.6,
        "avg_retry_attempts": 3.2,
        "avg_total_tokens": 1600.0,
        "avg_total_latency_ms": 2500.0,
        "degraded_ratio": 0.7,
    }
    with pytest.raises(ValueError):
        evaluate_thresholds(
            summary,
            min_success_rate=0.8,
            max_avg_retries=2.0,
            max_degraded_ratio=0.5,
            max_avg_latency_ms=2000,
            require_samples=1,
        )


def test_load_baseline_cases_from_fixture_manifest(tmp_path: Path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    (fixtures_dir / "cases.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {"id": "case-001", "topic": "T1", "brief": "B1"},
                    {"id": "case-002", "topic": "T2", "brief": "B2"},
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    cases = load_baseline_cases(fixtures_dir)
    assert len(cases) == 2
    assert cases[0]["id"] == "case-001"
