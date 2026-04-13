from __future__ import annotations

from dataclasses import replace

from .clarifier_models import (
    CLARIFIER_PROMPT_PATH,
    DEFAULT_AUDIENCE_HINT,
    DEFAULT_V2_THEME,
    DIMENSION_ORDER,
    MAX_BODY_CHAPTERS,
    ClarifierRequirements,
    ClarifierResult,
    ClarifierSession,
    _normalize_dimension_names,
    _normalize_template_name,
    _normalize_text,
)
from .clarifier_parsing import (
    _build_pending_questions,
    _build_requirements_from_text,
    _build_response_template,
    _contains_skip_keyword,
    _extract_requirements_from_choice_answers,
    _format_known_requirements,
    _is_generic_topic,
)
from .llm_openai import (
    OpenAIConfigurationError,
    OpenAIResponsesClient,
    OpenAIResponsesError,
    load_openai_responses_config,
)
from .prompting import render_prompt_template

def _llm_extract_requirements(
    text: str,
    *,
    existing_requirements: ClarifierRequirements | None = None,
    model: str | None = None,
) -> ClarifierRequirements | None:
    known_requirements = existing_requirements or ClarifierRequirements()
    try:
        client = OpenAIResponsesClient(load_openai_responses_config(model=model))
    except OpenAIConfigurationError:
        return None

    developer_prompt = render_prompt_template(
        CLARIFIER_PROMPT_PATH,
        known_requirements=_format_known_requirements(known_requirements),
        pending_dimensions=", ".join(known_requirements.known_dimensions().keys()) or "all",
    )
    user_prompt = f"User request:\n{text.strip()}\n"
    schema = {
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "purpose": {"type": "string"},
            "audience": {"type": "string"},
            "style": {"type": "string"},
            "theme": {"type": "string"},
            "core_content": {"type": "string"},
            "chapters": {"type": ["integer", "null"], "minimum": 1, "maximum": MAX_BODY_CHAPTERS},
            "min_slides": {"type": ["integer", "null"], "minimum": 1, "maximum": MAX_BODY_CHAPTERS},
            "max_slides": {"type": ["integer", "null"], "minimum": 1, "maximum": MAX_BODY_CHAPTERS},
            "slide_hint": {"type": "string"},
            "should_skip": {"type": "boolean"},
        },
        "required": [
            "topic",
            "purpose",
            "audience",
            "style",
            "theme",
            "core_content",
            "chapters",
            "min_slides",
            "max_slides",
            "slide_hint",
            "should_skip",
        ],
        "additionalProperties": False,
    }
    try:
        payload = client.create_structured_json(
            developer_prompt=developer_prompt,
            user_prompt=user_prompt,
            schema_name="sie_autoppt_clarifier",
            schema=schema,
        )
    except OpenAIResponsesError:
        return None

    if bool(payload.get("should_skip")):
        return ClarifierRequirements(raw_request=text.strip())
    return ClarifierRequirements(
        topic=str(payload.get("topic", "")).strip(),
        purpose=str(payload.get("purpose", "")).strip(),
        audience=str(payload.get("audience", "")).strip(),
        style=str(payload.get("style", "")).strip(),
        theme=str(payload.get("theme", "")).strip(),
        core_content=str(payload.get("core_content", "")).strip(),
        chapters=payload.get("chapters"),
        min_slides=payload.get("min_slides"),
        max_slides=payload.get("max_slides"),
        slide_hint=str(payload.get("slide_hint", "")).strip(),
        raw_request=text.strip(),
    )


def _combine_requirements(
    base: ClarifierRequirements,
    extracted: ClarifierRequirements,
    llm_extracted: ClarifierRequirements | None = None,
) -> ClarifierRequirements:
    combined = base.merge(extracted)
    if llm_extracted is not None:
        combined = combined.merge(llm_extracted)
    combined = replace(combined, theme=DEFAULT_V2_THEME)
    return combined


def _missing_dimensions(requirements: ClarifierRequirements) -> tuple[str, ...]:
    known = requirements.known_dimensions()
    return tuple(dimension for dimension in DIMENSION_ORDER if dimension not in known)


def _is_ready(requirements: ClarifierRequirements, missing_dimensions: tuple[str, ...]) -> bool:
    known_count = len(requirements.known_dimensions())
    has_specific_topic = not _is_generic_topic(requirements.topic)
    required_dimensions = {"purpose", "audience", "slides", "style", "theme"}
    if not has_specific_topic:
        return False
    if any(dimension not in requirements.known_dimensions() for dimension in required_dimensions):
        return False
    if has_specific_topic and requirements.core_content and known_count >= 5:
        return True
    if has_specific_topic and known_count >= 5:
        return True
    return False


def _build_brief(requirements: ClarifierRequirements, original_brief: str = "") -> str:
    parts = []
    if original_brief.strip():
        parts.append(original_brief.strip())
    if requirements.purpose:
        parts.append(f"用途：{requirements.purpose}")
    if requirements.style:
        if requirements.theme:
            parts.append(f"Theme: {requirements.theme}")
        parts.append(f"风格：{requirements.style}")
    if requirements.core_content:
        parts.append(f"核心内容：{requirements.core_content}")
    if requirements.slide_summary():
        parts.append(f"页数偏好：{requirements.slide_summary()}")
    return "\n".join(part for part in parts if part)


def _requires_blocking_clarification(requirements: ClarifierRequirements, guide_mode: str) -> bool:
    if guide_mode != "full":
        return False
    known = requirements.known_dimensions()
    return "topic" not in known or len(known) <= 2


def _build_message(
    requirements: ClarifierRequirements,
    *,
    status: str,
    guide_mode: str,
    questions: tuple[ClarifierQuestion, ...],
    blocking: bool,
    response_template: str,
) -> str:
    summary = requirements.summary_lines()
    if status == "skipped":
        prefix = "已按你的要求跳过澄清，后续会基于当前已知信息直接进入规划。"
    elif status == "ready":
        prefix = "需求已经足够清楚，可以直接进入 AI 规划。"
    elif blocking:
        prefix = "当前指令还不够清楚，我会先阻塞生成流程。请先回答下面的问题后，我再继续生成。"
    elif guide_mode == "full":
        prefix = "我先帮你把需求补齐。下面这些维度里，当前已知信息还不够。"
    else:
        prefix = "我已经拿到一部分信息，还差下面这些维度补齐后会更稳。"

    sections = [prefix]
    if summary:
        sections.append("已识别信息：\n" + "\n".join(f"- {line}" for line in summary))
    if questions:
        question_lines = []
        for index, question in enumerate(questions, start=1):
            question_lines.append(f"{index}. {question.prompt}")
            for option in question.options:
                recommended_tag = "（推荐）" if option.recommended else ""
                description = f" - {option.description}" if option.description else ""
                question_lines.append(f"   {option.key}. {option.value}{recommended_tag}{description}")
            if question.allow_custom:
                question_lines.append("   其他：可直接自定义输入")
        sections.append("待补充：\n" + "\n".join(question_lines))
        if response_template:
            sections.append("推荐回复模板：\n" + response_template)
        if blocking:
            sections.append("回复“直接生成”可跳过，但默认不会继续往下规划。")
        else:
            sections.append("也可以直接回复“直接生成”，跳过继续追问。")
    return "\n\n".join(sections)


def clarify_user_input(
    user_input: str,
    *,
    session: ClarifierSession | None = None,
    original_brief: str = "",
    model: str | None = None,
    prefer_llm: bool = True,
) -> ClarifierResult:
    existing_session = session or ClarifierSession()
    raw_input = user_input.strip()
    normalized_input = _normalize_text(user_input)
    skip_requested = _contains_skip_keyword(normalized_input)
    current_pending_dimensions = _normalize_dimension_names(
        existing_session.pending_dimensions or _missing_dimensions(existing_session.requirements)
    )

    choice_requirements = _extract_requirements_from_choice_answers(
        raw_input,
        current_pending_dimensions,
        existing_session.requirements,
    )
    heuristic_requirements = _build_requirements_from_text(normalized_input)
    llm_requirements = None
    if prefer_llm and normalized_input and not skip_requested:
        llm_requirements = _llm_extract_requirements(
            normalized_input,
            existing_requirements=existing_session.requirements,
            model=model,
        )
    if "topic" not in current_pending_dimensions and not choice_requirements.topic:
        heuristic_requirements = replace(heuristic_requirements, topic="")
        if llm_requirements is not None:
            llm_requirements = replace(llm_requirements, topic="")

    combined_requirements = _combine_requirements(
        existing_session.requirements,
        heuristic_requirements.merge(choice_requirements),
        llm_requirements,
    )
    if not combined_requirements.raw_request:
        combined_requirements = combined_requirements.merge(ClarifierRequirements(raw_request=normalized_input))

    missing_dimensions = _missing_dimensions(combined_requirements)
    if skip_requested:
        status = "skipped"
        guide_mode = "none"
    elif _is_ready(combined_requirements, missing_dimensions):
        status = "ready"
        guide_mode = "none"
    elif len(combined_requirements.known_dimensions()) <= 1 and _is_generic_topic(combined_requirements.topic):
        status = "needs_clarification"
        guide_mode = "full"
    else:
        status = "needs_clarification"
        guide_mode = "partial"

    questions = () if status in {"ready", "skipped"} else _build_pending_questions(missing_dimensions, combined_requirements)
    blocking = status == "needs_clarification" and _requires_blocking_clarification(combined_requirements, guide_mode)
    response_template = "" if status in {"ready", "skipped"} else _build_response_template(questions)
    message = _build_message(
        combined_requirements,
        status=status,
        guide_mode=guide_mode,
        questions=questions,
        blocking=blocking,
        response_template=response_template,
    )

    merged_history = existing_session.history + ({"role": "user", "content": normalized_input},)
    clarified_session = ClarifierSession(
        requirements=combined_requirements,
        turn_count=existing_session.turn_count + 1,
        pending_dimensions=missing_dimensions,
        asked_dimensions=tuple(dict.fromkeys((*existing_session.asked_dimensions, *missing_dimensions))),
        skipped=skip_requested,
        status=status,
        history=merged_history,
    )

    audience = combined_requirements.audience or ""
    topic = combined_requirements.topic or normalized_input
    return ClarifierResult(
        session=clarified_session,
        requirements=combined_requirements,
        status=status,
        guide_mode=guide_mode,
        missing_dimensions=missing_dimensions,
        questions=questions,
        message=message,
        topic=topic,
        audience=audience,
        brief=_build_brief(combined_requirements, original_brief=original_brief),
        chapters=combined_requirements.chapters,
        min_slides=combined_requirements.min_slides,
        max_slides=combined_requirements.max_slides,
        blocking=blocking,
        response_template=response_template,
        skipped=skip_requested,
    )


def derive_planning_context(
    *,
    topic: str,
    brief: str = "",
    audience: str = "",
    template: str = "",
    theme: str = "",
    chapters: int | None = None,
    min_slides: int | None = None,
    max_slides: int | None = None,
    model: str | None = None,
    prefer_llm: bool = False,
) -> ClarifierResult:
    explicit_requirements = ClarifierRequirements(
        audience="" if audience.strip() == DEFAULT_AUDIENCE_HINT else audience.strip(),
        template=_normalize_template_name(template.strip()) if template.strip() else "",
        theme=DEFAULT_V2_THEME,
        core_content=brief.strip(),
        chapters=chapters,
        min_slides=min_slides,
        max_slides=max_slides,
        slide_hint=(
            f"{chapters}页"
            if chapters is not None
            else (
                f"{min_slides}-{max_slides}页"
                if min_slides is not None and max_slides is not None
                else ""
            )
        ),
    )
    seed_session = ClarifierSession(requirements=explicit_requirements)
    result = clarify_user_input(
        topic,
        session=seed_session,
        original_brief=brief,
        model=model,
        prefer_llm=prefer_llm,
    )
    merged_requirements = result.requirements.merge(explicit_requirements)
    missing_dimensions = _missing_dimensions(merged_requirements)
    if result.skipped:
        status = "skipped"
        guide_mode = "none"
    elif _is_ready(merged_requirements, missing_dimensions):
        status = "ready"
        guide_mode = "none"
    elif len(merged_requirements.known_dimensions()) <= 1 and _is_generic_topic(merged_requirements.topic):
        status = "needs_clarification"
        guide_mode = "full"
    else:
        status = "needs_clarification"
        guide_mode = "partial"

    questions = () if status in {"ready", "skipped"} else _build_pending_questions(missing_dimensions, merged_requirements)
    blocking = status == "needs_clarification" and _requires_blocking_clarification(merged_requirements, guide_mode)
    response_template = "" if status in {"ready", "skipped"} else _build_response_template(questions)
    message = _build_message(
        merged_requirements,
        status=status,
        guide_mode=guide_mode,
        questions=questions,
        blocking=blocking,
        response_template=response_template,
    )
    merged_session = ClarifierSession(
        requirements=merged_requirements,
        turn_count=result.session.turn_count,
        pending_dimensions=missing_dimensions,
        asked_dimensions=result.session.asked_dimensions,
        skipped=result.skipped,
        status=status,
        history=result.session.history,
    )
    return ClarifierResult(
        session=merged_session,
        requirements=merged_requirements,
        status=status,
        guide_mode=guide_mode,
        missing_dimensions=missing_dimensions,
        questions=questions,
        message=message,
        topic=merged_requirements.topic or topic.strip(),
        audience=merged_requirements.audience.strip(),
        brief=_build_brief(merged_requirements, original_brief=brief),
        chapters=merged_requirements.chapters,
        min_slides=merged_requirements.min_slides,
        max_slides=merged_requirements.max_slides,
        blocking=blocking,
        response_template=response_template,
        skipped=result.skipped,
    )
