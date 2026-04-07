from __future__ import annotations

import datetime
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .content_service import build_deck_spec_from_structure
from .deck_spec_io import write_deck_spec
from .exceptions import AiHealthcheckBlockedError, AiHealthcheckFailedError, AiWorkflowError
from .generator import (
    generate_ppt_artifacts_from_deck_plan,
    generate_ppt_artifacts_from_deck_spec,
    generate_ppt_artifacts_from_html,
)
from .llm_openai import (
    OpenAIConfigurationError,
    OpenAIResponsesError,
    load_openai_responses_config,
)
from .models import DeckRenderTrace, GenerationArtifacts, StructureSpec
from .pipeline import build_deck_plan, plan_deck_from_html
from .planning.ai_planner import (
    AiPlanningRequest,
    ExternalPlannerError,
    plan_deck_spec_with_ai,
)
from .qa import write_qa_report
from .structure_service import (
    StructureGenerationRequest,
    generate_structure_with_ai,
)


@dataclass(frozen=True)
class RenderCommandResult:
    report_path: Path
    output_path: Path
    render_trace: DeckRenderTrace


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
    planner_command: str = ""

    def to_json(self) -> str:
        payload = {
            "status": self.status,
            "model": self.model,
            "base_url": self.base_url,
            "api_style": self.api_style,
            "topic": self.topic,
            "cover_title": self.cover_title,
            "page_count": self.page_count,
            "first_page_title": self.first_page_title,
        }
        if self.planner_command:
            payload["planner_command"] = self.planner_command
        return json.dumps(payload, ensure_ascii=False)


def build_plan_output_path(output_dir: Path, output_prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_prefix = re.sub(r'[<>:"/\\|?*]+', "_", output_prefix).strip(" ._") or "Enterprise-AI-PPT"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return output_dir / f"{safe_prefix}_{timestamp}.deck.json"


def build_structure_output_path(output_dir: Path, output_prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_prefix = re.sub(r'[<>:"/\\|?*]+', "_", output_prefix).strip(" ._") or "Enterprise-AI-PPT"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return output_dir / f"{safe_prefix}_{timestamp}.structure.json"


def generate_plan_from_html(
    html_path: Path,
    chapters: int | None,
    output_dir: Path,
    output_prefix: str,
    plan_output: Path | None = None,
) -> Path:
    deck_plan = plan_deck_from_html(html_path, chapters)
    final_output = plan_output or build_plan_output_path(output_dir, output_prefix)
    write_deck_spec(deck_plan.deck, final_output)
    return final_output


def generate_plan_with_ai(
    request: AiPlanningRequest,
    output_dir: Path,
    output_prefix: str,
    model: str | None = None,
    planner_command: str | None = None,
    plan_output: Path | None = None,
    template_path: Path | None = None,
) -> Path:
    try:
        deck = plan_deck_spec_with_ai(
            request,
            model=model,
            planner_command=planner_command,
            template_path=template_path,
        )
    except (OpenAIConfigurationError, OpenAIResponsesError, ExternalPlannerError, ValueError) as exc:
        raise AiWorkflowError(str(exc)) from exc

    final_output = plan_output or build_plan_output_path(output_dir, output_prefix)
    write_deck_spec(deck, final_output)
    return final_output


def generate_structure_only(
    request: StructureGenerationRequest,
    output_dir: Path,
    output_prefix: str,
    model: str | None = None,
    structure_output: Path | None = None,
) -> Path:
    try:
        result = generate_structure_with_ai(request, model=model)
    except (OpenAIConfigurationError, OpenAIResponsesError, ValueError) as exc:
        raise AiWorkflowError(str(exc)) from exc

    final_output = structure_output or build_structure_output_path(output_dir, output_prefix)
    final_output.parent.mkdir(parents=True, exist_ok=True)
    final_output.write_text(result.structure.to_json(), encoding="utf-8")
    return final_output


def load_structure_spec(structure_path: Path) -> StructureSpec:
    data = json.loads(structure_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Structure JSON must be an object.")
    return StructureSpec.from_dict(data)


def generate_plan_with_structure(
    request: StructureGenerationRequest | None,
    output_dir: Path,
    output_prefix: str,
    model: str | None = None,
    plan_output: Path | None = None,
    structure_output: Path | None = None,
    structure_path: Path | None = None,
) -> tuple[Path, Path | None]:
    if structure_path is not None:
        structure = load_structure_spec(structure_path)
        saved_structure_path = structure_path
    else:
        if request is None:
            raise ValueError("request is required when structure_path is not provided.")
        saved_structure_path = structure_output or build_structure_output_path(output_dir, output_prefix)
        saved_structure_path = generate_structure_only(
            request=request,
            output_dir=output_dir,
            output_prefix=output_prefix,
            model=model,
            structure_output=saved_structure_path,
        )
        structure = load_structure_spec(saved_structure_path)

    topic = request.topic if request is not None else structure.core_message
    deck = build_deck_spec_from_structure(structure, topic=topic)
    final_output = plan_output or build_plan_output_path(output_dir, output_prefix)
    write_deck_spec(deck, final_output)
    return final_output, saved_structure_path


def run_ai_healthcheck(
    request: AiPlanningRequest,
    model: str | None = None,
    planner_command: str | None = None,
    template_path: Path | None = None,
) -> AiCheckSummary:
    try:
        config = load_openai_responses_config(model=model) if not planner_command else None
        deck = plan_deck_spec_with_ai(
            request,
            model=model,
            planner_command=planner_command,
            template_path=template_path,
        )
    except OpenAIConfigurationError as exc:
        raise AiHealthcheckBlockedError(str(exc)) from exc
    except (OpenAIResponsesError, ExternalPlannerError, ValueError) as exc:
        raise AiHealthcheckFailedError(str(exc)) from exc

    return AiCheckSummary(
        status="ok",
        model=(config.model if config else "external-command"),
        base_url=(config.base_url if config else ""),
        api_style=(config.api_style if config else "external_command"),
        topic=request.topic,
        cover_title=deck.cover_title,
        page_count=len(deck.body_pages),
        first_page_title=deck.body_pages[0].title if deck.body_pages else "",
        planner_command=planner_command or "",
    )


def render_from_deck_spec(
    template_path: Path,
    deck_spec_path: Path,
    reference_body_path: Path | None,
    output_prefix: str,
    active_start: int,
    output_dir: Path,
) -> RenderCommandResult:
    artifacts = generate_ppt_artifacts_from_deck_spec(
        template_path=template_path,
        deck_spec_path=deck_spec_path,
        reference_body_path=reference_body_path,
        output_prefix=output_prefix,
        active_start=active_start,
        output_dir=output_dir,
    )
    return _finalize_render_result(artifacts, template_path)


def render_from_html(
    template_path: Path,
    html_path: Path,
    reference_body_path: Path | None,
    output_prefix: str,
    chapters: int | None,
    active_start: int,
    output_dir: Path,
) -> RenderCommandResult:
    artifacts = generate_ppt_artifacts_from_html(
        template_path=template_path,
        html_path=html_path,
        reference_body_path=reference_body_path,
        output_prefix=output_prefix,
        chapters=chapters,
        active_start=active_start,
        output_dir=output_dir,
    )
    return _finalize_render_result(artifacts, template_path)


def render_from_ai_plan(
    template_path: Path,
    request: AiPlanningRequest,
    reference_body_path: Path | None,
    output_prefix: str,
    active_start: int,
    output_dir: Path,
    model: str | None = None,
    planner_command: str | None = None,
    plan_output: Path | None = None,
) -> RenderCommandResult:
    try:
        deck = plan_deck_spec_with_ai(
            request,
            model=model,
            planner_command=planner_command,
            template_path=template_path,
        )
    except (OpenAIConfigurationError, OpenAIResponsesError, ExternalPlannerError, ValueError) as exc:
        raise AiWorkflowError(str(exc)) from exc

    if plan_output:
        write_deck_spec(deck, plan_output)

    artifacts = generate_ppt_artifacts_from_deck_plan(
        deck_plan=build_deck_plan(deck),
        input_kind="ai_topic",
        template_path=template_path,
        reference_body_path=reference_body_path,
        output_prefix=output_prefix,
        active_start=active_start,
        output_dir=output_dir,
    )
    return _finalize_render_result(artifacts, template_path)


def render_from_structure(
    template_path: Path,
    request: StructureGenerationRequest | None,
    reference_body_path: Path | None,
    output_prefix: str,
    active_start: int,
    output_dir: Path,
    model: str | None = None,
    plan_output: Path | None = None,
    structure_output: Path | None = None,
    structure_path: Path | None = None,
) -> RenderCommandResult:
    if structure_path is not None:
        structure = load_structure_spec(structure_path)
        saved_structure_path = structure_path
    else:
        if request is None:
            raise ValueError("request is required when structure_path is not provided.")
        saved_structure_path = structure_output or build_structure_output_path(output_dir, output_prefix)
        saved_structure_path = generate_structure_only(
            request=request,
            output_dir=output_dir,
            output_prefix=output_prefix,
            model=model,
            structure_output=saved_structure_path,
        )
        structure = load_structure_spec(saved_structure_path)

    topic = request.topic if request is not None else structure.core_message
    deck = build_deck_spec_from_structure(structure, topic=topic)

    if plan_output:
        write_deck_spec(deck, plan_output)

    artifacts = generate_ppt_artifacts_from_deck_plan(
        deck_plan=build_deck_plan(deck),
        input_kind="structure_json",
        template_path=template_path,
        reference_body_path=reference_body_path,
        output_prefix=output_prefix,
        active_start=active_start,
        output_dir=output_dir,
    )
    return _finalize_render_result(artifacts, template_path)


def _finalize_render_result(artifacts: GenerationArtifacts, template_path: Path) -> RenderCommandResult:
    report_path = write_qa_report(
        artifacts.output_path,
        len(artifacts.deck_plan.pattern_ids),
        pattern_ids=artifacts.deck_plan.pattern_ids,
        chapter_lines=artifacts.deck_plan.chapter_lines,
        template_path=template_path,
        render_trace=artifacts.render_trace,
    )
    return RenderCommandResult(
        report_path=report_path,
        output_path=artifacts.output_path,
        render_trace=artifacts.render_trace,
    )
