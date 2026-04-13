from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .clarifier import DEFAULT_AUDIENCE_HINT
from .exceptions import AiHealthcheckBlockedError, AiHealthcheckFailedError
from .llm_openai import OpenAIConfigurationError, OpenAIResponsesError, load_openai_responses_config
from .v2.services import DeckGenerationRequest, OutlineGenerationRequest, generate_deck_with_ai, generate_outline_with_ai, make_v2_ppt


@dataclass(frozen=True)
class AiCheckSummary:
    status: str
    model: str
    base_url: str
    api_style: str
    topic: str
    cover_title: str
    page_count: int
    first_page_title: str
    render_checked: bool = False
    pptx_path: str = ""
    warning_count: int = 0
    high_count: int = 0
    error_count: int = 0
    review_required: bool = False
    auto_score: int = 0
    auto_level: str = ""

    def to_json(self) -> str:
        return json.dumps(
            {
                "status": self.status,
                "model": self.model,
                "base_url": self.base_url,
                "api_style": self.api_style,
                "topic": self.topic,
                "cover_title": self.cover_title,
                "page_count": self.page_count,
                "first_page_title": self.first_page_title,
                "render_checked": self.render_checked,
                "pptx_path": self.pptx_path,
                "warning_count": self.warning_count,
                "high_count": self.high_count,
                "error_count": self.error_count,
                "review_required": self.review_required,
                "auto_score": self.auto_score,
                "auto_level": self.auto_level,
            },
            ensure_ascii=False,
        )


def run_ai_healthcheck(
    *,
    topic: str,
    brief: str = "",
    audience: str = DEFAULT_AUDIENCE_HINT,
    language: str = "zh-CN",
    theme: str = "sie_consulting_fixed",
    generation_mode: str = "deep",
    model: str | None = None,
    with_render: bool = False,
    output_dir: Path | None = None,
) -> AiCheckSummary:
    try:
        config = load_openai_responses_config(model=model)
        render_summary: dict[str, object] = {}
        if with_render:
            artifacts = make_v2_ppt(
                topic=topic,
                brief=brief,
                audience=audience,
                language=language,
                theme=theme,
                exact_slides=3,
                min_slides=3,
                max_slides=3,
                output_dir=output_dir,
                output_prefix="ai_healthcheck",
                model=model,
                generation_mode=generation_mode,
            )
            deck = artifacts.deck
            warnings_payload = json.loads(artifacts.warnings_path.read_text(encoding="utf-8")) if artifacts.warnings_path.exists() else {}
            summary = warnings_payload.get("summary", {})
            render_summary = {
                "render_checked": True,
                "pptx_path": str(artifacts.pptx_path),
                "warning_count": int(summary.get("warning_count", 0)),
                "high_count": int(summary.get("high_count", 0)),
                "error_count": int(summary.get("error_count", 0)),
                "review_required": bool(warnings_payload.get("review_required", False)),
                "auto_score": int(warnings_payload.get("auto_score", 0)),
                "auto_level": str(warnings_payload.get("auto_level", "")),
            }
        else:
            outline = generate_outline_with_ai(
                OutlineGenerationRequest(
                    topic=topic,
                    brief=brief,
                    audience=audience,
                    language=language,
                    theme=theme,
                    exact_slides=3,
                    generation_mode=generation_mode,
                ),
                model=model,
            )
            deck = generate_deck_with_ai(
                DeckGenerationRequest(
                    topic=topic,
                    outline=outline,
                    brief=brief,
                    audience=audience,
                    language=language,
                    theme=theme,
                    generation_mode=generation_mode,
                ),
                model=model,
            ).deck
    except OpenAIConfigurationError as exc:
        raise AiHealthcheckBlockedError(str(exc)) from exc
    except (OpenAIResponsesError, ValueError) as exc:
        raise AiHealthcheckFailedError(str(exc)) from exc

    return AiCheckSummary(
        status="ok",
        model=config.model,
        base_url=config.base_url,
        api_style=config.api_style,
        topic=topic,
        cover_title=deck.meta.title,
        page_count=len(deck.slides),
        first_page_title=deck.slides[0].title if deck.slides else "",
        render_checked=bool(render_summary.get("render_checked", False)),
        pptx_path=str(render_summary.get("pptx_path", "")),
        warning_count=int(render_summary.get("warning_count", 0)),
        high_count=int(render_summary.get("high_count", 0)),
        error_count=int(render_summary.get("error_count", 0)),
        review_required=bool(render_summary.get("review_required", False)),
        auto_score=int(render_summary.get("auto_score", 0)),
        auto_level=str(render_summary.get("auto_level", "")),
    )
