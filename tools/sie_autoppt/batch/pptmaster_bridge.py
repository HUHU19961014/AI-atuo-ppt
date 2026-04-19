from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..v2 import compile_semantic_deck_payload
from ..v2.services import _write_svg_project
from .contracts import ContentBundle, SvgRequest
from .export import build_shape_map_from_pptx, build_svg_manifest
from .hashing import sha256_file
from .logging import write_json
from .workspace import BatchWorkspace

REQUIRED_PPTMASTER_SCRIPTS = (
    "skills/ppt-master/scripts/total_md_split.py",
    "skills/ppt-master/scripts/finalize_svg.py",
    "skills/ppt-master/scripts/svg_to_pptx.py",
)


@dataclass(frozen=True)
class BridgeConfig:
    pptmaster_root: str = ""


def resolve_bridge_root(*, config: BridgeConfig) -> Path:
    raw_root = config.pptmaster_root or os.environ.get("SIE_PPTMASTER_ROOT", "")
    if not raw_root:
        raise FileNotFoundError("SIE_PPTMASTER_ROOT is not configured.")
    root = Path(raw_root).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"SIE_PPTMASTER_ROOT does not exist: {root}")
    for script in REQUIRED_PPTMASTER_SCRIPTS:
        candidate = root / script
        if not candidate.exists():
            raise FileNotFoundError(f"Missing required pptmaster script: {candidate}")
    return root


def run_pptmaster_bridge(*, workspace: BatchWorkspace, bundle: dict[str, Any], bridge_root: Path) -> dict[str, Any]:
    root = resolve_bridge_root(config=BridgeConfig(pptmaster_root=str(bridge_root)))
    bundle_model = ContentBundle.model_validate(bundle)
    semantic_payload = dict(bundle_model.semantic_payload or {})
    meta = semantic_payload.get("meta") or {}
    validated_deck = compile_semantic_deck_payload(
        semantic_payload,
        default_title=str(bundle_model.topic or meta.get("title") or "Untitled"),
        default_theme=str(bundle_model.theme or meta.get("theme") or "sie_consulting_fixed"),
        default_language=str(bundle_model.language or meta.get("language") or "zh-CN"),
        default_author=str(meta.get("author") or "AI Auto PPT"),
    )
    deck = validated_deck.deck
    page_refs = [slide.slide_id for slide in deck.slides] or ["s-001"]

    project_path = workspace.bridge_dir / "svg_project"
    _write_svg_project(deck, project_path=project_path)
    svg_request = SvgRequest(
        run_id=bundle_model.run_id,
        bundle_hash=bundle_model.bundle_hash,
        content_bundle_path=Path("preprocess/content_bundle.json").as_posix(),
        page_refs=page_refs,
    )
    write_json(workspace.svg_request_path, svg_request.model_dump(mode="json"))

    split_script = root / REQUIRED_PPTMASTER_SCRIPTS[0]
    finalize_script = root / REQUIRED_PPTMASTER_SCRIPTS[1]
    export_script = root / REQUIRED_PPTMASTER_SCRIPTS[2]
    pptx_path = workspace.bridge_dir / "exported_raw.pptx"
    _run_bridge_command([sys.executable, str(split_script), str(project_path)], step_name="svg split notes")
    _run_bridge_command([sys.executable, str(finalize_script), str(project_path)], step_name="svg finalize")
    _run_bridge_command(
        [sys.executable, str(export_script), str(project_path), "-s", "final", "-o", str(pptx_path)],
        step_name="svg export",
    )

    svg_dir = project_path / "svg_final"
    if not svg_dir.exists():
        svg_dir = project_path / "svg_output"
    svg_manifest = build_svg_manifest(
        run_id=bundle_model.run_id,
        bundle_hash=bundle_model.bundle_hash,
        run_dir=workspace.run_dir,
        project_root=project_path,
        svg_dir=svg_dir,
        page_refs=page_refs,
    )

    return {
        "svg_bundle_hash": svg_manifest.svg_bundle_hash,
        "svg_manifest": svg_manifest.model_dump(mode="json"),
        "export_hash": sha256_file(pptx_path),
        "exporter_version": "pptmaster-bridge-v1",
        "pptx_path": pptx_path.relative_to(workspace.run_dir).as_posix(),
        "shape_map": build_shape_map_from_pptx(pptx_path=pptx_path, page_refs=page_refs),
        "shape_map_mode": "heuristic",
    }


def _run_bridge_command(command: list[str], *, step_name: str) -> None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{step_name} timed out after 120s") from exc
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"{step_name} failed: {details or 'unknown error'}")
