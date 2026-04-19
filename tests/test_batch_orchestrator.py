import json
from pathlib import Path

from tools.sie_autoppt.batch.hashing import sha256_bytes, sha256_text
from tools.sie_autoppt.batch.orchestrator import BatchMakeRequest, run_batch_make
from tools.sie_autoppt.cli import validate_command_name
from tools.sie_autoppt.cli_parser import build_main_parser


def _fake_bundle(**kwargs):
    payload = {
        "run_id": kwargs["run_id"],
        "bundle_version": 1,
        "language": kwargs["language"],
        "topic": kwargs["topic"],
        "audience": kwargs["audience"],
        "theme": kwargs["theme"],
        "source_index": [
            {
                "source_ref": "src-topic",
                "type": "text",
                "content_hash": sha256_text(kwargs["topic"]),
            }
        ],
        "text_summary": {
            "summary": kwargs["brief"] or kwargs["topic"],
            "key_points": [kwargs["topic"]],
            "source_refs": ["src-topic"],
        },
        "images": [],
        "story_plan": {
            "outline": [
                {
                    "slide_ref": "s-001",
                    "intent": "section_break",
                    "title": "Overview",
                    "goal": "Summarize strategy",
                    "source_refs": ["src-topic"],
                }
            ]
        },
        "clarify_result": kwargs.get("clarify_result"),
        "semantic_payload": {
            "meta": {
                "title": kwargs["topic"],
                "theme": kwargs["theme"],
                "language": kwargs["language"],
                "author": "AI Auto PPT",
                "version": "v1",
            },
            "slides": [{"slide_id": "s-001", "intent": "section_break", "blocks": []}],
        },
    }
    payload["bundle_hash"] = sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return payload


def test_batch_make_cli_accepts_pptmaster_root_option():
    parser = build_main_parser()
    args = parser.parse_args(["batch-make", "--pptmaster-root", "C:/pptmaster"])
    assert args.command == "batch-make"
    assert args.pptmaster_root == "C:/pptmaster"


def test_validate_command_name_accepts_batch_make():
    parser = build_main_parser()
    validate_command_name("batch-make", parser)


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
        return _fake_bundle(**kwargs)

    def fake_bridge(*, workspace, bundle, bridge_root):
        svg_dir = workspace.bridge_dir / "svg_project"
        svg_dir.mkdir(parents=True, exist_ok=True)
        pptx_path = workspace.bridge_dir / "exported_raw.pptx"
        pptx_path.write_bytes(b"pptx")
        return {
            "svg_manifest": {
                "run_id": "run-001",
                "bundle_hash": bundle["bundle_hash"],
                "svg_bundle_hash": "sha256:" + ("a" * 64),
                "project_root": "bridge/svg_project",
                "pages": [
                    {
                        "page_ref": "s-001",
                        "svg_path": "bridge/svg_project/slide_01.svg",
                        "svg_hash": "sha256:" + ("e" * 64),
                    }
                ],
            },
            "svg_bundle_hash": "sha256:" + ("a" * 64),
            "export_hash": sha256_bytes(b"pptx"),
            "pptx_path": "bridge/exported_raw.pptx",
            "shape_map": [
                {
                    "page_ref": "s-001",
                    "svg_node_id": "node-1",
                    "ppt_shape_name": "Shape 1",
                    "ppt_shape_index": 1,
                    "role": "title",
                }
            ],
            "shape_map_mode": "heuristic",
        }

    result = run_batch_make(
        request=request,
        preprocess_fn=fake_preprocess,
        bridge_fn=fake_bridge,
        qa_fn=lambda **kwargs: {"run_id": "run-001", "status": "passed", "route": "stop", "issues": []},
        tuning_fn=lambda **kwargs: kwargs["export_manifest"],
        bridge_root=tmp_path,
        pre_export_qa_fn=lambda **kwargs: {"run_id": "run-001", "status": "passed", "route": "stop", "issues": []},
    )

    run_root = tmp_path / "runs" / "run-001"
    assert result["state"] == "SUCCEEDED"
    assert (run_root / "input" / "input_envelope.json").exists()
    assert (run_root / "bridge" / "svg_manifest.json").exists()
    assert (run_root / "bridge" / "export_manifest.json").exists()
    assert (run_root / "preprocess" / "ocr.json").exists()
    assert (run_root / "preprocess" / "image_descriptions.json").exists()
    assert (run_root / "preprocess" / "clarify_result.json").exists()
    assert (run_root / "preprocess" / "planning.json").exists()
    assert (run_root / "tune" / "tune_report.json").exists()
    assert (run_root / "final" / "run_summary.json").exists()
    assert (run_root / "logs" / "spans.jsonl").exists()
    assert (run_root / "logs" / "usage.jsonl").exists()
    assert (run_root / "logs" / "errors.jsonl").exists()

    bundle_payload = json.loads((run_root / "preprocess" / "content_bundle.json").read_text(encoding="utf-8"))
    svg_manifest_payload = json.loads((run_root / "bridge" / "svg_manifest.json").read_text(encoding="utf-8"))
    export_manifest_payload = json.loads((run_root / "bridge" / "export_manifest.json").read_text(encoding="utf-8"))
    assert (
        bundle_payload["bundle_hash"] == svg_manifest_payload["bundle_hash"] == export_manifest_payload["bundle_hash"]
    )
    run_summary = json.loads((run_root / "final" / "run_summary.json").read_text(encoding="utf-8"))
    assert run_summary["shape_map_mode"] == "heuristic"
    assert run_summary["degraded_mode"] is True
    assert run_summary["degraded_reasons"]
    planning_payload = json.loads((run_root / "preprocess" / "planning.json").read_text(encoding="utf-8"))
    assert planning_payload["story_plan"]["outline"][0]["slide_ref"] == "s-001"
    clarify_payload = json.loads((run_root / "preprocess" / "clarify_result.json").read_text(encoding="utf-8"))
    assert clarify_payload["status"] in {"not_available", "ready", "needs_clarification", "external_bundle"}

    spans = (run_root / "logs" / "spans.jsonl").read_text(encoding="utf-8")
    assert "PREPROCESSING" in spans
    assert "SVG_GENERATING" in spans
    assert "EXPORTING" in spans
    assert "SUCCEEDED" in spans


def test_orchestrator_retries_tuning_once_when_qa_routes_to_tune(tmp_path: Path):
    request = BatchMakeRequest(
        topic="AI strategy",
        brief="Executive summary",
        audience="Executive team",
        language="zh-CN",
        theme="sie_consulting_fixed",
        output_root=tmp_path,
        run_id="run-002",
    )
    tune_calls = {"count": 0}
    qa_calls = {"count": 0}

    def fake_preprocess(**kwargs):
        return _fake_bundle(**kwargs)

    def fake_bridge(*, workspace, bundle, bridge_root):
        pptx_path = workspace.bridge_dir / "exported_raw.pptx"
        pptx_path.write_bytes(b"pptx")
        return {
            "svg_manifest": {
                "run_id": "run-002",
                "bundle_hash": bundle["bundle_hash"],
                "svg_bundle_hash": "sha256:" + ("a" * 64),
                "project_root": "bridge/svg_project",
                "pages": [
                    {
                        "page_ref": "s-001",
                        "svg_path": "bridge/svg_project/slide_01.svg",
                        "svg_hash": "sha256:" + ("e" * 64),
                    }
                ],
            },
            "svg_bundle_hash": "sha256:" + ("a" * 64),
            "export_hash": sha256_bytes(b"pptx"),
            "pptx_path": "bridge/exported_raw.pptx",
            "shape_map": [
                {
                    "page_ref": "s-001",
                    "svg_node_id": "node-1",
                    "ppt_shape_name": "Shape 1",
                    "ppt_shape_index": 1,
                    "role": "title",
                }
            ],
            "shape_map_mode": "heuristic",
        }

    def fake_tuning(**kwargs):
        tune_calls["count"] += 1
        return kwargs["export_manifest"]

    def fake_qa(**kwargs):
        qa_calls["count"] += 1
        if qa_calls["count"] == 1:
            return {
                "run_id": "run-002",
                "status": "repairable",
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
        return {"run_id": "run-002", "status": "passed", "route": "stop", "issues": []}

    result = run_batch_make(
        request=request,
        preprocess_fn=fake_preprocess,
        bridge_fn=fake_bridge,
        qa_fn=fake_qa,
        tuning_fn=fake_tuning,
        bridge_root=tmp_path,
        pre_export_qa_fn=lambda **kwargs: {"run_id": "run-002", "status": "passed", "route": "stop", "issues": []},
    )

    assert result["state"] == "SUCCEEDED"
    assert tune_calls["count"] == 2


def test_orchestrator_fails_when_qa_routes_to_regenerate_and_budget_exhausted(tmp_path: Path):
    request = BatchMakeRequest(
        topic="AI strategy",
        brief="Executive summary",
        audience="Executive team",
        language="zh-CN",
        theme="sie_consulting_fixed",
        output_root=tmp_path,
        run_id="run-003",
    )
    bridge_calls = {"count": 0}

    def fake_preprocess(**kwargs):
        return _fake_bundle(**kwargs)

    def fake_bridge(*, workspace, bundle, bridge_root):
        bridge_calls["count"] += 1
        pptx_path = workspace.bridge_dir / "exported_raw.pptx"
        pptx_path.write_bytes(b"pptx")
        return {
            "svg_manifest": {
                "run_id": "run-003",
                "bundle_hash": bundle["bundle_hash"],
                "svg_bundle_hash": "sha256:" + ("a" * 64),
                "project_root": "bridge/svg_project",
                "pages": [
                    {
                        "page_ref": "s-001",
                        "svg_path": "bridge/svg_project/slide_01.svg",
                        "svg_hash": "sha256:" + ("e" * 64),
                    }
                ],
            },
            "svg_bundle_hash": "sha256:" + ("a" * 64),
            "export_hash": sha256_bytes(b"pptx"),
            "pptx_path": "bridge/exported_raw.pptx",
            "shape_map": [
                {
                    "page_ref": "s-001",
                    "svg_node_id": "node-1",
                    "ppt_shape_name": "Shape 1",
                    "ppt_shape_index": 1,
                    "role": "title",
                }
            ],
            "shape_map_mode": "heuristic",
        }

    result = run_batch_make(
        request=request,
        preprocess_fn=fake_preprocess,
        bridge_fn=fake_bridge,
        qa_fn=lambda **kwargs: {
            "run_id": "run-003",
            "status": "repairable",
            "route": "regenerate",
            "issues": [
                {
                    "issue_id": "qa-002",
                    "class": "layout",
                    "severity": "high",
                    "repair_route": "regenerate",
                    "message": "content overflow",
                }
            ],
        },
        tuning_fn=lambda **kwargs: kwargs["export_manifest"],
        bridge_root=tmp_path,
        pre_export_qa_fn=lambda **kwargs: {"run_id": "run-003", "status": "passed", "route": "stop", "issues": []},
    )

    assert result["state"] == "FAILED"
    assert bridge_calls["count"] > 1
    dead_letter = json.loads((tmp_path / "runs" / "run-003" / "dead_letter.json").read_text(encoding="utf-8"))
    assert dead_letter["failure_code"]
    assert dead_letter["retry_attempts"] >= 1


def test_pre_export_qa_failure_stops_before_bridge(tmp_path: Path):
    request = BatchMakeRequest(
        topic="AI strategy",
        brief="Executive summary",
        audience="Executive team",
        language="zh-CN",
        theme="sie_consulting_fixed",
        output_root=tmp_path,
        run_id="run-004",
    )
    bridge_calls = {"count": 0}

    def fake_preprocess(**kwargs):
        return _fake_bundle(**kwargs)

    def fake_bridge(*, workspace, bundle, bridge_root):
        bridge_calls["count"] += 1
        raise AssertionError("bridge should not be called when pre-export QA fails")

    result = run_batch_make(
        request=request,
        preprocess_fn=fake_preprocess,
        bridge_fn=fake_bridge,
        qa_fn=lambda **kwargs: {"run_id": "run-004", "status": "passed", "route": "stop", "issues": []},
        tuning_fn=lambda **kwargs: kwargs["export_manifest"],
        bridge_root=tmp_path,
        pre_export_qa_fn=lambda **kwargs: {
            "run_id": "run-004",
            "status": "failed",
            "route": "stop",
            "issues": [
                {
                    "issue_id": "qa-pre-001",
                    "class": "content",
                    "severity": "error",
                    "repair_route": "stop",
                    "message": "quality gate failed",
                }
            ],
        },
    )

    assert result["state"] == "FAILED"
    assert bridge_calls["count"] == 0


def test_orchestrator_does_not_retry_non_retryable_bridge_error(tmp_path: Path):
    request = BatchMakeRequest(
        topic="AI strategy",
        brief="Executive summary",
        audience="Executive team",
        language="zh-CN",
        theme="sie_consulting_fixed",
        output_root=tmp_path,
        run_id="run-005",
    )
    bridge_calls = {"count": 0}

    def fake_preprocess(**kwargs):
        return _fake_bundle(**kwargs)

    def fake_bridge(*, workspace, bundle, bridge_root):
        _ = (workspace, bundle, bridge_root)
        bridge_calls["count"] += 1
        raise ValueError("unsupported slide intent: section_break")

    result = run_batch_make(
        request=request,
        preprocess_fn=fake_preprocess,
        bridge_fn=fake_bridge,
        qa_fn=lambda **kwargs: {"run_id": "run-005", "status": "passed", "route": "stop", "issues": []},
        tuning_fn=lambda **kwargs: kwargs["export_manifest"],
        bridge_root=tmp_path,
        pre_export_qa_fn=lambda **kwargs: {"run_id": "run-005", "status": "passed", "route": "stop", "issues": []},
    )

    assert result["state"] == "FAILED"
    assert bridge_calls["count"] == 1
    dead_letter = json.loads((tmp_path / "runs" / "run-005" / "dead_letter.json").read_text(encoding="utf-8"))
    assert dead_letter["stage"] == "SVG_GENERATING"
    assert dead_letter["failure_code"] == "bridge_failed"
    assert dead_letter["retry_attempts"] == 0


def test_orchestrator_persists_bridge_attempt_artifacts_for_regeneration(tmp_path: Path):
    request = BatchMakeRequest(
        topic="AI strategy",
        brief="Executive summary",
        audience="Executive team",
        language="zh-CN",
        theme="sie_consulting_fixed",
        output_root=tmp_path,
        run_id="run-006",
    )
    bridge_calls = {"count": 0}
    qa_calls = {"count": 0}

    def fake_preprocess(**kwargs):
        return _fake_bundle(**kwargs)

    def fake_bridge(*, workspace, bundle, bridge_root):
        _ = (bridge_root,)
        bridge_calls["count"] += 1
        pptx_payload = f"pptx-{bridge_calls['count']}".encode("utf-8")
        pptx_path = workspace.bridge_dir / "exported_raw.pptx"
        pptx_path.write_bytes(pptx_payload)
        return {
            "svg_manifest": {
                "run_id": "run-006",
                "bundle_hash": bundle["bundle_hash"],
                "svg_bundle_hash": "sha256:" + ("a" * 64),
                "project_root": "bridge/svg_project",
                "pages": [
                    {
                        "page_ref": "s-001",
                        "svg_path": "bridge/svg_project/slide_01.svg",
                        "svg_hash": "sha256:" + ("e" * 64),
                    }
                ],
            },
            "svg_bundle_hash": "sha256:" + ("a" * 64),
            "export_hash": sha256_bytes(pptx_payload),
            "pptx_path": "bridge/exported_raw.pptx",
            "shape_map": [
                {
                    "page_ref": "s-001",
                    "svg_node_id": "node-1",
                    "ppt_shape_name": "Shape 1",
                    "ppt_shape_index": 1,
                    "role": "title",
                }
            ],
            "shape_map_mode": "heuristic",
        }

    def fake_qa(**kwargs):
        qa_calls["count"] += 1
        if qa_calls["count"] == 1:
            return {
                "run_id": "run-006",
                "status": "repairable",
                "route": "regenerate",
                "issues": [
                    {
                        "issue_id": "qa-regen-001",
                        "class": "layout",
                        "severity": "high",
                        "repair_route": "regenerate",
                        "message": "content overflow",
                    }
                ],
            }
        return {"run_id": "run-006", "status": "passed", "route": "stop", "issues": []}

    result = run_batch_make(
        request=request,
        preprocess_fn=fake_preprocess,
        bridge_fn=fake_bridge,
        qa_fn=fake_qa,
        tuning_fn=lambda **kwargs: kwargs["export_manifest"],
        bridge_root=tmp_path,
        pre_export_qa_fn=lambda **kwargs: {"run_id": "run-006", "status": "passed", "route": "stop", "issues": []},
    )

    assert result["state"] == "SUCCEEDED"
    assert bridge_calls["count"] == 2
    attempts_dir = tmp_path / "runs" / "run-006" / "bridge" / "attempts"
    assert attempts_dir.exists()
    assert len(list(attempts_dir.glob("svg_manifest.attempt-*.json"))) == 2
    assert len(list(attempts_dir.glob("export_manifest.attempt-*.json"))) == 2


def test_run_batch_make_records_multimodal_inputs_in_envelope(tmp_path: Path):
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nfakepng")
    attachment_path = tmp_path / "sample.pdf"
    attachment_path.write_bytes(b"%PDF-1.4\nfake")
    structured_path = tmp_path / "sample.json"
    structured_path.write_text('{"a": 1}', encoding="utf-8")

    request = BatchMakeRequest(
        topic="AI strategy",
        brief="Executive summary",
        audience="Executive team",
        language="zh-CN",
        theme="sie_consulting_fixed",
        output_root=tmp_path,
        run_id="run-007",
        links=("https://example.com/strategy",),
        image_files=(image_path,),
        attachment_files=(attachment_path,),
        structured_data_file=structured_path,
    )

    def fake_preprocess(**kwargs):
        return _fake_bundle(**kwargs)

    def fake_bridge(*, workspace, bundle, bridge_root):
        pptx_path = workspace.bridge_dir / "exported_raw.pptx"
        pptx_path.write_bytes(b"pptx")
        return {
            "svg_manifest": {
                "run_id": "run-007",
                "bundle_hash": bundle["bundle_hash"],
                "svg_bundle_hash": "sha256:" + ("a" * 64),
                "project_root": "bridge/svg_project",
                "pages": [
                    {
                        "page_ref": "s-001",
                        "svg_path": "bridge/svg_project/slide_01.svg",
                        "svg_hash": "sha256:" + ("e" * 64),
                    }
                ],
            },
            "svg_bundle_hash": "sha256:" + ("a" * 64),
            "export_hash": sha256_bytes(b"pptx"),
            "pptx_path": "bridge/exported_raw.pptx",
            "shape_map": [
                {
                    "page_ref": "s-001",
                    "svg_node_id": "node-1",
                    "ppt_shape_name": "Shape 1",
                    "ppt_shape_index": 1,
                    "role": "title",
                }
            ],
            "shape_map_mode": "heuristic",
        }

    result = run_batch_make(
        request=request,
        preprocess_fn=fake_preprocess,
        bridge_fn=fake_bridge,
        qa_fn=lambda **kwargs: {"run_id": "run-007", "status": "passed", "route": "stop", "issues": []},
        tuning_fn=lambda **kwargs: kwargs["export_manifest"],
        bridge_root=tmp_path,
        pre_export_qa_fn=lambda **kwargs: {"run_id": "run-007", "status": "passed", "route": "stop", "issues": []},
    )

    assert result["state"] == "SUCCEEDED"
    run_root = tmp_path / "runs" / "run-007"
    envelope = json.loads((run_root / "input" / "input_envelope.json").read_text(encoding="utf-8"))
    input_types = {item["type"] for item in envelope["inputs"]}
    assert input_types == {"text", "link", "image", "attachment", "structured_data"}
    source_paths = [run_root / item["path"] for item in envelope["inputs"]]
    assert all(path.exists() for path in source_paths)


def test_run_batch_make_invalid_link_maps_to_input_invalid_failure(tmp_path: Path):
    request = BatchMakeRequest(
        topic="AI strategy",
        brief="Executive summary",
        audience="Executive team",
        language="zh-CN",
        theme="sie_consulting_fixed",
        output_root=tmp_path,
        run_id="run-008",
        links=("example.com/no-scheme",),
    )
    preprocess_calls = {"count": 0}

    def fake_preprocess(**kwargs):
        _ = kwargs
        preprocess_calls["count"] += 1
        return _fake_bundle(
            run_id=request.run_id,
            topic=request.topic,
            brief=request.brief,
            audience=request.audience,
            language=request.language,
            theme=request.theme,
        )

    result = run_batch_make(
        request=request,
        preprocess_fn=fake_preprocess,
        bridge_fn=lambda **kwargs: (_ for _ in ()).throw(AssertionError("bridge should not run")),
        qa_fn=lambda **kwargs: {"run_id": "run-008", "status": "passed", "route": "stop", "issues": []},
        tuning_fn=lambda **kwargs: kwargs["export_manifest"],
        bridge_root=tmp_path,
        pre_export_qa_fn=lambda **kwargs: {"run_id": "run-008", "status": "passed", "route": "stop", "issues": []},
    )

    assert result["state"] == "FAILED"
    assert preprocess_calls["count"] == 0
    dead_letter = json.loads((tmp_path / "runs" / "run-008" / "dead_letter.json").read_text(encoding="utf-8"))
    assert dead_letter["failure_code"] == "input_invalid"


def test_run_batch_make_rejects_disallowed_attachment_suffix_when_invoked_directly(tmp_path: Path):
    blocked_attachment = tmp_path / "payload.exe"
    blocked_attachment.write_bytes(b"MZ")

    request = BatchMakeRequest(
        topic="AI strategy",
        brief="Executive summary",
        audience="Executive team",
        language="zh-CN",
        theme="sie_consulting_fixed",
        output_root=tmp_path,
        run_id="run-009",
        attachment_files=(blocked_attachment,),
    )
    preprocess_calls = {"count": 0}

    def fake_preprocess(**kwargs):
        _ = kwargs
        preprocess_calls["count"] += 1
        return _fake_bundle(
            run_id=request.run_id,
            topic=request.topic,
            brief=request.brief,
            audience=request.audience,
            language=request.language,
            theme=request.theme,
        )

    result = run_batch_make(
        request=request,
        preprocess_fn=fake_preprocess,
        bridge_fn=lambda **kwargs: (_ for _ in ()).throw(AssertionError("bridge should not run")),
        qa_fn=lambda **kwargs: {"run_id": "run-009", "status": "passed", "route": "stop", "issues": []},
        tuning_fn=lambda **kwargs: kwargs["export_manifest"],
        bridge_root=tmp_path,
        pre_export_qa_fn=lambda **kwargs: {"run_id": "run-009", "status": "passed", "route": "stop", "issues": []},
    )

    assert result["state"] == "FAILED"
    assert preprocess_calls["count"] == 0
    dead_letter = json.loads((tmp_path / "runs" / "run-009" / "dead_letter.json").read_text(encoding="utf-8"))
    assert dead_letter["failure_code"] == "input_invalid"
    assert "unsupported file suffix" in dead_letter["message"]


def test_orchestrator_maps_export_manifest_validation_error_to_export_invalid(tmp_path: Path):
    request = BatchMakeRequest(
        topic="AI strategy",
        brief="Executive summary",
        audience="Executive team",
        language="zh-CN",
        theme="sie_consulting_fixed",
        output_root=tmp_path,
        run_id="run-010",
    )

    def fake_preprocess(**kwargs):
        return _fake_bundle(**kwargs)

    def fake_bridge(*, workspace, bundle, bridge_root):
        _ = (bundle, bridge_root)
        pptx_path = workspace.bridge_dir / "exported_raw.pptx"
        pptx_path.write_bytes(b"pptx")
        return {
            "svg_manifest": {
                "run_id": "run-010",
                "bundle_hash": _fake_bundle(
                    run_id="run-010",
                    topic="AI strategy",
                    brief="Executive summary",
                    audience="Executive team",
                    language="zh-CN",
                    theme="sie_consulting_fixed",
                )["bundle_hash"],
                "svg_bundle_hash": "sha256:" + ("a" * 64),
                "project_root": "bridge/svg_project",
                "pages": [
                    {
                        "page_ref": "s-001",
                        "svg_path": "bridge/svg_project/slide_01.svg",
                        "svg_hash": "sha256:" + ("b" * 64),
                    }
                ],
            },
            "svg_bundle_hash": "sha256:" + ("a" * 64),
            "export_hash": sha256_bytes(b"pptx"),
            "pptx_path": "bridge/exported_raw.pptx",
            "shape_map": [],
            "shape_map_mode": "heuristic",
        }

    result = run_batch_make(
        request=request,
        preprocess_fn=fake_preprocess,
        bridge_fn=fake_bridge,
        qa_fn=lambda **kwargs: {"run_id": "run-010", "status": "passed", "route": "stop", "issues": []},
        tuning_fn=lambda **kwargs: kwargs["export_manifest"],
        bridge_root=tmp_path,
        pre_export_qa_fn=lambda **kwargs: {"run_id": "run-010", "status": "passed", "route": "stop", "issues": []},
    )

    assert result["state"] == "FAILED"
    dead_letter = json.loads((tmp_path / "runs" / "run-010" / "dead_letter.json").read_text(encoding="utf-8"))
    assert dead_letter["stage"] == "EXPORTING"
    assert dead_letter["failure_code"] == "export_invalid"


def test_orchestrator_runs_optional_review_patch_stage_after_qa_pass(tmp_path: Path):
    request = BatchMakeRequest(
        topic="AI strategy",
        brief="Executive summary",
        audience="Executive team",
        language="zh-CN",
        theme="sie_consulting_fixed",
        output_root=tmp_path,
        run_id="run-011",
    )
    review_calls = {"count": 0}

    def fake_preprocess(**kwargs):
        return _fake_bundle(**kwargs)

    def fake_bridge(*, workspace, bundle, bridge_root):
        _ = (bridge_root,)
        pptx_path = workspace.bridge_dir / "exported_raw.pptx"
        pptx_path.write_bytes(b"pptx")
        return {
            "svg_manifest": {
                "run_id": "run-011",
                "bundle_hash": bundle["bundle_hash"],
                "svg_bundle_hash": "sha256:" + ("a" * 64),
                "project_root": "bridge/svg_project",
                "pages": [
                    {
                        "page_ref": "s-001",
                        "svg_path": "bridge/svg_project/slide_01.svg",
                        "svg_hash": "sha256:" + ("e" * 64),
                    }
                ],
            },
            "svg_bundle_hash": "sha256:" + ("a" * 64),
            "export_hash": sha256_bytes(b"pptx"),
            "pptx_path": "bridge/exported_raw.pptx",
            "shape_map": [
                {
                    "page_ref": "s-001",
                    "svg_node_id": "node-1",
                    "ppt_shape_name": "Shape 1",
                    "ppt_shape_index": 1,
                    "role": "title",
                }
            ],
            "shape_map_mode": "heuristic",
        }

    def fake_review_patch(**kwargs):
        review_calls["count"] += 1
        workspace = kwargs["workspace"]
        review_dir = workspace.qa_dir / "review_patch"
        review_dir.mkdir(parents=True, exist_ok=True)
        (review_dir / "review_once.json").write_text("{}", encoding="utf-8")
        (review_dir / "patches_review_once.json").write_text('{"patches":[]}', encoding="utf-8")
        (review_dir / "patched.deck.json").write_text(
            json.dumps(
                {
                    "meta": {
                        "title": "QA Deck",
                        "theme": "sie_consulting_fixed",
                        "language": "zh-CN",
                        "author": "AI Auto PPT",
                        "version": "2.0",
                    },
                    "slides": [{"slide_id": "s-001", "layout": "title_only", "title": "建议结论"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {
            "review_path": "qa/review_patch/review_once.json",
            "patch_path": "qa/review_patch/patches_review_once.json",
            "patched_deck_path": "qa/review_patch/patched.deck.json",
        }

    result = run_batch_make(
        request=request,
        preprocess_fn=fake_preprocess,
        bridge_fn=fake_bridge,
        qa_fn=lambda **kwargs: {"run_id": "run-011", "status": "passed", "route": "stop", "issues": []},
        tuning_fn=lambda **kwargs: kwargs["export_manifest"],
        bridge_root=tmp_path,
        pre_export_qa_fn=lambda **kwargs: {"run_id": "run-011", "status": "passed", "route": "stop", "issues": []},
        review_patch_fn=fake_review_patch,
    )

    assert result["state"] == "SUCCEEDED"
    assert review_calls["count"] == 1
    review_dir = tmp_path / "runs" / "run-011" / "qa" / "review_patch"
    assert (review_dir / "review_once.json").exists()
    assert (review_dir / "patches_review_once.json").exists()
    assert (review_dir / "patched.deck.json").exists()
