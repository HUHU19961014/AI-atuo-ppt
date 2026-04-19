import json
from pathlib import Path

import pytest

from tools.sie_autoppt.batch.review_patch import run_batch_review_patch_once
from tools.sie_autoppt.batch.workspace import BatchWorkspace
from tools.sie_autoppt.v2.schema import validate_deck_payload


def _semantic_bundle() -> dict:
    return {
        "topic": "AI strategy",
        "theme": "sie_consulting_fixed",
        "language": "zh-CN",
        "semantic_payload": {
            "meta": {
                "title": "AI strategy",
                "theme": "sie_consulting_fixed",
                "language": "zh-CN",
                "author": "AI Auto PPT",
                "version": "2.0",
            },
            "slides": [
                {
                    "slide_id": "s-001",
                    "intent": "section",
                    "title": "项目背景",
                    "blocks": [],
                }
            ],
        },
    }


def _write_review_once_outputs(review_dir: Path, *, deck_title: str, patch_payload: dict) -> Path:
    review_dir.mkdir(parents=True, exist_ok=True)
    review_path = review_dir / "review_once.json"
    patch_path = review_dir / "patches_review_once.json"
    deck_path = review_dir / "review_once.deck.json"
    pptx_path = review_dir / "review_once.pptx"
    preview_dir = review_dir / "previews_review_once"

    review_path.write_text(json.dumps({"summary": "ok"}, ensure_ascii=False), encoding="utf-8")
    patch_path.write_text(json.dumps(patch_payload, ensure_ascii=False), encoding="utf-8")
    deck_path.write_text(
        json.dumps(
            {
                "meta": {
                    "title": "AI strategy",
                    "theme": "sie_consulting_fixed",
                    "language": "zh-CN",
                    "author": "AI Auto PPT",
                    "version": "2.0",
                },
                "slides": [{"slide_id": "s-001", "layout": "title_only", "title": deck_title}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    pptx_path.write_bytes(b"pptx")
    preview_dir.mkdir(parents=True, exist_ok=True)
    return deck_path


def test_run_batch_review_patch_once_writes_standard_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    workspace = BatchWorkspace.create(root=tmp_path, run_id="run-review-001")
    expected_review_dir = workspace.qa_dir / "review_patch"
    _ = validate_deck_payload(
        {
            "meta": {
                "title": "AI strategy",
                "theme": "sie_consulting_fixed",
                "language": "zh-CN",
                "author": "AI Auto PPT",
                "version": "2.0",
            },
            "slides": [{"slide_id": "s-001", "layout": "title_only", "title": "项目背景"}],
        }
    )

    def _fake_review_once(*, deck_path, output_dir, model=None, theme_name=None):
        _ = (deck_path, model, theme_name)
        reviewed_deck_path = _write_review_once_outputs(
            output_dir,
            deck_title="项目背景",
            patch_payload={
                "patches": [
                    {
                        "page": 1,
                        "field": "slides[0].title",
                        "old_value": "项目背景",
                        "new_value": "项目建议",
                        "reason": "标题改成结论式表达",
                    }
                ]
            },
        )
        return type(
            "FakeReviewArtifacts",
            (),
            {
                "review_path": output_dir / "review_once.json",
                "patch_path": output_dir / "patches_review_once.json",
                "deck_path": reviewed_deck_path,
                "pptx_path": output_dir / "review_once.pptx",
                "preview_dir": output_dir / "previews_review_once",
            },
        )()

    monkeypatch.setattr("tools.sie_autoppt.batch.review_patch.review_once", _fake_review_once)

    result = run_batch_review_patch_once(
        workspace=workspace,
        bundle=_semantic_bundle(),
        model="test-model",
        theme_name="sie_consulting_fixed",
    )

    assert result["review_path"].endswith("review_once.json")
    assert result["patch_path"].endswith("patches_review_once.json")
    assert result["patched_deck_path"].endswith("patched.deck.json")
    assert (expected_review_dir / "review_once.json").exists()
    assert (expected_review_dir / "patches_review_once.json").exists()
    assert (expected_review_dir / "patched.deck.json").exists()


def test_run_batch_review_patch_once_raises_on_patch_conflict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    workspace = BatchWorkspace.create(root=tmp_path, run_id="run-review-002")

    def _fake_review_once(*, deck_path, output_dir, model=None, theme_name=None):
        _ = (deck_path, model, theme_name)
        reviewed_deck_path = _write_review_once_outputs(
            output_dir,
            deck_title="项目背景",
            patch_payload={
                "patches": [
                    {
                        "page": 1,
                        "field": "slides[0].title",
                        "old_value": "错误旧值",
                        "new_value": "项目建议",
                        "reason": "触发旧值冲突",
                    }
                ]
            },
        )
        return type(
            "FakeReviewArtifacts",
            (),
            {
                "review_path": output_dir / "review_once.json",
                "patch_path": output_dir / "patches_review_once.json",
                "deck_path": reviewed_deck_path,
                "pptx_path": output_dir / "review_once.pptx",
                "preview_dir": output_dir / "previews_review_once",
            },
        )()

    monkeypatch.setattr("tools.sie_autoppt.batch.review_patch.review_once", _fake_review_once)

    with pytest.raises(RuntimeError, match="old_value mismatch"):
        run_batch_review_patch_once(
            workspace=workspace,
            bundle=_semantic_bundle(),
            model="test-model",
            theme_name="sie_consulting_fixed",
        )
