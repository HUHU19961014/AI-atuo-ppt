from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .config import MAX_BODY_CHAPTERS
from .llm_openai import (
    OpenAIConfigurationError,
    OpenAIResponsesClient,
    OpenAIResponsesError,
    load_openai_responses_config,
)
from .prompting import render_prompt_template


DEFAULT_AUDIENCE_HINT = "管理层 + 业务负责人"
CLARIFIER_PROMPT_PATH = "prompts/system/clarifier.md"
DIMENSION_ORDER = ("purpose", "audience", "slides", "style", "core_content")
DIMENSION_LABELS = {
    "purpose": "用途",
    "audience": "受众",
    "slides": "页数",
    "style": "风格",
    "core_content": "核心内容",
}
DIMENSION_OPTIONS = {
    "purpose": ("工作汇报", "教学课件", "产品提案", "会议演讲"),
    "audience": ("公司领导", "客户", "同事", "学生", "通用"),
    "slides": ("3-5页", "10页左右", "20页以上"),
    "style": ("商务专业", "科技现代", "简约清晰", "活泼有趣"),
    "core_content": (),
}
SKIP_KEYWORDS = (
    "直接生成",
    "直接开始",
    "跳过引导",
    "跳过澄清",
    "先生成",
    "skip",
)
GENERIC_REQUEST_PATTERNS = (
    r"^帮我(?:做|生成|写|整理)?(?:一份|一个|个)?ppt$",
    r"^做(?:一份|一个|个)?ppt$",
    r"^生成(?:一份|一个|个)?ppt$",
    r"^ppt$",
    r"^presentation$",
)
PURPOSE_PATTERNS = (
    (r"(工作汇报|业绩汇报|经营汇报|季度汇报|年度汇报|汇报)", "工作汇报"),
    (r"(教学课件|培训课件|培训材料|课程讲义|教学)", "教学课件"),
    (r"(产品提案|产品方案|提案|解决方案|方案汇报|招投标)", "产品提案"),
    (r"(会议演讲|主题演讲|分享会|路演|演讲)", "会议演讲"),
)
AUDIENCE_PATTERNS = (
    (r"(公司领导|管理层|老板|高层)", "公司领导"),
    (r"(客户|甲方|合作伙伴)", "客户"),
    (r"(同事|内部团队|项目组)", "同事"),
    (r"(学生|学员)", "学生"),
    (r"(通用|泛用|大众)", "通用"),
)
STYLE_PATTERNS = (
    (r"(商务专业|商务风|正式商务|高管汇报风)", "商务专业"),
    (r"(科技现代|科技风|未来感|科技感)", "科技现代"),
    (r"(简约清晰|极简|简洁|简约风)", "简约清晰"),
    (r"(活泼有趣|年轻化|轻松|趣味)", "活泼有趣"),
)
CONTENT_PATTERNS = (
    r"(?:核心内容|主要内容|重点|关键内容|内容重点)\s*(?:是|为|包括|围绕)?\s*[:：]?\s*(.+)$",
    r"(?:内容|包括|围绕|聚焦|重点讲|主要讲)\s*[:：]?\s*(.+)$",
)


@dataclass(frozen=True)
class ClarifierQuestion:
    dimension: str
    prompt: str
    options: tuple[str, ...] = ()
    allow_custom: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "label": DIMENSION_LABELS.get(self.dimension, self.dimension),
            "prompt": self.prompt,
            "options": list(self.options),
            "allow_custom": self.allow_custom,
        }


@dataclass(frozen=True)
class ClarifierRequirements:
    topic: str = ""
    purpose: str = ""
    audience: str = ""
    style: str = ""
    core_content: str = ""
    chapters: int | None = None
    min_slides: int | None = None
    max_slides: int | None = None
    slide_hint: str = ""
    raw_request: str = ""

    def slide_summary(self) -> str:
        if self.slide_hint:
            return self.slide_hint
        if self.chapters is not None:
            return f"{self.chapters}页"
        if self.min_slides is not None and self.max_slides is not None:
            return f"{self.min_slides}-{self.max_slides}页"
        if self.min_slides is not None:
            return f"{self.min_slides}页以上"
        return ""

    def known_dimensions(self) -> dict[str, str]:
        known: dict[str, str] = {}
        if self.purpose:
            known["purpose"] = self.purpose
        if self.audience:
            known["audience"] = self.audience
        slide_summary = self.slide_summary()
        if slide_summary:
            known["slides"] = slide_summary
        if self.style:
            known["style"] = self.style
        if self.core_content:
            known["core_content"] = self.core_content
        return known

    def merge(self, other: "ClarifierRequirements") -> "ClarifierRequirements":
        return ClarifierRequirements(
            topic=other.topic or self.topic,
            purpose=other.purpose or self.purpose,
            audience=other.audience or self.audience,
            style=other.style or self.style,
            core_content=other.core_content or self.core_content,
            chapters=other.chapters if other.chapters is not None else self.chapters,
            min_slides=other.min_slides if other.min_slides is not None else self.min_slides,
            max_slides=other.max_slides if other.max_slides is not None else self.max_slides,
            slide_hint=other.slide_hint or self.slide_hint,
            raw_request=other.raw_request or self.raw_request,
        )

    def summary_lines(self) -> list[str]:
        lines = []
        if self.topic:
            lines.append(f"主题：{self.topic}")
        for dimension, value in self.known_dimensions().items():
            lines.append(f"{DIMENSION_LABELS[dimension]}：{value}")
        return lines


@dataclass(frozen=True)
class ClarifierSession:
    requirements: ClarifierRequirements = field(default_factory=ClarifierRequirements)
    turn_count: int = 0
    pending_dimensions: tuple[str, ...] = ()
    asked_dimensions: tuple[str, ...] = ()
    skipped: bool = False
    status: str = "needs_clarification"
    history: tuple[dict[str, str], ...] = ()

    def to_json(self) -> str:
        payload = {
            "requirements": asdict(self.requirements),
            "turn_count": self.turn_count,
            "pending_dimensions": list(self.pending_dimensions),
            "asked_dimensions": list(self.asked_dimensions),
            "skipped": self.skipped,
            "status": self.status,
            "history": list(self.history),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)


@dataclass(frozen=True)
class ClarifierResult:
    session: ClarifierSession
    requirements: ClarifierRequirements
    status: str
    guide_mode: str
    missing_dimensions: tuple[str, ...]
    questions: tuple[ClarifierQuestion, ...]
    message: str
    topic: str
    audience: str
    brief: str
    chapters: int | None
    min_slides: int | None
    max_slides: int | None
    skipped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "guide_mode": self.guide_mode,
            "skipped": self.skipped,
            "message": self.message,
            "topic": self.topic,
            "audience": self.audience,
            "brief": self.brief,
            "chapters": self.chapters,
            "min_slides": self.min_slides,
            "max_slides": self.max_slides,
            "missing_dimensions": list(self.missing_dimensions),
            "requirements": asdict(self.requirements),
            "questions": [question.to_dict() for question in self.questions],
            "session": json.loads(self.session.to_json()),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def load_clarifier_session(payload: str) -> ClarifierSession:
    data = json.loads(payload)
    requirements = ClarifierRequirements(**data.get("requirements", {}))
    return ClarifierSession(
        requirements=requirements,
        turn_count=int(data.get("turn_count", 0)),
        pending_dimensions=tuple(data.get("pending_dimensions", ())),
        asked_dimensions=tuple(data.get("asked_dimensions", ())),
        skipped=bool(data.get("skipped", False)),
        status=str(data.get("status", "needs_clarification")),
        history=tuple(data.get("history", ())),
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


def _build_pending_questions(missing_dimensions: tuple[str, ...]) -> tuple[ClarifierQuestion, ...]:
    prompts = {
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
                options=tuple(DIMENSION_OPTIONS[dimension]),
            )
        )
    return tuple(questions)


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
    return combined


def _missing_dimensions(requirements: ClarifierRequirements) -> tuple[str, ...]:
    known = requirements.known_dimensions()
    return tuple(dimension for dimension in DIMENSION_ORDER if dimension not in known)


def _is_ready(requirements: ClarifierRequirements, missing_dimensions: tuple[str, ...]) -> bool:
    known_count = len(requirements.known_dimensions())
    has_specific_topic = not _is_generic_topic(requirements.topic)
    if requirements.core_content and known_count >= 3:
        return True
    if has_specific_topic and known_count >= 3:
        return True
    return False


def _build_brief(requirements: ClarifierRequirements, original_brief: str = "") -> str:
    parts = []
    if original_brief.strip():
        parts.append(original_brief.strip())
    if requirements.purpose:
        parts.append(f"用途：{requirements.purpose}")
    if requirements.style:
        parts.append(f"风格：{requirements.style}")
    if requirements.core_content:
        parts.append(f"核心内容：{requirements.core_content}")
    if requirements.slide_summary():
        parts.append(f"页数偏好：{requirements.slide_summary()}")
    return "\n".join(part for part in parts if part)


def _build_message(
    requirements: ClarifierRequirements,
    *,
    status: str,
    guide_mode: str,
    questions: tuple[ClarifierQuestion, ...],
) -> str:
    summary = requirements.summary_lines()
    if status == "skipped":
        prefix = "已按你的要求跳过澄清，后续会基于当前已知信息直接进入规划。"
    elif status == "ready":
        prefix = "需求已经足够清楚，可以直接进入 AI 规划。"
    elif guide_mode == "full":
        prefix = "我先帮你把需求补齐。下面 5 个维度里，当前已知信息比较少。"
    else:
        prefix = "我已经拿到一部分信息，还差下面这些维度补齐后会更稳。"

    sections = [prefix]
    if summary:
        sections.append("已识别信息：\n" + "\n".join(f"- {line}" for line in summary))
    if questions:
        question_lines = []
        for index, question in enumerate(questions, start=1):
            option_text = " / ".join(question.options) if question.options else "可自由输入"
            question_lines.append(f"{index}. {question.prompt} ({option_text} / 其他)")
        sections.append("待补充：\n" + "\n".join(question_lines))
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
    normalized_input = _normalize_text(user_input)
    skip_requested = _contains_skip_keyword(normalized_input)

    heuristic_requirements = _build_requirements_from_text(normalized_input)
    llm_requirements = None
    if prefer_llm and normalized_input and not skip_requested:
        llm_requirements = _llm_extract_requirements(
            normalized_input,
            existing_requirements=existing_session.requirements,
            model=model,
        )

    combined_requirements = _combine_requirements(
        existing_session.requirements,
        heuristic_requirements,
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

    questions = () if status in {"ready", "skipped"} else _build_pending_questions(missing_dimensions)
    message = _build_message(combined_requirements, status=status, guide_mode=guide_mode, questions=questions)

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
        skipped=skip_requested,
    )


def derive_planning_context(
    *,
    topic: str,
    brief: str = "",
    audience: str = "",
    chapters: int | None = None,
    min_slides: int | None = None,
    max_slides: int | None = None,
    model: str | None = None,
    prefer_llm: bool = False,
) -> ClarifierResult:
    explicit_requirements = ClarifierRequirements(
        audience="" if audience.strip() == DEFAULT_AUDIENCE_HINT else audience.strip(),
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

    questions = () if status in {"ready", "skipped"} else _build_pending_questions(missing_dimensions)
    message = _build_message(merged_requirements, status=status, guide_mode=guide_mode, questions=questions)
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
        skipped=result.skipped,
    )
