from unittest.mock import patch

from tools.sie_autoppt.v2.schema import OutlineDocument
from tools.sie_autoppt.v2.services import generate_compiled_v2_deck


def _outline() -> OutlineDocument:
    return OutlineDocument.model_validate(
        {
            "pages": [
                {"page_no": 1, "title": "Context", "goal": "Set context."},
                {"page_no": 2, "title": "Plan", "goal": "Present the roadmap."},
            ]
        }
    )


def _semantic_payload() -> dict:
    return {
        "meta": {
            "title": "AI strategy",
            "theme": "sie_consulting_fixed",
            "language": "zh-CN",
            "author": "AI",
            "version": "2.0",
        },
        "slides": [
            {
                "slide_id": "s1",
                "title": "Conclusion",
                "intent": "conclusion",
                "blocks": [{"kind": "statement", "text": "Focus on one chain first."}],
            }
        ],
    }


def test_generate_compiled_v2_deck_builds_outline_semantic_and_validated_deck():
    context = {"industry": "manufacturing", "decision_focus": "budget"}
    strategy = {"core_tension": "speed_vs_quality", "recommended_narrative_arc": "diagnose_then_scale"}
    outline = _outline()
    semantic_payload = _semantic_payload()

    with patch("tools.sie_autoppt.v2.services.ensure_generation_context", return_value=(context, strategy)), patch(
        "tools.sie_autoppt.v2.services.generate_outline_with_ai",
        return_value=outline,
    ) as outline_mock, patch(
        "tools.sie_autoppt.v2.services.generate_semantic_deck_with_ai",
        return_value=semantic_payload,
    ) as semantic_mock:
        result = generate_compiled_v2_deck(
            topic="AI strategy",
            brief="Executive summary",
            audience="Executive team",
            language="zh-CN",
            theme="sie_consulting_fixed",
            author="AI",
            model=None,
        )

    assert result.outline.to_list() == outline.to_list()
    assert result.semantic_payload["slides"][0]["slide_id"] == "s1"
    assert result.validated_deck.deck.slides[0].slide_id == "s1"
    outline_request = outline_mock.call_args.args[0]
    deck_request = semantic_mock.call_args.args[0]
    assert outline_request.structured_context == context
    assert outline_request.strategic_analysis == strategy
    assert deck_request.structured_context == context
    assert deck_request.strategic_analysis == strategy


def test_generate_compiled_v2_deck_reuses_provided_outline():
    outline = _outline()
    semantic_payload = _semantic_payload()

    with patch("tools.sie_autoppt.v2.services.ensure_generation_context", return_value=({}, {})), patch(
        "tools.sie_autoppt.v2.services.generate_outline_with_ai"
    ) as outline_mock, patch(
        "tools.sie_autoppt.v2.services.generate_semantic_deck_with_ai",
        return_value=semantic_payload,
    ) as semantic_mock:
        result = generate_compiled_v2_deck(
            topic="AI strategy",
            brief="Executive summary",
            audience="Executive team",
            language="zh-CN",
            theme="sie_consulting_fixed",
            author="AI",
            model=None,
            outline=outline,
        )

    assert result.outline.to_list() == outline.to_list()
    assert result.validated_deck.deck.meta.title == "AI strategy"
    outline_mock.assert_not_called()
    assert semantic_mock.call_args.args[0].outline.to_list() == outline.to_list()
