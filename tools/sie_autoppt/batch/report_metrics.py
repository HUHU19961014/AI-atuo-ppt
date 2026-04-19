from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_baseline_cases(fixtures_dir: Path) -> list[dict[str, Any]]:
    manifest_path = fixtures_dir / "cases.json"
    if not manifest_path.exists():
        return []
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        return []
    return [case for case in cases if isinstance(case, dict)]


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_run_metrics(runs_root: Path, *, run_id_prefix_filter: str = "") -> list[dict[str, Any]]:
    if not runs_root.exists():
        return []
    records: list[dict[str, Any]] = []
    for run_dir in sorted(candidate for candidate in runs_root.iterdir() if candidate.is_dir()):
        summary_path = run_dir / "final" / "run_summary.json"
        dead_letter_path = run_dir / "dead_letter.json"
        if summary_path.exists():
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            run_id = str(payload.get("run_id") or run_dir.name)
            if run_id_prefix_filter and not run_id.startswith(run_id_prefix_filter):
                continue
            records.append(
                {
                    "run_id": run_id,
                    "success": str(payload.get("final_state") or "").upper() == "SUCCEEDED",
                    "retry_attempts": _to_int(payload.get("retry_attempts_total"), 0),
                    "llm_total_tokens": _to_int(payload.get("llm_total_tokens"), 0),
                    "total_latency_ms": _to_int(payload.get("total_latency_ms"), 0),
                    "degraded_mode": _to_bool(payload.get("degraded_mode")),
                    "ai_five_stage_mode": str(payload.get("ai_five_stage_mode") or "legacy"),
                }
            )
            continue
        if dead_letter_path.exists():
            payload = json.loads(dead_letter_path.read_text(encoding="utf-8"))
            run_id = str(payload.get("run_id") or run_dir.name)
            if run_id_prefix_filter and not run_id.startswith(run_id_prefix_filter):
                continue
            records.append(
                {
                    "run_id": run_id,
                    "success": False,
                    "retry_attempts": _to_int(payload.get("retry_attempts"), 0),
                    "llm_total_tokens": 0,
                    "total_latency_ms": 0,
                    "degraded_mode": False,
                    "ai_five_stage_mode": "unknown",
                }
            )
    return records


def aggregate_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    total_runs = len(records)
    success_records = [record for record in records if record.get("success")]
    success_runs = len(success_records)
    retries = [max(0, _to_int(record.get("retry_attempts"), 0)) for record in success_records]
    tokens = [max(0, _to_int(record.get("llm_total_tokens"), 0)) for record in success_records]
    latencies = [max(0, _to_int(record.get("total_latency_ms"), 0)) for record in success_records]
    degraded = [record for record in success_records if _to_bool(record.get("degraded_mode"))]

    mode_counts: dict[str, int] = {}
    for record in records:
        key = str(record.get("ai_five_stage_mode") or "unknown")
        mode_counts[key] = mode_counts.get(key, 0) + 1

    return {
        "total_runs": total_runs,
        "success_runs": success_runs,
        "success_rate": (success_runs / total_runs) if total_runs else 0.0,
        "avg_retry_attempts": statistics.fmean(retries) if retries else 0.0,
        "avg_total_tokens": statistics.fmean(tokens) if tokens else 0.0,
        "avg_total_latency_ms": statistics.fmean(latencies) if latencies else 0.0,
        "degraded_ratio": (len(degraded) / success_runs) if success_runs else 0.0,
        "ai_five_stage_mode_counts": mode_counts,
    }


def evaluate_thresholds(
    summary: dict[str, Any],
    *,
    min_success_rate: float,
    max_avg_retries: float,
    max_degraded_ratio: float,
    max_avg_latency_ms: int,
    require_samples: int,
) -> None:
    total_runs = _to_int(summary.get("total_runs"), 0)
    if total_runs < max(0, require_samples):
        raise ValueError(f"run sample count is below required minimum: {total_runs} < {require_samples}")
    if total_runs == 0:
        return

    violations: list[str] = []
    success_rate = float(summary.get("success_rate") or 0.0)
    avg_retries = float(summary.get("avg_retry_attempts") or 0.0)
    degraded_ratio = float(summary.get("degraded_ratio") or 0.0)
    avg_latency_ms = float(summary.get("avg_total_latency_ms") or 0.0)

    if success_rate < min_success_rate:
        violations.append(f"success_rate {success_rate:.4f} < {min_success_rate:.4f}")
    if max_avg_retries >= 0 and avg_retries > max_avg_retries:
        violations.append(f"avg_retry_attempts {avg_retries:.4f} > {max_avg_retries:.4f}")
    if max_degraded_ratio >= 0 and degraded_ratio > max_degraded_ratio:
        violations.append(f"degraded_ratio {degraded_ratio:.4f} > {max_degraded_ratio:.4f}")
    if max_avg_latency_ms > 0 and avg_latency_ms > max_avg_latency_ms:
        violations.append(f"avg_total_latency_ms {avg_latency_ms:.2f} > {max_avg_latency_ms}")
    if violations:
        raise ValueError("; ".join(violations))


def _slug(text: str) -> str:
    normalized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in text.strip().lower())
    trimmed = normalized.strip("-")
    return trimmed or "case"


def build_replay_plan(
    *,
    cases: list[dict[str, Any]],
    output_root: Path,
    pptmaster_root: Path | None,
    main_py: Path,
    run_id_prefix: str = "ai-five-stage",
) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        case_id = _slug(str(case.get("id") or f"case-{index:03d}"))
        run_id = f"{run_id_prefix}-{index:03d}-{case_id}"
        command = [
            sys.executable,
            str(main_py),
            "batch-make",
            "--topic",
            str(case.get("topic") or ""),
            "--brief",
            str(case.get("brief") or ""),
            "--audience",
            str(case.get("audience") or "Executive team"),
            "--language",
            str(case.get("language") or "zh-CN"),
            "--theme",
            str(case.get("theme") or "sie_consulting_fixed"),
            "--output-dir",
            str(output_root),
            "--run-id",
            run_id,
        ]
        if pptmaster_root is not None:
            command.extend(["--pptmaster-root", str(pptmaster_root)])
        for link in case.get("links") or []:
            command.extend(["--link", str(link)])
        for image_file in case.get("image_files") or []:
            command.extend(["--image-file", str(image_file)])
        for attachment_file in case.get("attachment_files") or []:
            command.extend(["--attachment-file", str(attachment_file)])
        structured_data = case.get("structured_data_json")
        if structured_data:
            command.extend(["--structured-data-json", str(structured_data)])
        plan.append({"id": case_id, "run_id": run_id, "command": command})
    return plan


def _execute_replay_plan(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in plan:
        command = list(item["command"])
        started_at = datetime.now(timezone.utc)
        completed = subprocess.run(command, capture_output=True, text=True)
        finished_at = datetime.now(timezone.utc)
        results.append(
            {
                "id": item["id"],
                "run_id": item["run_id"],
                "returncode": completed.returncode,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "stderr_tail": "\n".join(completed.stderr.splitlines()[-5:]),
            }
        )
    return results


def _comparison_payload(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, dict[str, float]]:
    metrics = ("success_rate", "avg_retry_attempts", "avg_total_tokens", "avg_total_latency_ms", "degraded_ratio")
    comparison: dict[str, dict[str, float]] = {}
    for key in metrics:
        current_value = float(current.get(key) or 0.0)
        baseline_value = float(baseline.get(key) or 0.0)
        comparison[key] = {
            "current": current_value,
            "baseline": baseline_value,
            "delta": current_value - baseline_value,
        }
    return comparison


def render_markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# AI Five-Stage Metrics",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- runs_root: `{report['runs_root']}`",
        f"- total_runs: `{summary['total_runs']}`",
        f"- success_rate: `{summary['success_rate']:.4f}`",
        f"- avg_retry_attempts: `{summary['avg_retry_attempts']:.4f}`",
        f"- avg_total_tokens: `{summary['avg_total_tokens']:.2f}`",
        f"- avg_total_latency_ms: `{summary['avg_total_latency_ms']:.2f}`",
        f"- degraded_ratio: `{summary['degraded_ratio']:.4f}`",
    ]
    comparison = report.get("comparison")
    if isinstance(comparison, dict) and comparison:
        lines.extend(
            [
                "",
                "## Baseline Comparison",
                "",
                "| Metric | Baseline | Current | Delta |",
                "|---|---:|---:|---:|",
            ]
        )
        for key, payload in comparison.items():
            lines.append(
                f"| `{key}` | {payload['baseline']:.4f} | {payload['current']:.4f} | {payload['delta']:+.4f} |"
            )
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate and gate AI five-stage batch metrics.")
    parser.add_argument("--runs-root", type=Path, default=Path("output") / "runs")
    parser.add_argument("--run-id-prefix-filter", default="")
    parser.add_argument("--report-out", type=Path, default=Path("output") / "reports" / "ai_five_stage_metrics.json")
    parser.add_argument("--markdown-out", type=Path, default=Path("output") / "reports" / "ai_five_stage_metrics.md")
    parser.add_argument("--fixtures-dir", type=Path, default=None)
    parser.add_argument("--replay-plan-out", type=Path, default=None)
    parser.add_argument("--execute-replay", action="store_true")
    parser.add_argument("--main-py", type=Path, default=Path("main.py"))
    parser.add_argument("--output-root", type=Path, default=Path("output"))
    parser.add_argument("--pptmaster-root", type=Path, default=None)
    parser.add_argument("--run-id-prefix", default="ai-five-stage")
    parser.add_argument("--baseline-report", type=Path, default=None)
    parser.add_argument("--min-fixtures", type=int, default=0)
    parser.add_argument("--require-samples", type=int, default=0)
    parser.add_argument("--min-success-rate", type=float, default=0.0)
    parser.add_argument("--max-avg-retries", type=float, default=-1.0)
    parser.add_argument("--max-degraded-ratio", type=float, default=-1.0)
    parser.add_argument("--max-avg-latency-ms", type=int, default=0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    baseline_cases = load_baseline_cases(args.fixtures_dir) if args.fixtures_dir is not None else []
    if args.min_fixtures > 0 and len(baseline_cases) < args.min_fixtures:
        raise SystemExit(
            f"baseline fixtures below minimum: {len(baseline_cases)} < {args.min_fixtures} in {args.fixtures_dir}"
        )

    replay_plan: list[dict[str, Any]] = []
    replay_results: list[dict[str, Any]] = []
    if baseline_cases:
        replay_plan = build_replay_plan(
            cases=baseline_cases,
            output_root=args.output_root,
            pptmaster_root=args.pptmaster_root,
            main_py=args.main_py,
            run_id_prefix=args.run_id_prefix,
        )
    if args.replay_plan_out is not None:
        args.replay_plan_out.parent.mkdir(parents=True, exist_ok=True)
        args.replay_plan_out.write_text(json.dumps(replay_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.execute_replay and replay_plan:
        replay_results = _execute_replay_plan(replay_plan)

    records = load_run_metrics(args.runs_root, run_id_prefix_filter=args.run_id_prefix_filter.strip())
    summary = aggregate_metrics(records)
    evaluate_thresholds(
        summary,
        min_success_rate=max(0.0, args.min_success_rate),
        max_avg_retries=args.max_avg_retries,
        max_degraded_ratio=args.max_degraded_ratio,
        max_avg_latency_ms=max(0, args.max_avg_latency_ms),
        require_samples=max(0, args.require_samples),
    )

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runs_root": args.runs_root.as_posix(),
        "summary": summary,
        "run_count": len(records),
        "baseline_fixture_count": len(baseline_cases),
        "replay_results": replay_results,
    }
    if args.baseline_report is not None and args.baseline_report.exists():
        baseline_payload = json.loads(args.baseline_report.read_text(encoding="utf-8"))
        baseline_summary = baseline_payload.get("summary") if isinstance(baseline_payload, dict) else None
        if isinstance(baseline_summary, dict):
            report["comparison"] = _comparison_payload(summary, baseline_summary)

    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_out is not None:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(render_markdown_report(report), encoding="utf-8")
    print(args.report_out.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
