# Internal Batch PPTMaster P0/P1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the internal batch PPT pipeline v1 so `Enterprise-AI-PPT` runs through an isolated run workspace, structured artifacts, a configurable `pptmaster` bridge, deterministic post-export tuning, and routeable QA.

**Architecture:** Keep existing V2 semantic generation logic as reusable building blocks, but move runtime ownership into a new `tools/sie_autoppt/batch/` package. The new control plane owns `run_id`, stage transitions, retry budgets, timeouts, artifact hashes, and external bridge configuration; V2 becomes a semantic service layer instead of the only orchestration surface.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, existing `tools/sie_autoppt/v2/*` modules, repo-local CLI, external `pptmaster` scripts configured through `SIE_PPTMASTER_ROOT`.

---

## Plan Boundaries

- `P0` covers: batch control plane primitives, input safety, `pptmaster` bridge configuration, batch orchestrator, run-isolated outputs, and export manifest integrity.
- `P1` covers: deterministic tuning and QA routing, documentation drift fixes, repo hygiene, and legacy boundary tightening.
- This plan does not implement distributed workers, online service APIs, or mandatory human approval gates.

## Proposed File Map

### Create

- `tools/sie_autoppt/batch/__init__.py`
- `tools/sie_autoppt/batch/contracts.py`
- `tools/sie_autoppt/batch/hashing.py`
- `tools/sie_autoppt/batch/workspace.py`
- `tools/sie_autoppt/batch/input_guard.py`
- `tools/sie_autoppt/batch/dead_letter.py`
- `tools/sie_autoppt/batch/state.py`
- `tools/sie_autoppt/batch/preprocess.py`
- `tools/sie_autoppt/batch/pptmaster_bridge.py`
- `tools/sie_autoppt/batch/export.py`
- `tools/sie_autoppt/batch/tuning.py`
- `tools/sie_autoppt/batch/qa_router.py`
- `tools/sie_autoppt/batch/orchestrator.py`
- `tests/test_batch_contracts.py`
- `tests/test_batch_input_guard.py`
- `tests/test_batch_bridge.py`
- `tests/test_batch_preprocess.py`
- `tests/test_batch_orchestrator.py`
- `tests/test_batch_tuning.py`
- `tests/test_doc_drift.py`

### Modify

- `tools/sie_autoppt/cli_parser.py`
- `tools/sie_autoppt/cli.py`
- `tools/sie_autoppt/v2/services.py`
- `tools/sie_autoppt/v2/io.py`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/CLI_REFERENCE.md`
- `docs/LEGACY_BOUNDARY.md`
- `docs/TESTING.md`
- `.gitignore`

### Keep Compatibility-Only

- `tools/sie_autoppt/generator.py`
- `tools/sie_autoppt/body_renderers.py`
- `tools/sie_autoppt/generation_runtime.py`
- `tools/sie_autoppt/generation_support.py`
- `tools/sie_autoppt/pipeline.py`
- `tools/sie_autoppt/planning/legacy_html_planner.py`
- `tools/sie_autoppt/planning/legacy_html_support.py`

## Execution Order

1. `P0` Task 1-5
2. `P1` Task 6-7

## P0 Tasks

### Task 1: Add Batch Contracts, Hashing, And Workspace Primitives

**Files:**
- Create: `tools/sie_autoppt/batch/__init__.py`
- Create: `tools/sie_autoppt/batch/contracts.py`
- Create: `tools/sie_autoppt/batch/hashing.py`
- Create: `tools/sie_autoppt/batch/workspace.py`
- Test: `tests/test_batch_contracts.py`

- [x] **Step 1: Write the failing tests**

```python
from pathlib import Path

from tools.sie_autoppt.batch.contracts import (
    ExportManifest,
    InputEnvelope,
    InputSource,
    RunMetadata,
)
from tools.sie_autoppt.batch.hashing import sha256_bytes, sha256_text
from tools.sie_autoppt.batch.workspace import BatchWorkspace


def test_sha256_text_is_stable():
    assert sha256_text("alpha") == sha256_text("alpha")
    assert sha256_text("alpha") != sha256_text("beta")


def test_sha256_bytes_prefixes_algorithm():
    digest = sha256_bytes(b"abc")
    assert digest.startswith("sha256:")
    assert len(digest) > len("sha256:")


def test_input_envelope_round_trip():
    envelope = InputEnvelope(
        run=RunMetadata(run_id="run-001", mode="internal_batch"),
        inputs=[
            InputSource(
                source_ref="src-001",
                type="text",
                path="input/source/topic.txt",
                content_hash="sha256:abc",
                mime_type="text/plain",
                size_bytes=12,
                safe=True,
            )
        ],
    )
    payload = envelope.model_dump(mode="json")
    assert payload["run"]["run_id"] == "run-001"
    assert payload["inputs"][0]["source_ref"] == "src-001"


def test_export_manifest_requires_shape_map():
    manifest = ExportManifest(
        run_id="run-001",
        bundle_hash="sha256:bundle",
        svg_bundle_hash="sha256:svg",
        export_hash="sha256:pptx",
        exporter_version="pptmaster-bridge-v1",
        pptx_path="bridge/exported_raw.pptx",
        shape_map=[
            {
                "page_ref": "s-001",
                "svg_node_id": "node-1",
                "ppt_shape_name": "Shape 1",
                "ppt_shape_index": 1,
                "role": "title",
            }
        ],
    )
    assert manifest.shape_map[0].page_ref == "s-001"


def test_batch_workspace_creates_stage_directories(tmp_path: Path):
    workspace = BatchWorkspace.create(root=tmp_path, run_id="run-001")
    assert workspace.run_dir.exists()
    assert workspace.input_dir.exists()
    assert workspace.preprocess_dir.exists()
    assert workspace.bridge_dir.exists()
    assert workspace.tune_dir.exists()
    assert workspace.qa_dir.exists()
    assert workspace.final_dir.exists()
    assert workspace.logs_dir.exists()
```

- [x] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_batch_contracts.py -q`  
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.sie_autoppt.batch'`.

- [x] **Step 3: Write the minimal implementation**

Create `tools/sie_autoppt/batch/__init__.py`:

```python
from .contracts import ExportManifest, InputEnvelope, InputSource, RunMetadata
from .workspace import BatchWorkspace

__all__ = [
    "BatchWorkspace",
    "ExportManifest",
    "InputEnvelope",
    "InputSource",
    "RunMetadata",
]
```

Create `tools/sie_autoppt/batch/hashing.py`:

```python
from __future__ import annotations

import hashlib
from pathlib import Path


def _format_digest(raw: bytes) -> str:
    return f"sha256:{raw.hex()}"


def sha256_bytes(payload: bytes) -> str:
    return _format_digest(hashlib.sha256(payload).digest())


def sha256_text(payload: str) -> str:
    return sha256_bytes(payload.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())
```

Create `tools/sie_autoppt/batch/contracts.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class RunMetadata(BaseModel):
    run_id: str = Field(min_length=1)
    mode: Literal["internal_batch"] = "internal_batch"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InputSource(BaseModel):
    source_ref: str = Field(min_length=1)
    type: Literal["text", "link", "image", "attachment", "structured_data"]
    path: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    mime_type: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    safe: bool


class InputEnvelope(BaseModel):
    run: RunMetadata
    inputs: list[InputSource]


class ShapeMapEntry(BaseModel):
    page_ref: str = Field(min_length=1)
    svg_node_id: str = Field(min_length=1)
    ppt_shape_name: str = Field(min_length=1)
    ppt_shape_index: int = Field(ge=0)
    role: str = Field(min_length=1)


class ExportManifest(BaseModel):
    run_id: str = Field(min_length=1)
    bundle_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    svg_bundle_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    export_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    exporter_version: str = Field(min_length=1)
    pptx_path: str = Field(min_length=1)
    shape_map: list[ShapeMapEntry]
```

Create `tools/sie_autoppt/batch/workspace.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BatchWorkspace:
    run_dir: Path
    input_dir: Path
    preprocess_dir: Path
    bridge_dir: Path
    tune_dir: Path
    qa_dir: Path
    final_dir: Path
    logs_dir: Path

    @classmethod
    def create(cls, *, root: Path, run_id: str) -> "BatchWorkspace":
        run_dir = root / "runs" / run_id
        input_dir = run_dir / "input"
        preprocess_dir = run_dir / "preprocess"
        bridge_dir = run_dir / "bridge"
        tune_dir = run_dir / "tune"
        qa_dir = run_dir / "qa"
        final_dir = run_dir / "final"
        logs_dir = run_dir / "logs"
        for path in (
            input_dir,
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
            preprocess_dir=preprocess_dir,
            bridge_dir=bridge_dir,
            tune_dir=tune_dir,
            qa_dir=qa_dir,
            final_dir=final_dir,
            logs_dir=logs_dir,
        )
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_batch_contracts.py -q`  
Expected: all tests in `tests/test_batch_contracts.py` PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add tools/sie_autoppt/batch/__init__.py tools/sie_autoppt/batch/contracts.py tools/sie_autoppt/batch/hashing.py tools/sie_autoppt/batch/workspace.py tests/test_batch_contracts.py
git commit -m "feat: add batch workspace and artifact contracts"
```

### Task 2: Add Input Guard And Dead Letter Support

**Files:**
- Create: `tools/sie_autoppt/batch/input_guard.py`
- Create: `tools/sie_autoppt/batch/dead_letter.py`
- Test: `tests/test_batch_input_guard.py`

- [x] **Step 1: Write the failing tests**

```python
from pathlib import Path

import pytest

from tools.sie_autoppt.batch.dead_letter import write_dead_letter
from tools.sie_autoppt.batch.input_guard import InputGuardConfig, validate_local_inputs


def test_validate_local_inputs_rejects_oversized_file(tmp_path: Path):
    oversized = tmp_path / "big.txt"
    oversized.write_text("x" * 16, encoding="utf-8")
    config = InputGuardConfig(max_bytes=8, allowed_suffixes={".txt"})
    with pytest.raises(ValueError, match="exceeds size limit"):
        validate_local_inputs([oversized], config=config)


def test_validate_local_inputs_rejects_disallowed_suffix(tmp_path: Path):
    payload = tmp_path / "payload.exe"
    payload.write_text("bad", encoding="utf-8")
    config = InputGuardConfig(max_bytes=100, allowed_suffixes={".txt"})
    with pytest.raises(ValueError, match="unsupported file suffix"):
        validate_local_inputs([payload], config=config)


def test_write_dead_letter_persists_failure_payload(tmp_path: Path):
    output = write_dead_letter(
        run_dir=tmp_path,
        payload={
            "run_id": "run-001",
            "stage": "SVG_GENERATING",
            "error_code": "bridge_timeout",
            "message": "pptmaster bridge timed out",
        },
    )
    assert output.exists()
    assert "bridge_timeout" in output.read_text(encoding="utf-8")
```

- [x] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_batch_input_guard.py -q`  
Expected: FAIL with `ModuleNotFoundError` for the new batch modules.

- [x] **Step 3: Write the minimal implementation**

Create `tools/sie_autoppt/batch/input_guard.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InputGuardConfig:
    max_bytes: int
    allowed_suffixes: set[str]


def validate_local_inputs(paths: list[Path], *, config: InputGuardConfig) -> list[Path]:
    validated: list[Path] = []
    for path in paths:
        if path.suffix.lower() not in config.allowed_suffixes:
            raise ValueError(f"unsupported file suffix: {path.suffix}")
        if path.stat().st_size > config.max_bytes:
            raise ValueError(f"{path.name} exceeds size limit {config.max_bytes}")
        validated.append(path)
    return validated
```

Create `tools/sie_autoppt/batch/dead_letter.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_dead_letter(*, run_dir: Path, payload: dict[str, Any]) -> Path:
    target = run_dir / "dead_letter.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_batch_input_guard.py -q`  
Expected: all tests in `tests/test_batch_input_guard.py` PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add tools/sie_autoppt/batch/input_guard.py tools/sie_autoppt/batch/dead_letter.py tests/test_batch_input_guard.py
git commit -m "feat: add batch input safety and dead letter support"
```

### Task 3: Add PPTMaster Bridge Configuration And Export Manifest Validation

**Files:**
- Create: `tools/sie_autoppt/batch/pptmaster_bridge.py`
- Create: `tools/sie_autoppt/batch/export.py`
- Modify: `tools/sie_autoppt/cli_parser.py`
- Test: `tests/test_batch_bridge.py`

- [x] **Step 1: Write the failing tests**

```python
from pathlib import Path

import pytest

from tools.sie_autoppt.batch.export import verify_export_manifest_hash
from tools.sie_autoppt.batch.pptmaster_bridge import BridgeConfig, resolve_bridge_root


def test_resolve_bridge_root_raises_when_root_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="SIE_PPTMASTER_ROOT"):
        resolve_bridge_root(config=BridgeConfig(pptmaster_root=str(tmp_path / "missing")))


def test_verify_export_manifest_hash_rejects_mismatched_file(tmp_path: Path):
    pptx_path = tmp_path / "exported_raw.pptx"
    pptx_path.write_bytes(b"pptx")
    with pytest.raises(ValueError, match="export hash mismatch"):
        verify_export_manifest_hash(
            pptx_path=pptx_path,
            expected_hash="sha256:deadbeef",
        )
```

- [x] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_batch_bridge.py -q`  
Expected: FAIL because `pptmaster_bridge.py` and `export.py` do not exist.

- [x] **Step 3: Write the minimal implementation**

Create `tools/sie_autoppt/batch/pptmaster_bridge.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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
```

Create `tools/sie_autoppt/batch/export.py`:

```python
from __future__ import annotations

from pathlib import Path

from .hashing import sha256_file


def verify_export_manifest_hash(*, pptx_path: Path, expected_hash: str) -> None:
    actual = sha256_file(pptx_path)
    if actual != expected_hash:
        raise ValueError(f"export hash mismatch: expected {expected_hash}, got {actual}")
```

Modify `tools/sie_autoppt/cli_parser.py`:

```python
    parser.add_argument(
        "--pptmaster-root",
        default="",
        help="Absolute path to the external pptmaster repository root. Overrides SIE_PPTMASTER_ROOT.",
    )
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_batch_bridge.py -q`  
Expected: all tests in `tests/test_batch_bridge.py` PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add tools/sie_autoppt/batch/pptmaster_bridge.py tools/sie_autoppt/batch/export.py tools/sie_autoppt/cli_parser.py tests/test_batch_bridge.py
git commit -m "feat: add pptmaster bridge configuration and export hash checks"
```

### Task 4: Extract Batch Preprocess Adapter From V2 Services

**Files:**
- Create: `tools/sie_autoppt/batch/preprocess.py`
- Modify: `tools/sie_autoppt/v2/services.py`
- Test: `tests/test_batch_preprocess.py`

- [x] **Step 1: Write the failing tests**

```python
from unittest.mock import patch

from tools.sie_autoppt.batch.preprocess import build_content_bundle
from tools.sie_autoppt.v2.schema import OutlineDocument


def test_build_content_bundle_uses_v2_outline_and_semantic_generation():
    outline = OutlineDocument.model_validate(
        {
            "pages": [
                {"slide_id": "s-001", "title": "Overview", "intent": "section_break"},
            ]
        }
    )
    semantic_payload = {
        "meta": {"title": "AI Strategy", "theme": "sie_consulting_fixed", "language": "zh-CN", "author": "AI Auto PPT", "version": "v1"},
        "slides": [{"slide_id": "s-001", "intent": "section_break", "blocks": []}],
    }
    with (
        patch("tools.sie_autoppt.batch.preprocess.generate_outline_with_ai", return_value=outline),
        patch("tools.sie_autoppt.batch.preprocess.generate_semantic_deck_with_ai", return_value=semantic_payload),
    ):
        bundle = build_content_bundle(
            topic="AI Strategy",
            brief="Executive audience",
            audience="Executive team",
            language="zh-CN",
            theme="sie_consulting_fixed",
            model=None,
        )
    assert bundle["topic"] == "AI Strategy"
    assert bundle["story_plan"]["outline"][0]["slide_ref"] == "s-001"
    assert bundle["semantic_payload"]["slides"][0]["slide_id"] == "s-001"
```

- [x] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_batch_preprocess.py -q`  
Expected: FAIL because `batch/preprocess.py` does not exist.

- [x] **Step 3: Write the minimal implementation**

Create `tools/sie_autoppt/batch/preprocess.py`:

```python
from __future__ import annotations

from typing import Any

from ..clarifier import DEFAULT_AUDIENCE_HINT
from ..v2.services import DeckGenerationRequest, OutlineGenerationRequest, generate_outline_with_ai, generate_semantic_deck_with_ai


def build_content_bundle(
    *,
    topic: str,
    brief: str,
    audience: str,
    language: str,
    theme: str,
    model: str | None,
) -> dict[str, Any]:
    outline = generate_outline_with_ai(
        OutlineGenerationRequest(
            topic=topic,
            brief=brief,
            audience=audience or DEFAULT_AUDIENCE_HINT,
            language=language,
            theme=theme,
        ),
        model=model,
    )
    semantic_payload = generate_semantic_deck_with_ai(
        DeckGenerationRequest(
            topic=topic,
            outline=outline,
            brief=brief,
            audience=audience or DEFAULT_AUDIENCE_HINT,
            language=language,
            theme=theme,
        ),
        model=model,
    )
    return {
        "bundle_version": 1,
        "topic": topic,
        "audience": audience or DEFAULT_AUDIENCE_HINT,
        "language": language,
        "text_summary": {
            "summary": brief or topic,
            "key_points": [topic],
            "source_refs": ["src-topic"],
        },
        "story_plan": {
            "outline": [
                {
                    "slide_ref": page.slide_id,
                    "intent": getattr(page, "intent", "unknown"),
                    "title": page.title,
                    "source_refs": ["src-topic"],
                }
                for page in outline.pages
            ]
        },
        "semantic_payload": semantic_payload,
    }
```

Modify `tools/sie_autoppt/v2/services.py` by extracting the current semantic generation steps into a reusable helper:

```python
def generate_compiled_v2_deck(
    *,
    topic: str,
    brief: str,
    audience: str,
    language: str,
    theme: str,
    author: str,
    model: str | None,
    exact_slides: int | None = None,
    min_slides: int = 6,
    max_slides: int = 10,
    generation_mode: str = "deep",
) -> ValidatedDeck:
    normalized_language = normalize_language_code(language)
    resolved_generation_mode = normalize_generation_mode(generation_mode)
    structured_context, strategic_analysis = ensure_generation_context(
        topic=topic,
        brief=brief,
        audience=audience,
        language=normalized_language,
        generation_mode=resolved_generation_mode,
        structured_context=None,
        strategic_analysis=None,
        model=model,
    )
    outline = generate_outline_with_ai(
        OutlineGenerationRequest(
            topic=topic,
            brief=brief,
            audience=audience,
            language=normalized_language,
            theme=theme,
            exact_slides=exact_slides,
            min_slides=min_slides,
            max_slides=max_slides,
            generation_mode=resolved_generation_mode,
            structured_context=structured_context,
            strategic_analysis=strategic_analysis,
        ),
        model=model,
    )
    semantic_payload = generate_semantic_deck_with_ai(
        DeckGenerationRequest(
            topic=topic,
            outline=outline,
            brief=brief,
            audience=audience,
            language=normalized_language,
            theme=theme,
            author=author,
            generation_mode=resolved_generation_mode,
            structured_context=structured_context,
            strategic_analysis=strategic_analysis,
        ),
        model=model,
    )
    return compile_semantic_deck_payload(
        semantic_payload,
        default_title=topic,
        default_theme=theme,
        default_language=normalized_language,
        default_author=author,
    )
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_batch_preprocess.py tests/test_v2_services.py -q`  
Expected: new batch preprocess tests PASS and existing `tests/test_v2_services.py` stays green.

- [ ] **Step 5: Commit**

Run:

```bash
git add tools/sie_autoppt/batch/preprocess.py tools/sie_autoppt/v2/services.py tests/test_batch_preprocess.py
git commit -m "refactor: extract reusable batch preprocess adapter from v2 services"
```

### Task 5: Implement Batch State Machine And CLI Wiring

**Files:**
- Create: `tools/sie_autoppt/batch/state.py`
- Create: `tools/sie_autoppt/batch/orchestrator.py`
- Modify: `tools/sie_autoppt/cli.py`
- Modify: `tools/sie_autoppt/cli_parser.py`
- Test: `tests/test_batch_orchestrator.py`

- [x] **Step 1: Write the failing tests**

```python
from pathlib import Path

from tools.sie_autoppt.batch.orchestrator import BatchMakeRequest, run_batch_make


def test_run_batch_make_creates_isolated_run_workspace(tmp_path: Path):
    request = BatchMakeRequest(
        topic="AI strategy",
        brief="Executive summary",
        audience="Executive team",
        language="zh-CN",
        theme="sie_consulting_fixed",
        output_root=tmp_path,
        run_id="run-001",
    )

    def fake_preprocess(**kwargs):
        return {
            "bundle_version": 1,
            "topic": kwargs["topic"],
            "audience": kwargs["audience"],
            "language": kwargs["language"],
            "story_plan": {"outline": []},
            "semantic_payload": {"meta": {}, "slides": []},
        }

    def fake_bridge(*, workspace, bundle, bridge_root):
        svg_dir = workspace.bridge_dir / "svg_project"
        svg_dir.mkdir(parents=True, exist_ok=True)
        pptx_path = workspace.bridge_dir / "exported_raw.pptx"
        pptx_path.write_bytes(b"pptx")
        return {
            "svg_bundle_hash": "sha256:svg",
            "export_hash": "sha256:export",
            "pptx_path": pptx_path,
            "shape_map": [],
        }

    result = run_batch_make(
        request=request,
        preprocess_fn=fake_preprocess,
        bridge_fn=fake_bridge,
        qa_fn=lambda **kwargs: {"status": "passed", "issues": []},
        tuning_fn=lambda **kwargs: kwargs["export_manifest"],
        bridge_root=tmp_path,
    )

    assert result["state"] == "SUCCEEDED"
    assert (tmp_path / "runs" / "run-001" / "input").exists()
    assert (tmp_path / "runs" / "run-001" / "bridge" / "export_manifest.json").exists()
```

- [x] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_batch_orchestrator.py -q`  
Expected: FAIL because `orchestrator.py` and `state.py` do not exist.

- [x] **Step 3: Write the minimal implementation**

Create `tools/sie_autoppt/batch/state.py`:

```python
from __future__ import annotations

from enum import StrEnum


class BatchState(StrEnum):
    INIT = "INIT"
    INPUT_VALIDATED = "INPUT_VALIDATED"
    BUNDLE_READY = "BUNDLE_READY"
    EXPORT_READY = "EXPORT_READY"
    TUNING = "TUNING"
    QA_CHECKING = "QA_CHECKING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
```

Create `tools/sie_autoppt/batch/orchestrator.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .contracts import ExportManifest, RunMetadata
from .state import BatchState
from .workspace import BatchWorkspace


@dataclass(frozen=True)
class BatchMakeRequest:
    topic: str
    brief: str
    audience: str
    language: str
    theme: str
    output_root: Path
    run_id: str
    model: str | None = None


def run_batch_make(
    *,
    request: BatchMakeRequest,
    preprocess_fn: Callable[..., dict[str, Any]],
    bridge_fn: Callable[..., dict[str, Any]],
    tuning_fn: Callable[..., Any],
    qa_fn: Callable[..., dict[str, Any]],
    bridge_root: Path,
) -> dict[str, Any]:
    workspace = BatchWorkspace.create(root=request.output_root, run_id=request.run_id)
    run_meta = RunMetadata(run_id=request.run_id)
    (workspace.run_dir / "run.json").write_text(
        json.dumps(run_meta.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    bundle = preprocess_fn(
        topic=request.topic,
        brief=request.brief,
        audience=request.audience,
        language=request.language,
        theme=request.theme,
        model=request.model,
    )
    (workspace.preprocess_dir / "content_bundle.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    bridge_payload = bridge_fn(workspace=workspace, bundle=bundle, bridge_root=bridge_root)
    export_manifest = ExportManifest(
        run_id=request.run_id,
        bundle_hash=bundle.get("bundle_hash", "sha256:bundle"),
        svg_bundle_hash=bridge_payload["svg_bundle_hash"],
        export_hash=bridge_payload["export_hash"],
        exporter_version="pptmaster-bridge-v1",
        pptx_path=str(bridge_payload["pptx_path"]),
        shape_map=bridge_payload["shape_map"],
    )
    export_manifest_path = workspace.bridge_dir / "export_manifest.json"
    export_manifest_path.write_text(
        export_manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )
    tuning_fn(workspace=workspace, export_manifest=export_manifest)
    qa_payload = qa_fn(workspace=workspace, export_manifest=export_manifest)
    (workspace.qa_dir / "qa_report.json").write_text(
        json.dumps(qa_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if qa_payload["status"] != "passed":
        return {"state": BatchState.FAILED.value, "run_dir": str(workspace.run_dir)}
    final_path = workspace.final_dir / "final.pptx"
    Path(export_manifest.pptx_path).replace(final_path)
    return {"state": BatchState.SUCCEEDED.value, "run_dir": str(workspace.run_dir), "final_pptx": str(final_path)}
```

Modify `tools/sie_autoppt/cli_parser.py`:

```python
    parser.add_argument(
        "command",
        nargs="?",
        metavar="command",
        default="make",
        help="Primary commands: make, review, iterate, batch-make. Use onepage for a single SIE body slide (agent-driven).",
    )
```

Modify `tools/sie_autoppt/cli.py`:

```python
WORKFLOW_COMMANDS = (
    "make",
    "batch-make",
    "onepage",
    "ai-check",
    "clarify",
    "clarify-web",
    "v2-outline",
    "v2-plan",
    "v2-compile",
    "v2-patch",
    "v2-render",
    "v2-make",
    "v2-review",
    "v2-iterate",
    "review",
    "iterate",
    "visual-draft",
)
```

Add a dedicated branch near the command handling path:

```python
    if effective_command == "batch-make":
        from .batch.orchestrator import BatchMakeRequest, run_batch_make
        from .batch.preprocess import build_content_bundle
        from .batch.state import BatchState

        request = BatchMakeRequest(
            topic=resolved_topic or args.topic.strip(),
            brief=resolved_brief,
            audience=resolved_audience,
            language=args.language,
            theme=v2_theme or "sie_consulting_fixed",
            output_root=Path(args.output_dir),
            run_id=args.run_id.strip() or "batch-run",
            model=args.llm_model.strip() or None,
        )
        result = run_batch_make(
            request=request,
            preprocess_fn=build_content_bundle,
            bridge_fn=lambda **kwargs: (_ for _ in ()).throw(NotImplementedError("real bridge wiring added in Task 6")),
            tuning_fn=lambda **kwargs: kwargs["export_manifest"],
            qa_fn=lambda **kwargs: {"status": "passed", "issues": []},
            bridge_root=Path(args.pptmaster_root),
        )
        print(result["state"])
        return
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_batch_orchestrator.py -q`  
Expected: all tests in `tests/test_batch_orchestrator.py` PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add tools/sie_autoppt/batch/state.py tools/sie_autoppt/batch/orchestrator.py tools/sie_autoppt/cli_parser.py tools/sie_autoppt/cli.py tests/test_batch_orchestrator.py
git commit -m "feat: add batch orchestrator and cli entrypoint"
```

## P1 Tasks

### Task 6: Add Deterministic Tuning And QA Routing

**Files:**
- Create: `tools/sie_autoppt/batch/tuning.py`
- Create: `tools/sie_autoppt/batch/qa_router.py`
- Test: `tests/test_batch_tuning.py`

- [x] **Step 1: Write the failing tests**

```python
from pathlib import Path

import pytest

from tools.sie_autoppt.batch.contracts import ExportManifest
from tools.sie_autoppt.batch.qa_router import route_qa_issues
from tools.sie_autoppt.batch.tuning import verify_manifest_before_tuning


def test_route_qa_issues_sends_style_issue_to_tune():
    route = route_qa_issues(
        [
            {
                "issue_id": "qa-001",
                "class": "style",
                "severity": "warning",
                "repair_route": "tune",
                "page_ref": "s-001",
                "message": "font mismatch",
            }
        ]
    )
    assert route == "tune"


def test_route_qa_issues_sends_layout_issue_to_regenerate():
    route = route_qa_issues(
        [
            {
                "issue_id": "qa-002",
                "class": "layout",
                "severity": "high",
                "repair_route": "regenerate",
                "page_ref": "s-001",
                "message": "content overflow",
            }
        ]
    )
    assert route == "regenerate"


def test_verify_manifest_before_tuning_rejects_hash_mismatch(tmp_path: Path):
    pptx = tmp_path / "exported_raw.pptx"
    pptx.write_bytes(b"pptx")
    manifest = ExportManifest(
        run_id="run-001",
        bundle_hash="sha256:abcd",
        svg_bundle_hash="sha256:1234",
        export_hash="sha256:deadbeef",
        exporter_version="pptmaster-bridge-v1",
        pptx_path=str(pptx),
        shape_map=[],
    )
    with pytest.raises(ValueError, match="export hash mismatch"):
        verify_manifest_before_tuning(manifest)
```

- [x] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_batch_tuning.py -q`  
Expected: FAIL because the tuning and routing modules do not exist.

- [x] **Step 3: Write the minimal implementation**

Create `tools/sie_autoppt/batch/qa_router.py`:

```python
from __future__ import annotations


def route_qa_issues(issues: list[dict[str, str]]) -> str:
    if any(issue["repair_route"] == "stop" for issue in issues):
        return "stop"
    if any(issue["repair_route"] == "regenerate" for issue in issues):
        return "regenerate"
    return "tune"
```

Create `tools/sie_autoppt/batch/tuning.py`:

```python
from __future__ import annotations

from pathlib import Path

from .contracts import ExportManifest
from .hashing import sha256_file


def verify_manifest_before_tuning(manifest: ExportManifest) -> None:
    pptx_path = Path(manifest.pptx_path)
    actual_hash = sha256_file(pptx_path)
    if actual_hash != manifest.export_hash:
        raise ValueError(f"export hash mismatch: expected {manifest.export_hash}, got {actual_hash}")
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_batch_tuning.py -q`  
Expected: all tests in `tests/test_batch_tuning.py` PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add tools/sie_autoppt/batch/tuning.py tools/sie_autoppt/batch/qa_router.py tests/test_batch_tuning.py
git commit -m "feat: add batch tuning verification and qa routing"
```

### Task 7: Align Documentation, Add Drift Tests, And Clean Repo Hygiene

**Files:**
- Create: `tests/test_doc_drift.py`
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/CLI_REFERENCE.md`
- Modify: `docs/LEGACY_BOUNDARY.md`
- Modify: `docs/TESTING.md`
- Modify: `.gitignore`

- [x] **Step 1: Write the failing tests**

```python
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_testing_doc_does_not_reference_missing_scripts():
    testing_doc = (REPO_ROOT / "docs" / "TESTING.md").read_text(encoding="utf-8")
    assert "tools/check_legacy_boundary.py" not in testing_doc
    assert "tools/stress_test_v2.py" not in testing_doc


def test_cli_reference_mentions_batch_make():
    cli_doc = (REPO_ROOT / "docs" / "CLI_REFERENCE.md").read_text(encoding="utf-8")
    assert "batch-make" in cli_doc


def test_gitignore_covers_repo_temp_directories():
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".tmp_ppt_master_research/" in gitignore
    assert ".tmp_test_runtime/" in gitignore
    assert ".tmp_test_workspace/" in gitignore
```

- [x] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_doc_drift.py -q`  
Expected: FAIL because docs and `.gitignore` do not yet match the new batch architecture.

- [x] **Step 3: Update docs and repo hygiene**

Add these lines to `.gitignore`:

```gitignore
.tmp_ppt_master_research/
.tmp_pytest_cache/
.tmp_test_runtime/
.tmp_test_workspace/
.mypy_cache/
.ruff_cache/
__pycache__/
output/runs/
```

Update `README.md` to add the new workflow line under capabilities and quick start:

```md
- Internal batch pipeline with run-scoped artifacts, `pptmaster` bridge integration, and deterministic post-export tuning.
```

```powershell
enterprise-ai-ppt batch-make `
  --topic "Enterprise AI adoption roadmap" `
  --brief "Audience: executive team. Focus on current pain points, target architecture, phased rollout, and expected value." `
  --generation-mode deep `
  --pptmaster-root "D:\path\to\ppt-master" `
  --run-id run-001 `
  --output-dir .\output
```

Update `docs/ARCHITECTURE.md`:

```md
## Current Architecture

This document now distinguishes between the current V2 semantic path and the target internal batch path. The internal batch path owns run isolation, artifact manifests, `pptmaster` bridge configuration, deterministic tuning, and QA routing.
```

Update `docs/CLI_REFERENCE.md`:

```md
| `batch-make` | Internal batch pipeline (`input -> content bundle -> pptmaster -> tuning -> QA`) | Yes | `output/runs/<run-id>/final/final.pptx` |
```

Update `docs/LEGACY_BOUNDARY.md`:

```md
- `batch-make` must not import or route through `generator.py`, `body_renderers.py`, or `planning/legacy_html_planner.py`.
- Legacy modules remain compatibility-only and are not part of the internal batch control plane.
```

Update `docs/TESTING.md`:

````md
## Internal Batch Test Entry

Run the local batch-focused subset:

```powershell
python -m pytest tests/test_batch_contracts.py tests/test_batch_input_guard.py tests/test_batch_bridge.py tests/test_batch_preprocess.py tests/test_batch_orchestrator.py tests/test_batch_tuning.py tests/test_doc_drift.py -q
```

The document must no longer reference missing helper scripts.
````

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_doc_drift.py -q`  
Expected: all tests in `tests/test_doc_drift.py` PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add .gitignore README.md docs/ARCHITECTURE.md docs/CLI_REFERENCE.md docs/LEGACY_BOUNDARY.md docs/TESTING.md tests/test_doc_drift.py
git commit -m "docs: align batch architecture docs and repo hygiene"
```

## Final Verification

- [x] Run the combined `P0` test subset

Run:

```bash
python -m pytest tests/test_batch_contracts.py tests/test_batch_input_guard.py tests/test_batch_bridge.py tests/test_batch_preprocess.py tests/test_batch_orchestrator.py tests/test_batch_tuning.py tests/test_doc_drift.py -q
```

Expected: the full batch-focused subset PASS.

- [x] Run the existing semantic compatibility subset

Run:

```bash
python -m pytest tests/test_v2_services.py tests/test_v2_cli.py tests/test_quality_gate.py -q
```

Expected: no regression in the current V2-compatible path.

- [x] Run a local CLI smoke command with a fake or real bridge root

Run:

```bash
python .\main.py batch-make --topic "AI strategy" --brief "Executive deck" --audience "Executive team" --language zh-CN --theme sie_consulting_fixed --pptmaster-root D:\path\to\ppt-master --run-id smoke-run --output-dir .\output
```

Expected: the command creates `output/runs/smoke-run/` with stage directories and writes either `final/final.pptx` or a clear `dead_letter.json`.

## 2026-04-18 Execution Evidence

- `python -m pytest tests/test_batch_contracts.py tests/test_batch_input_guard.py tests/test_batch_bridge.py tests/test_batch_preprocess.py tests/test_batch_orchestrator.py tests/test_batch_tuning.py tests/test_doc_drift.py -q`  
  Result: `57 passed in 5.40s`.
- `python -m pytest tests/test_v2_services.py tests/test_v2_cli.py tests/test_quality_gate.py -q`  
  Result: `56 passed in 3.87s`.
- Real bridge root validation used:  
  `C:\Users\CHENHU\Documents\cursor\project\pptmaster\ppt-master` with:
  - `skills/ppt-master/scripts/total_md_split.py`
  - `skills/ppt-master/scripts/finalize_svg.py`
  - `skills/ppt-master/scripts/svg_to_pptx.py`
- Smoke success path command:
  `python .\main.py batch-make --content-bundle-json C:\Users\CHENHU\Documents\cursor\project\AI-atuo-ppt\Enterprise-AI-PPT\.tmp_test_runtime\smoke_bundle_min.json --pptmaster-root C:\Users\CHENHU\Documents\cursor\project\pptmaster\ppt-master --run-id smoke-run-bridge2-20260418 --output-dir .\output`  
  Result: `output\runs\smoke-run-bridge2-20260418\final\final.pptx`, and `final/run_summary.json` with `final_state=SUCCEEDED`.
- Smoke failure path evidence (non-blocking runtime precondition):
  `output/runs/smoke-run-20260418/dead_letter.json` contains `stage=PREPROCESSING`, `failure_code=preprocess_failed`, `retry_attempts=2`.
- Accepted deviation preserved: [docs/superpowers/2026-04-18-internal-batch-accepted-deviations.md](c:/Users/CHENHU/Documents/cursor/project/AI-atuo-ppt/Enterprise-AI-PPT/docs/superpowers/2026-04-18-internal-batch-accepted-deviations.md).
- Commit steps (`Step 5`) remain intentionally unchecked in this closeout because the current workspace already contains unrelated in-flight changes and this pass is verification/documentation closure only.

## Spec Coverage Check

- Run-scoped outputs and immutable artifacts: covered by Task 1 and Task 5.
- Input safety and dead letter handling: covered by Task 2.
- Explicit `pptmaster` bridge configuration and export integrity: covered by Task 3.
- Extraction of orchestration out of `v2/services.py`: covered by Task 4 and Task 5.
- Deterministic tuning and QA routing: covered by Task 6.
- Documentation drift, cleanup, and legacy quarantine rules: covered by Task 7.

## Risk Notes For Execution

- Do not attempt real `pptmaster` bridge execution before Task 3 lands; use injected fake bridge functions in Task 5 tests.
- Do not move or delete `generator.py` or `body_renderers.py` during `P0`; only tighten boundaries and stop new batch code from using them.
- Keep `make` and `v2-make` behavior stable during `P0`; `batch-make` is the new safe entrypoint until the batch path is proven.
- If `tests/test_v2_services.py` fails after Task 4, revert the `v2/services.py` helper extraction before proceeding to Task 5.

