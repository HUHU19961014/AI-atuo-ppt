# Internal Batch PPTMaster P2/P3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen the internal batch pipeline beyond the P0/P1 skeleton by adding typed SVG/export manifests, real deterministic tuning, and state-aware QA routing and repair behavior.

**Architecture:** Keep the existing `tools/sie_autoppt/batch/` control plane, but replace placeholder behavior with real artifact emission and safe post-export edits. `pptmaster` remains the layout producer; Python only verifies manifests, applies deterministic style normalization, and routes layout defects away from Layer 4.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, python-pptx, existing `sie_autoppt.v2` helpers, current batch orchestrator.

---

## Scope

- `P2` in this pass means: typed `svg_manifest.json`, stronger export artifact chain, and real deterministic tuning against exported PPTX.
- `P3` in this pass means: QA issue classification, tune/regenerate/stop routing, one safe repair loop in the orchestrator, and final run summary artifacts.
- This plan does not attempt distributed workers, full visual review automation, or precise SVG-node-to-PPT-shape mapping inside `pptmaster`.

## File Map

### Create

- `tests/test_batch_manifests.py`

### Modify

- `tools/sie_autoppt/batch/contracts.py`
- `tools/sie_autoppt/batch/export.py`
- `tools/sie_autoppt/batch/pptmaster_bridge.py`
- `tools/sie_autoppt/batch/tuning.py`
- `tools/sie_autoppt/batch/qa_router.py`
- `tools/sie_autoppt/batch/orchestrator.py`
- `tests/test_batch_contracts.py`
- `tests/test_batch_bridge.py`
- `tests/test_batch_tuning.py`
- `tests/test_batch_orchestrator.py`

## Task 1: Add Typed SVG Manifest And Run Summary Contracts

**Files:**
- Modify: `tools/sie_autoppt/batch/contracts.py`
- Modify: `tests/test_batch_contracts.py`
- Create: `tests/test_batch_manifests.py`

- [x] **Step 1: Write the failing tests**

Add tests that assert:

```python
from tools.sie_autoppt.batch.contracts import RunSummary, SvgManifest


def test_svg_manifest_round_trip():
    manifest = SvgManifest(
        run_id="run-001",
        bundle_hash="sha256:" + ("a" * 64),
        svg_bundle_hash="sha256:" + ("b" * 64),
        project_root="bridge/svg_project",
        pages=[
            {
                "page_ref": "s-001",
                "svg_path": "bridge/svg_project/svg_final/slide_01.svg",
                "svg_hash": "sha256:" + ("c" * 64),
            }
        ],
    )
    assert manifest.pages[0].page_ref == "s-001"


def test_run_summary_tracks_final_state():
    summary = RunSummary(
        run_id="run-001",
        final_state="SUCCEEDED",
        final_pptx="final/final.pptx",
        bundle_hash="sha256:" + ("a" * 64),
        export_hash="sha256:" + ("b" * 64),
    )
    assert summary.final_state == "SUCCEEDED"
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_batch_contracts.py tests/test_batch_manifests.py -q`  
Expected: FAIL because `SvgManifest` and `RunSummary` do not exist.

- [x] **Step 3: Write the minimal implementation**

Add to `tools/sie_autoppt/batch/contracts.py`:

```python
class SvgPageManifest(BaseModel):
    page_ref: str = Field(min_length=1)
    svg_path: str = Field(min_length=1)
    svg_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")


class SvgManifest(BaseModel):
    run_id: str = Field(min_length=1)
    bundle_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    svg_bundle_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    project_root: str = Field(min_length=1)
    pages: list[SvgPageManifest] = Field(min_length=1)


class RunSummary(BaseModel):
    run_id: str = Field(min_length=1)
    final_state: str = Field(min_length=1)
    final_pptx: str | None = None
    bundle_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    export_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_batch_contracts.py tests/test_batch_manifests.py -q`  
Expected: PASS.

## Task 2: Emit Real SVG Manifest From Bridge

**Files:**
- Modify: `tools/sie_autoppt/batch/export.py`
- Modify: `tools/sie_autoppt/batch/pptmaster_bridge.py`
- Modify: `tests/test_batch_bridge.py`

- [x] **Step 1: Write the failing tests**

Add a test that builds two fake SVG files and asserts:

```python
from tools.sie_autoppt.batch.export import build_svg_manifest


def test_build_svg_manifest_hashes_svg_pages(tmp_path):
    svg_dir = tmp_path / "svg_final"
    svg_dir.mkdir()
    (svg_dir / "slide_01.svg").write_text("<svg>1</svg>", encoding="utf-8")
    (svg_dir / "slide_02.svg").write_text("<svg>2</svg>", encoding="utf-8")

    manifest = build_svg_manifest(
        run_id="run-001",
        bundle_hash="sha256:" + ("a" * 64),
        project_root=tmp_path,
        svg_dir=svg_dir,
        page_refs=["s-001", "s-002"],
    )

    assert manifest.pages[0].page_ref == "s-001"
    assert manifest.pages[1].svg_hash.startswith("sha256:")
```

- [x] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_batch_bridge.py tests/test_batch_manifests.py -q`  
Expected: FAIL because `build_svg_manifest()` does not exist.

- [x] **Step 3: Write the minimal implementation**

Add to `tools/sie_autoppt/batch/export.py`:

```python
def build_svg_manifest(*, run_id: str, bundle_hash: str, project_root: Path, svg_dir: Path, page_refs: list[str]) -> SvgManifest:
    svg_files = sorted(svg_dir.glob("*.svg"))
    pages = []
    for index, svg_path in enumerate(svg_files):
        page_ref = page_refs[index] if index < len(page_refs) else f"s-{index + 1:03d}"
        pages.append(
            {
                "page_ref": page_ref,
                "svg_path": str(svg_path.relative_to(project_root.parent)),
                "svg_hash": sha256_file(svg_path),
            }
        )
    svg_bundle_hash = sha256_text(json.dumps(pages, ensure_ascii=False, sort_keys=True))
    return SvgManifest(
        run_id=run_id,
        bundle_hash=bundle_hash,
        svg_bundle_hash=svg_bundle_hash,
        project_root=str(project_root.relative_to(project_root.parent)),
        pages=pages,
    )
```

Wire `tools/sie_autoppt/batch/pptmaster_bridge.py` to return:

```python
{
    "svg_manifest": svg_manifest.model_dump(mode="json"),
    ...
}
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_batch_bridge.py tests/test_batch_manifests.py -q`  
Expected: PASS.

## Task 3: Replace No-Op Tuning With Deterministic PPTX Normalization

**Files:**
- Modify: `tools/sie_autoppt/batch/tuning.py`
- Modify: `tests/test_batch_tuning.py`

- [x] **Step 1: Write the failing tests**

Add a test that creates a PPTX with explicit wrong font and asserts:

```python
from pptx import Presentation

from tools.sie_autoppt.batch.tuning import run_deterministic_tuning


def test_run_deterministic_tuning_normalizes_font(tmp_path):
    pptx_path = tmp_path / "exported_raw.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    box = slide.shapes.add_textbox(0, 0, 1000000, 1000000)
    run = box.text_frame.paragraphs[0].add_run()
    run.text = "hello"
    run.font.name = "Arial"
    prs.save(pptx_path)

    result = run_deterministic_tuning(
        workspace=BatchWorkspace.create(root=tmp_path, run_id="run-001"),
        export_manifest={
            "run_id": "run-001",
            "bundle_hash": "sha256:" + ("a" * 64),
            "svg_bundle_hash": "sha256:" + ("b" * 64),
            "export_hash": sha256_file(pptx_path),
            "exporter_version": "pptmaster-bridge-v1",
            "pptx_path": str(pptx_path),
            "shape_map": [{"page_ref": "s-001", "svg_node_id": "n1", "ppt_shape_name": "TextBox 1", "ppt_shape_index": 1, "role": "title"}],
        },
    )

    tuned = Presentation(result["pptx_path"])
    assert tuned.slides[0].shapes[0].text_frame.paragraphs[0].runs[0].font.name == "Microsoft YaHei"
```

- [x] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_batch_tuning.py -q`  
Expected: FAIL because real tuning is not implemented.

- [x] **Step 3: Write the minimal implementation**

In `tools/sie_autoppt/batch/tuning.py`, add:

```python
def run_deterministic_tuning(*, workspace: BatchWorkspace, export_manifest: dict[str, Any]) -> dict[str, Any]:
    manifest = ExportManifest.model_validate(export_manifest)
    verify_manifest_before_tuning(manifest)
    source = Path(manifest.pptx_path)
    target = workspace.tune_dir / "tuned.pptx"
    shutil.copy2(source, target)

    prs = Presentation(target)
    actions = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if not getattr(shape, "has_text_frame", False):
                continue
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    if run.font.name != "Microsoft YaHei":
                        run.font.name = "Microsoft YaHei"
                        actions.append("font_name_normalized")
    prs.save(target)
    return {
        "status": "tuned",
        "actions": actions,
        "pptx_path": str(target),
        "tuned_hash": sha256_file(target),
    }
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_batch_tuning.py -q`  
Expected: PASS.

## Task 4: Add QA Classification And One Repair Loop In Orchestrator

**Files:**
- Modify: `tools/sie_autoppt/batch/qa_router.py`
- Modify: `tools/sie_autoppt/batch/orchestrator.py`
- Modify: `tests/test_batch_orchestrator.py`

- [x] **Step 1: Write the failing tests**

Add tests that assert:

```python
def test_orchestrator_retries_tuning_once_when_qa_routes_to_tune(...):
    ...
    assert result["state"] == "SUCCEEDED"
    assert tune_calls == 2


def test_orchestrator_fails_when_qa_routes_to_regenerate(...):
    ...
    assert result["state"] == "FAILED"
    assert "regenerate" in Path(dead_letter_path).read_text(encoding="utf-8")
```

- [x] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_batch_orchestrator.py -q`  
Expected: FAIL because orchestrator only supports pass/fail, not route-aware behavior.

- [x] **Step 3: Write the minimal implementation**

In `tools/sie_autoppt/batch/qa_router.py`, change `run_basic_qa()` to return structured issues:

```python
{
    "status": "failed",
    "route": "tune",
    "issues": [
        {
            "issue_id": "qa-001",
            "class": "style",
            "severity": "warning",
            "repair_route": "tune",
            "message": "font mismatch",
        }
    ],
}
```

In `tools/sie_autoppt/batch/orchestrator.py`, handle:

```python
if qa_result.get("status") != "passed":
    route = qa_result.get("route", "stop")
    if route == "tune":
        tuning_result = tuning_fn(..., qa_result=qa_result)
        qa_result = qa_fn(..., tuning_result=tuning_result)
    elif route == "regenerate":
        raise ValueError("QA requested regenerate route.")
    else:
        raise ValueError("QA requested terminal stop.")
```

Also write `final/run_summary.json` on success.

- [x] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_batch_orchestrator.py tests/test_batch_tuning.py -q`  
Expected: PASS.

## Final Verification

- [x] Run the full batch subset

Run:

```bash
python -m pytest tests/test_batch_contracts.py tests/test_batch_manifests.py tests/test_batch_input_guard.py tests/test_batch_bridge.py tests/test_batch_preprocess.py tests/test_batch_orchestrator.py tests/test_batch_tuning.py tests/test_doc_drift.py -q
```

Expected: PASS.

- [x] Run compatibility subset

Run:

```bash
python -m pytest tests/test_v2_services.py tests/test_v2_cli.py tests/test_quality_gate.py -q
```

Expected: PASS with no regression in current V2 path.

## 2026-04-18 Execution Evidence

- `python -m pytest tests/test_batch_contracts.py tests/test_batch_manifests.py tests/test_batch_input_guard.py tests/test_batch_bridge.py tests/test_batch_preprocess.py tests/test_batch_orchestrator.py tests/test_batch_tuning.py tests/test_doc_drift.py -q`  
  Result: `59 passed in 4.54s`.
- `python -m pytest tests/test_v2_services.py tests/test_v2_cli.py tests/test_quality_gate.py -q`  
  Result: `56 passed in 3.87s`.
- Real bridge smoke and accepted deviation records for this closeout are tracked in:
  - [docs/superpowers/plans/2026-04-17-internal-batch-pptmaster-p0-p1-plan.md](c:/Users/CHENHU/Documents/cursor/project/AI-atuo-ppt/Enterprise-AI-PPT/docs/superpowers/plans/2026-04-17-internal-batch-pptmaster-p0-p1-plan.md)
  - [docs/superpowers/2026-04-18-internal-batch-accepted-deviations.md](c:/Users/CHENHU/Documents/cursor/project/AI-atuo-ppt/Enterprise-AI-PPT/docs/superpowers/2026-04-18-internal-batch-accepted-deviations.md)
