from __future__ import annotations

import re

from .clarifier_models import (
    AUDIENCE_PATTERNS,
    CONTENT_PATTERNS,
    DEFAULT_V2_THEME,
    DIMENSION_LABELS,
    DIMENSION_OPTIONS,
    DIMENSION_OPTION_DESCRIPTIONS,
    GENERIC_REQUEST_PATTERNS,
    MAX_BODY_CHAPTERS,
    PURPOSE_PATTERNS,
    SKIP_KEYWORDS,
    STYLE_PATTERNS,
    ClarifierOption,
    ClarifierQuestion,
    ClarifierRequirements,
    _available_v2_themes,
    _extract_theme,
)

def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _contains_skip_keyword(text: str) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in SKIP_KEYWORDS)


def _extract_by_patterns(text: str, patterns: tuple[tuple[str, str], ...]) -> str:
    for pattern, normalized in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return normalized
    return ""


def _extract_slide_preferences(text: str) -> tuple[int | None, int | None, int | None, str]:
    range_match = re.search(r"(\d+)\s*[-~到至]\s*(\d+)\s*页", text, flags=re.IGNORECASE)
    if range_match:
        min_slides = max(1, int(range_match.group(1)))
        max_slides = max(min_slides, min(int(range_match.group(2)), MAX_BODY_CHAPTERS))
        return None, min_slides, max_slides, f"{min_slides}-{max_slides}页"

    more_match = re.search(r"(\d+)\s*页\s*(?:以上|起)", text, flags=re.IGNORECASE)
    if more_match:
        lower_bound = max(1, int(more_match.group(1)))
        lower_bound = min(lower_bound, MAX_BODY_CHAPTERS)
        return None, lower_bound, MAX_BODY_CHAPTERS, f"{lower_bound}页以上"

    approx_match = re.search(r"(\d+)\s*页\s*(?:左右|上下|以内)", text, flags=re.IGNORECASE)
    if approx_match:
        chapters = max(1, min(int(approx_match.group(1)), MAX_BODY_CHAPTERS))
        return chapters, None, None, f"{chapters}页左右"

    exact_match = re.search(r"(\d+)\s*页", text, flags=re.IGNORECASE)
    if exact_match:
        chapters = max(1, min(int(exact_match.group(1)), MAX_BODY_CHAPTERS))
        return chapters, None, None, f"{chapters}页"

    return None, None, None, ""


def _extract_core_content(text: str) -> str:
    normalized = _normalize_text(text)
    for pattern in CONTENT_PATTERNS:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            candidate = match.group(1).strip(" ：:，,。.；;")
            if candidate:
                return candidate

    if re.search(r"[、,，/]", normalized) and len(normalized) >= 16:
        fragments = [fragment.strip() for fragment in re.split(r"[。；;]", normalized) if fragment.strip()]
        if fragments:
            candidate = fragments[-1]
            if len(candidate) >= 8:
                return candidate
    return ""


def _strip_metadata_from_topic(text: str) -> str:
    candidate = text
    candidate = re.sub(r"给[^，。；;,:：]{1,12}(?:看|汇报|展示)", " ", candidate)
    candidate = re.sub(r"(面向|针对)[^，。；;,:：]{1,12}", " ", candidate)
    candidate = re.sub(r"\d+\s*[-~到至]\s*\d+\s*页", " ", candidate)
    candidate = re.sub(r"\d+\s*页\s*(?:左右|上下|以内|以上|起)?", " ", candidate)
    candidate = re.sub(r"(商务专业|科技现代|简约清晰|活泼有趣|商务风|科技风|简约风)\s*风格?", " ", candidate)
    candidate = re.sub(r"\b风格\b", " ", candidate)
    candidate = re.sub(r"(帮我|请|麻烦|想要|需要)(?:做|生成|写|整理)?", " ", candidate)
    candidate = re.sub(r"(一份|一个|个)", " ", candidate)
    candidate = re.sub(r"\bPPT\b", " ", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"(内容|重点|包括|围绕|聚焦).*$", " ", candidate)
    candidate = re.sub(r"[，,。；;：:]", " ", candidate)
    return _normalize_text(candidate)


def _is_generic_topic(text: str) -> bool:
    if not text:
        return True
    normalized = _normalize_text(text).lower()
    return any(re.fullmatch(pattern, normalized, flags=re.IGNORECASE) for pattern in GENERIC_REQUEST_PATTERNS)


def _extract_topic(text: str) -> str:
    candidate = _strip_metadata_from_topic(text)
    if _is_generic_topic(candidate):
        return ""
    return candidate[:60]


def _build_requirements_from_text(text: str) -> ClarifierRequirements:
    normalized = _normalize_text(text)
    chapters, min_slides, max_slides, slide_hint = _extract_slide_preferences(normalized)
    return ClarifierRequirements(
        topic=_extract_topic(normalized),
        purpose=_extract_by_patterns(normalized, PURPOSE_PATTERNS),
        audience=_extract_by_patterns(normalized, AUDIENCE_PATTERNS),
        style=_extract_by_patterns(normalized, STYLE_PATTERNS),
        theme=_extract_theme(normalized),
        core_content=_extract_core_content(normalized),
        chapters=chapters,
        min_slides=min_slides,
        max_slides=max_slides,
        slide_hint=slide_hint,
        raw_request=normalized,
    )


def _format_known_requirements(requirements: ClarifierRequirements) -> str:
    lines = requirements.summary_lines()
    return "\n".join(f"- {line}" for line in lines) if lines else "- none"


def _choice_key(index: int) -> str:
    return chr(ord("A") + index)


def _recommended_option_for_dimension(dimension: str, requirements: ClarifierRequirements) -> str:
    if dimension == "purpose":
        if requirements.purpose:
            return requirements.purpose
        normalized = requirements.raw_request
        if "方案" in normalized or "提案" in normalized:
            return "产品提案"
        if "课件" in normalized or "培训" in normalized:
            return "教学课件"
        if "演讲" in normalized or "路演" in normalized:
            return "会议演讲"
        return "工作汇报"
    if dimension == "audience":
        if requirements.audience:
            return requirements.audience
        if requirements.purpose == "教学课件":
            return "学生"
        if requirements.purpose == "产品提案":
            return "客户"
        if requirements.purpose == "会议演讲":
            return "通用"
        return "公司领导"
    if dimension == "slides":
        return requirements.slide_summary() or "10页左右"
    if dimension == "style":
        if requirements.style:
            return requirements.style
        if requirements.purpose == "教学课件":
            return "简约清晰"
        if requirements.purpose == "会议演讲":
            return "科技现代"
        return "商务专业"
    if dimension == "theme":
        if requirements.theme:
            return f"theme:{requirements.theme}"
        return f"theme:{DEFAULT_V2_THEME}"
    if dimension == "core_content":
        if requirements.core_content:
            return requirements.core_content
        if requirements.purpose == "产品提案":
            return "痛点/方案/价值"
        if requirements.purpose == "会议演讲":
            return "背景/目标/路径"
        return "进展/风险/下一步"
    return ""


def _build_options_for_dimension(dimension: str, requirements: ClarifierRequirements) -> tuple[ClarifierOption, ...]:
    if dimension == "theme":
        recommended_value = _recommended_option_for_dimension(dimension, requirements)
        options: list[ClarifierOption] = []
        for index, theme_name in enumerate(_available_v2_themes()):
            value = f"theme:{theme_name}"
            description = "V2 semantic theme" if theme_name != DEFAULT_V2_THEME else "V2 semantic theme (default)"
            options.append(
                ClarifierOption(
                    key=_choice_key(index),
                    value=value,
                    description=description,
                    recommended=value == recommended_value,
                )
            )
        if options and not any(option.recommended for option in options):
            first = options[0]
            options[0] = ClarifierOption(
                key=first.key,
                value=first.value,
                description=first.description,
                recommended=True,
            )
        return tuple(options)

    values = DIMENSION_OPTIONS.get(dimension, ())
    descriptions = DIMENSION_OPTION_DESCRIPTIONS.get(dimension, {})
    recommended_value = _recommended_option_for_dimension(dimension, requirements)
    resolved_options = tuple(
        ClarifierOption(
            key=_choice_key(index),
            value=value,
            description=descriptions.get(value, ""),
            recommended=value == recommended_value,
        )
        for index, value in enumerate(values)
    )
    if resolved_options and not any(option.recommended for option in resolved_options):
        first = resolved_options[0]
        return (
            ClarifierOption(
                key=first.key,
                value=first.value,
                description=first.description,
                recommended=True,
            ),
            *resolved_options[1:],
        )
    return resolved_options


def _build_pending_questions(
    missing_dimensions: tuple[str, ...],
    requirements: ClarifierRequirements,
) -> tuple[ClarifierQuestion, ...]:
    prompts = {
        "theme": "请选择主题风格（V2 theme）。",
        "topic": "这份 PPT 的主题是什么？请尽量用一句话说清楚。",
        "purpose": "这份 PPT 主要用于什么场景？",
        "audience": "这份 PPT 主要给谁看？",
        "slides": "你希望大概做多少页？",
        "style": "你想要什么风格？",
        "core_content": "这次最想重点讲哪些内容？",
    }
    questions = []
    for dimension in missing_dimensions:
        questions.append(
            ClarifierQuestion(
                dimension=dimension,
                prompt=prompts[dimension],
                options=_build_options_for_dimension(dimension, requirements),
            )
        )
    return tuple(questions)


def _apply_dimension_answer(dimension: str, raw_value: str) -> ClarifierRequirements:
    value = _normalize_text(raw_value)
    if not value:
        return ClarifierRequirements()
    if dimension == "topic":
        return ClarifierRequirements(topic=value)
    if dimension == "purpose":
        return ClarifierRequirements(purpose=value)
    if dimension == "audience":
        return ClarifierRequirements(audience=value)
    if dimension == "style":
        return ClarifierRequirements(style=value)
    if dimension == "theme":
        if value.lower().startswith("theme:"):
            return ClarifierRequirements(theme=value.split(":", 1)[1].strip())
        detected_theme = _extract_theme(value)
        if detected_theme:
            return ClarifierRequirements(theme=detected_theme)
        return ClarifierRequirements(theme=value)
    if dimension == "core_content":
        return ClarifierRequirements(core_content=value)
    if dimension == "slides":
        chapters, min_slides, max_slides, slide_hint = _extract_slide_preferences(value)
        return ClarifierRequirements(
            chapters=chapters,
            min_slides=min_slides,
            max_slides=max_slides,
            slide_hint=slide_hint,
        )
    return ClarifierRequirements()


def _extract_requirements_from_choice_answers(
    text: str,
    pending_dimensions: tuple[str, ...],
    base_requirements: ClarifierRequirements,
) -> ClarifierRequirements:
    if not pending_dimensions:
        return ClarifierRequirements()
    questions = _build_pending_questions(pending_dimensions, base_requirements)
    extracted = ClarifierRequirements()
    for index, question in enumerate(questions, start=1):
        matched = False
        if question.options:
            option_map = {option.key.upper(): option.value for option in question.options}
            patterns = (
                rf"(?:^|[\s,，;；]){index}\s*[:：=．.、-]?\s*([A-Z])\b",
                rf"(?:^|[\s,，;；]){question.dimension}\s*[:：=]?\s*([A-Z])\b",
            )
            for pattern in patterns:
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match:
                    option_key = match.group(1).upper()
                    if option_key in option_map:
                        extracted = extracted.merge(_apply_dimension_answer(question.dimension, option_map[option_key]))
                        matched = True
                        break
        if matched:
            continue
        if question.allow_custom:
            patterns = (
                rf"(?:^|[\n\r]){index}\s*[:：=．.、-]\s*(.+)",
                rf"(?:^|[\n\r]){question.dimension}\s*[:：=]\s*(.+)",
            )
            for pattern in patterns:
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match:
                    value = _normalize_text(match.group(1))
                    if value:
                        extracted = extracted.merge(_apply_dimension_answer(question.dimension, value))
                        break
    return extracted


def _build_response_template(questions: tuple[ClarifierQuestion, ...]) -> str:
    lines = []
    for index, question in enumerate(questions, start=1):
        recommended_option = next((option for option in question.options if option.recommended), None)
        if recommended_option is not None:
            lines.append(f"{index}{recommended_option.key}")
        else:
            lines.append(f"{index}. {DIMENSION_LABELS.get(question.dimension, question.dimension)}：")
    return "\n".join(lines)
