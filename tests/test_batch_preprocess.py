import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from tools.sie_autoppt.batch.hashing import sha256_text
from tools.sie_autoppt.batch.preprocess import (
    build_content_bundle,
    compute_content_bundle_hash,
    load_content_bundle_artifact,
)
from tools.sie_autoppt.v2.schema import OutlineDocument


def test_build_content_bundle_uses_v2_outline_and_semantic_generation():
    outline = OutlineDocument.model_validate(
        {
            "pages": [
                {"page_no": 1, "title": "Overview", "goal": "Summarize the strategy"},
            ]
        }
    )
    semantic_payload = {
        "meta": {
            "title": "AI Strategy",
            "theme": "sie_consulting_fixed",
            "language": "zh-CN",
            "author": "AI Auto PPT",
            "version": "v1",
        },
        "slides": [{"slide_id": "s-001", "intent": "section_break", "blocks": []}],
    }
    with (
        patch("tools.sie_autoppt.batch.preprocess.generate_outline_with_ai", return_value=outline),
        patch("tools.sie_autoppt.batch.preprocess.generate_semantic_deck_with_ai", return_value=semantic_payload),
    ):
        bundle = build_content_bundle(
            run_id="run-001",
            topic="AI Strategy",
            brief="Executive audience",
            audience="Executive team",
            language="zh-CN",
            theme="sie_consulting_fixed",
            model=None,
        )
    assert bundle["run_id"] == "run-001"
    assert bundle["bundle_hash"].startswith("sha256:")
    assert bundle["source_index"][0]["source_ref"] == "src-topic"
    assert bundle["text_summary"]["source_refs"] == ["src-topic"]
    assert bundle["topic"] == "AI Strategy"
    assert bundle["story_plan"]["outline"][0]["slide_ref"] == "s-001"
    assert bundle["story_plan"]["outline"][0]["source_refs"] == ["src-topic"]
    assert bundle["semantic_payload"]["slides"][0]["slide_id"] == "s-001"
    assert bundle["bundle_hash"] == compute_content_bundle_hash(bundle)


def test_build_content_bundle_propagates_clarify_result_and_slide_bounds():
    outline = OutlineDocument.model_validate(
        {
            "pages": [
                {"page_no": 1, "title": "Overview", "goal": "Summarize the strategy"},
            ]
        }
    )
    semantic_payload = {
        "meta": {
            "title": "AI Strategy",
            "theme": "sie_consulting_fixed",
            "language": "zh-CN",
            "author": "AI Auto PPT",
            "version": "v1",
        },
        "slides": [{"slide_id": "s-001", "intent": "section_break", "blocks": []}],
    }
    clarify_result = {
        "status": "ready",
        "topic": "AI Strategy",
        "audience": "Executive team",
        "min_slides": 7,
        "max_slides": 7,
    }
    with (
        patch("tools.sie_autoppt.batch.preprocess.generate_outline_with_ai", return_value=outline) as outline_mock,
        patch("tools.sie_autoppt.batch.preprocess.generate_semantic_deck_with_ai", return_value=semantic_payload),
    ):
        bundle = build_content_bundle(
            run_id="run-001",
            topic="AI Strategy",
            brief="Executive audience",
            audience="Executive team",
            language="zh-CN",
            theme="sie_consulting_fixed",
            model=None,
            chapters=7,
            min_slides=7,
            max_slides=7,
            clarify_result=clarify_result,
        )

    request = outline_mock.call_args.args[0]
    assert request.exact_slides == 7
    assert request.min_slides == 7
    assert request.max_slides == 7
    assert bundle["clarify_result"] == clarify_result


def test_build_content_bundle_uses_input_envelope_sources_and_images():
    outline = OutlineDocument.model_validate(
        {
            "pages": [
                {"page_no": 1, "title": "Overview", "goal": "Summarize the strategy"},
            ]
        }
    )
    semantic_payload = {
        "meta": {
            "title": "AI Strategy",
            "theme": "sie_consulting_fixed",
            "language": "zh-CN",
            "author": "AI Auto PPT",
            "version": "v1",
        },
        "slides": [{"slide_id": "s-001", "intent": "section_break", "blocks": []}],
    }
    input_envelope = {
        "run_id": "run-001",
        "created_at": "2026-04-18T00:00:00+00:00",
        "mode": "internal_batch",
        "inputs": [
            {
                "source_ref": "src-topic",
                "type": "text",
                "path": "input/source/topic.txt",
                "content_hash": "sha256:" + ("a" * 64),
                "mime_type": "text/plain",
                "size_bytes": 12,
                "safe": True,
            },
            {
                "source_ref": "src-link-001",
                "type": "link",
                "path": "input/source/link-001.url",
                "content_hash": "sha256:" + ("b" * 64),
                "mime_type": "text/uri-list",
                "size_bytes": 24,
                "safe": True,
            },
            {
                "source_ref": "src-image-001",
                "type": "image",
                "path": "input/source/image-001.png",
                "content_hash": "sha256:" + ("c" * 64),
                "mime_type": "image/png",
                "size_bytes": 1024,
                "safe": True,
            },
            {
                "source_ref": "src-attachment-001",
                "type": "attachment",
                "path": "input/source/data-001.pdf",
                "content_hash": "sha256:" + ("d" * 64),
                "mime_type": "application/pdf",
                "size_bytes": 2048,
                "safe": True,
            },
            {
                "source_ref": "src-data-001",
                "type": "structured_data",
                "path": "input/source/table-001.json",
                "content_hash": "sha256:" + ("e" * 64),
                "mime_type": "application/json",
                "size_bytes": 512,
                "safe": True,
            },
        ],
    }
    with (
        patch("tools.sie_autoppt.batch.preprocess.generate_outline_with_ai", return_value=outline),
        patch("tools.sie_autoppt.batch.preprocess.generate_semantic_deck_with_ai", return_value=semantic_payload),
    ):
        bundle = build_content_bundle(
            run_id="run-001",
            topic="AI Strategy",
            brief="Executive audience",
            audience="Executive team",
            language="zh-CN",
            theme="sie_consulting_fixed",
            model=None,
            input_envelope=input_envelope,
        )
    assert {entry["source_ref"] for entry in bundle["source_index"]} == {
        "src-topic",
        "src-link-001",
        "src-image-001",
        "src-attachment-001",
        "src-data-001",
    }
    assert bundle["images"]
    assert bundle["images"][0]["source_refs"] == ["src-image-001"]
    assert set(bundle["story_plan"]["outline"][0]["source_refs"]) == {
        "src-topic",
        "src-link-001",
        "src-image-001",
        "src-attachment-001",
        "src-data-001",
    }


def test_build_content_bundle_selects_best_semantic_candidate_and_builds_argument_refs():
    outline = OutlineDocument.model_validate(
        {
            "pages": [
                {"page_no": 1, "title": "Overview", "goal": "Summarize the strategy"},
                {"page_no": 2, "title": "Execution", "goal": "Explain execution priorities"},
            ]
        }
    )
    semantic_candidates = [
        {
            "meta": {
                "title": "Deck A",
                "theme": "sie_consulting_fixed",
                "language": "zh-CN",
                "author": "AI Auto PPT",
                "version": "v1",
            },
            "slides": [{"slide_id": "s-001", "intent": "section_break", "blocks": []}],
        },
        {
            "meta": {
                "title": "Deck B",
                "theme": "sie_consulting_fixed",
                "language": "zh-CN",
                "author": "AI Auto PPT",
                "version": "v1",
            },
            "slides": [
                {
                    "slide_id": "s-001",
                    "intent": "section_break",
                    "data_sources": [{"claim": "ROI up", "source": "src-topic", "confidence": "medium"}],
                    "blocks": [{"kind": "statement", "text": "Lead with the decision."}],
                },
                {
                    "slide_id": "s-002",
                    "intent": "narrative",
                    "blocks": [{"kind": "bullets", "items": ["Owner assigned", "Milestone defined"]}],
                },
            ],
        },
    ]
    with (
        patch("tools.sie_autoppt.batch.preprocess.generate_outline_with_ai", return_value=outline),
        patch("tools.sie_autoppt.batch.preprocess.generate_semantic_deck_with_ai") as single_mock,
        patch(
            "tools.sie_autoppt.batch.preprocess.generate_semantic_decks_with_ai_batch",
            new=AsyncMock(return_value=semantic_candidates),
        ) as batch_mock,
    ):
        bundle = build_content_bundle(
            run_id="run-001",
            topic="AI Strategy",
            brief="Executive audience",
            audience="Executive team",
            language="zh-CN",
            theme="sie_consulting_fixed",
            model=None,
            semantic_candidate_count=2,
        )

    batch_mock.assert_called_once()
    single_mock.assert_not_called()
    assert bundle["semantic_payload"]["meta"]["title"] == "Deck B"
    assert bundle["story_plan"]["outline"][0]["argument_refs"]
    first_argument = bundle["story_plan"]["outline"][0]["argument_refs"][0]
    assert first_argument["argument"]
    assert first_argument["source_refs"] == ["src-topic"]


def test_load_content_bundle_artifact_rewrites_run_id_and_hash(tmp_path: Path):
    bundle_path = tmp_path / "bundle.json"
    bundle_payload = {
        "run_id": "old-run",
        "bundle_version": 1,
        "bundle_hash": "sha256:" + ("a" * 64),
        "language": "zh-CN",
        "topic": "AI Strategy",
        "audience": "Executive team",
        "theme": "sie_consulting_fixed",
        "source_index": [
            {
                "source_ref": "src-topic",
                "type": "text",
                "content_hash": "sha256:" + ("b" * 64),
            }
        ],
        "text_summary": {
            "summary": "Executive audience",
            "key_points": ["AI Strategy"],
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
        "semantic_payload": {"meta": {}, "slides": []},
    }
    bundle_path.write_text(json.dumps(bundle_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    loaded = load_content_bundle_artifact(path=bundle_path, run_id="new-run")

    assert loaded["run_id"] == "new-run"
    assert loaded["bundle_hash"].startswith("sha256:")
    assert loaded["bundle_hash"] != bundle_payload["bundle_hash"]


def test_compute_content_bundle_hash_ignores_bundle_hash_field():
    bundle = {
        "run_id": "run-001",
        "bundle_version": 1,
        "bundle_hash": "sha256:" + ("a" * 64),
        "language": "zh-CN",
        "topic": "AI Strategy",
        "audience": "Executive team",
        "theme": "sie_consulting_fixed",
        "source_index": [
            {
                "source_ref": "src-topic",
                "type": "text",
                "content_hash": "sha256:" + ("b" * 64),
            }
        ],
        "text_summary": {
            "summary": "Executive audience",
            "key_points": ["AI Strategy"],
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
        "semantic_payload": {"meta": {}, "slides": []},
    }
    digest_a = compute_content_bundle_hash(bundle)
    bundle["bundle_hash"] = "sha256:" + ("f" * 64)
    digest_b = compute_content_bundle_hash(bundle)
    assert digest_a == digest_b
    assert digest_a == sha256_text(
        json.dumps(
            {key: value for key, value in bundle.items() if key != "bundle_hash"},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
