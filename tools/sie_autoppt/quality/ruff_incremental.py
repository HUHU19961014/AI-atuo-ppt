from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

_REPO_ROOT = Path.cwd().resolve()


@dataclass(frozen=True)
class RuffEntry:
    path: str
    code: str
    count: int

    def as_dict(self) -> dict[str, object]:
        return {"path": self.path, "code": self.code, "count": self.count}


def aggregate_diagnostics(diagnostics: Iterable[dict[str, Any]]) -> list[RuffEntry]:
    counts: Counter[tuple[str, str]] = Counter()
    for diagnostic in diagnostics:
        path = diagnostic.get("filename")
        code = diagnostic.get("code")
        if not isinstance(path, str) or not isinstance(code, str):
            continue
        normalized_path = _normalize_path(path)
        if not normalized_path or not code.strip():
            continue
        counts[(normalized_path, code.strip())] += 1
    return [RuffEntry(path=path, code=code, count=count) for (path, code), count in sorted(counts.items())]


def _normalize_path(path: str) -> str:
    path_obj = Path(path)
    try:
        resolved = path_obj.resolve()
    except OSError:
        return path_obj.as_posix()
    try:
        return resolved.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def compare_entries(current: list[RuffEntry], baseline: list[RuffEntry]) -> list[str]:
    baseline_map = {(entry.path, entry.code): entry.count for entry in baseline}
    regressions: list[str] = []
    for entry in current:
        baseline_count = baseline_map.get((entry.path, entry.code), 0)
        if entry.count > baseline_count:
            regressions.append(
                f"{entry.path} [{entry.code}] increased from {baseline_count} to {entry.count}"
            )
    return regressions


def _summary(entries: list[RuffEntry]) -> dict[str, object]:
    by_code: Counter[str] = Counter()
    for entry in entries:
        by_code[entry.code] += entry.count
    return {
        "issue_count": sum(entry.count for entry in entries),
        "entry_count": len(entries),
        "by_code": dict(sorted(by_code.items())),
    }


def _run_ruff(paths: list[str]) -> list[dict[str, Any]]:
    command = [sys.executable, "-m", "ruff", "check", *paths, "--output-format", "json", "--exit-zero"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "ruff execution failed"
        raise RuntimeError(message)
    payload = json.loads(completed.stdout or "[]")
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected ruff JSON output: expected array payload.")
    return [item for item in payload if isinstance(item, dict)]


def _load_entries(path: Path) -> list[RuffEntry]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries_raw: object
    if isinstance(payload, dict):
        entries_raw = payload.get("entries")
    else:
        entries_raw = payload
    if not isinstance(entries_raw, list):
        raise ValueError(f"Invalid baseline format: missing list 'entries' in {path}")

    entries: list[RuffEntry] = []
    for item in entries_raw:
        if not isinstance(item, dict):
            continue
        path_value = item.get("path")
        code_value = item.get("code")
        count_value = item.get("count")
        if not isinstance(path_value, str) or not isinstance(code_value, str):
            continue
        if not isinstance(count_value, int):
            continue
        entries.append(RuffEntry(path=path_value, code=code_value, count=count_value))
    return entries


def _write_payload(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _serialize(entries: list[RuffEntry]) -> list[dict[str, object]]:
    return [entry.as_dict() for entry in entries]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ruff incremental gate: allow existing baseline, block newly introduced violations."
    )
    parser.add_argument("--paths", nargs="+", required=True, help="Paths passed to `ruff check`.")
    parser.add_argument("--baseline", type=Path, required=True, help="Baseline JSON file path.")
    parser.add_argument("--report-out", type=Path, default=None, help="Optional comparison report output path.")
    parser.add_argument("--write-baseline", action="store_true", help="Write current results as baseline and exit.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    diagnostics = _run_ruff(args.paths)
    current_entries = aggregate_diagnostics(diagnostics)
    current_payload: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "paths": list(args.paths),
        "summary": _summary(current_entries),
        "entries": _serialize(current_entries),
    }
    if args.write_baseline:
        _write_payload(args.baseline, current_payload)
        print(args.baseline.as_posix())
        return 0

    if not args.baseline.exists():
        raise SystemExit(f"ruff baseline not found: {args.baseline}")

    baseline_entries = _load_entries(args.baseline)
    regressions = compare_entries(current_entries, baseline_entries)
    report_payload: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_path": args.baseline.as_posix(),
        "paths": list(args.paths),
        "baseline_summary": _summary(baseline_entries),
        "current_summary": _summary(current_entries),
        "regressions": regressions,
    }
    if args.report_out is not None:
        _write_payload(args.report_out, report_payload)
        print(args.report_out.as_posix())

    if regressions:
        raise SystemExit("ruff incremental gate failed:\n- " + "\n- ".join(regressions))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
