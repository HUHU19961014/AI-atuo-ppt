from pathlib import Path

import pytest

from tools.sie_autoppt.batch.contracts import (
    ContentBundle,
    ExportManifest,
    InputEnvelope,
    InputSource,
    QaIssue,
    QaReport,
    RunMetadata,
    RunSummary,
    SvgRequest,
    SvgManifest,
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
    run = RunMetadata(run_id="run-001", mode="internal_batch")
    envelope = InputEnvelope(
        run_id=run.run_id,
        created_at=run.created_at,
        mode=run.mode,
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
    assert payload["run_id"] == "run-001"
    assert payload["mode"] == "internal_batch"
    assert payload["inputs"][0]["source_ref"] == "src-001"


def test_export_manifest_accepts_shape_map_entries():
    manifest = ExportManifest(
        run_id="run-001",
        bundle_hash="sha256:" + ("a" * 64),
        svg_bundle_hash="sha256:" + ("b" * 64),
        export_hash="sha256:" + ("c" * 64),
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
    assert workspace.input_source_dir.exists()
    assert workspace.svg_request_path.parent == workspace.bridge_dir


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


def test_content_bundle_round_trip():
    bundle = ContentBundle(
        run_id="run-001",
        bundle_version=1,
        bundle_hash="sha256:" + ("a" * 64),
        language="zh-CN",
        topic="AI Strategy",
        audience="Executive team",
        theme="sie_consulting_fixed",
        source_index=[
            {
                "source_ref": "src-topic",
                "type": "text",
                "content_hash": "sha256:" + ("b" * 64),
            }
        ],
        text_summary={
            "summary": "Executive audience",
            "key_points": ["AI Strategy"],
            "source_refs": ["src-topic"],
        },
        images=[],
        story_plan={
            "outline": [
                {
                    "slide_ref": "s-001",
                    "intent": "section_break",
                    "title": "Overview",
                    "goal": "Summarize strategy",
                    "source_refs": ["src-topic"],
                    "argument_refs": [
                        {
                            "argument": "Need decision this quarter",
                            "source_refs": ["src-topic"],
                            "block_ref": "s-001#b1",
                        }
                    ],
                }
            ]
        },
        semantic_payload={"meta": {}, "slides": []},
    )
    assert bundle.source_index[0].source_ref == "src-topic"
    assert bundle.story_plan.outline[0].argument_refs[0].block_ref == "s-001#b1"


def test_workspace_rejects_existing_run_id(tmp_path: Path):
    BatchWorkspace.create(root=tmp_path, run_id="run-001")
    with pytest.raises(FileExistsError, match="already exists"):
        BatchWorkspace.create(root=tmp_path, run_id="run-001")


def test_qa_report_round_trip():
    report = QaReport(
        run_id="run-001",
        status="repairable",
        route="tune",
        issues=[
            QaIssue(
                issue_id="qa-001",
                class_="style",
                severity="warning",
                repair_route="tune",
                page_ref="s-001",
                message="font mismatch",
            )
        ],
    )
    payload = report.model_dump(mode="json", by_alias=True)
    assert payload["issues"][0]["class"] == "style"
    assert payload["status"] == "repairable"


def test_qa_report_rejects_invalid_status():
    with pytest.raises(ValueError, match="status"):
        QaReport(
            run_id="run-001",
            status="failed-ish",
            route="stop",
            issues=[],
        )


def test_svg_request_round_trip():
    request = SvgRequest(
        run_id="run-001",
        bundle_hash="sha256:" + ("f" * 64),
        content_bundle_path="preprocess/content_bundle.json",
        page_refs=["s-001", "s-002"],
    )
    payload = request.model_dump(mode="json")
    assert payload["content_bundle_path"] == "preprocess/content_bundle.json"
