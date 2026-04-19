from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BatchWorkspace:
    run_dir: Path
    input_dir: Path
    input_source_dir: Path
    preprocess_dir: Path
    bridge_dir: Path
    tune_dir: Path
    qa_dir: Path
    final_dir: Path
    logs_dir: Path
    svg_request_path: Path

    @classmethod
    def create(cls, *, root: Path, run_id: str) -> "BatchWorkspace":
        run_dir = root / "runs" / run_id
        if run_dir.exists():
            raise FileExistsError(f"run workspace already exists: {run_dir}")
        input_dir = run_dir / "input"
        input_source_dir = input_dir / "source"
        preprocess_dir = run_dir / "preprocess"
        bridge_dir = run_dir / "bridge"
        tune_dir = run_dir / "tune"
        qa_dir = run_dir / "qa"
        final_dir = run_dir / "final"
        logs_dir = run_dir / "logs"
        svg_request_path = bridge_dir / "svg_request.json"

        for path in (
            run_dir,
            input_dir,
            input_source_dir,
            preprocess_dir,
            bridge_dir,
            tune_dir,
            qa_dir,
            final_dir,
            logs_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

        return cls(
            run_dir=run_dir,
            input_dir=input_dir,
            input_source_dir=input_source_dir,
            preprocess_dir=preprocess_dir,
            bridge_dir=bridge_dir,
            tune_dir=tune_dir,
            qa_dir=qa_dir,
            final_dir=final_dir,
            logs_dir=logs_dir,
            svg_request_path=svg_request_path,
        )
