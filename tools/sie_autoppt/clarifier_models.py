from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from .config import DEFAULT_TEMPLATE, MAX_BODY_CHAPTERS, TEMPLATES_DIR
from .llm_openai import (
    OpenAIConfigurationError,
    OpenAIResponsesClient,
    OpenAIResponsesError,
    load_openai_responses_config,
)
from .prompting import render_prompt_template


DEFAULT_AUDIENCE_HINT = "管理层 + 业务负责人"
CLARIFIER_PROMPT_PATH = "prompts/system/clarifier.md"
DIMENSION_ORDER = ("topic", "purpose", "audience", "slides", "style", "theme", "core_content")
DIMENSION_LABELS = {
    "theme": "Theme",
    "topic": "主题",
    "purpose": "用途",
    "audience": "受众",
    "slides": "页数",
    "style": "风格",
    "core_content": "核心内容",
}
DIMENSION_OPTIONS = {
    "topic": (),
    "purpose": ("工作汇报", "教学课件", "产品提案", "会议演讲"),
    "audience": ("公司领导", "客户", "同事", "学生", "通用"),
    "slides": ("3-5页", "10页左右", "20页以上"),
    "style": ("商务专业", "科技现代", "简约清晰", "活泼有趣"),
    "core_content": ("现状/问题/建议", "痛点/方案/价值", "进展/风险/下一步", "背景/目标/路径"),
}
DIMENSION_OPTION_DESCRIPTIONS = {
    "purpose": {
        "工作汇报": "强调进展、问题和决策建议，适合经营复盘或阶段汇报",
        "教学课件": "强调知识点结构和案例解释，适合培训或授课",
        "产品提案": "强调痛点、方案和收益，适合售前或对外沟通",
        "会议演讲": "强调观点表达和节奏，适合主题分享或发言",
    },
    "audience": {
        "公司领导": "结论先行，细节适中，突出关键决策信息",
        "客户": "强调价值、案例和差异化，减少内部术语",
        "同事": "可保留更多执行细节、分工和协同信息",
        "学生": "需要更多解释、示例和层层展开",
        "通用": "保持中性表达，适合未明确受众时的默认场景",
    },
    "slides": {
        "3-5页": "适合高层快报、过会材料或电梯汇报",
        "10页左右": "最常见的完整汇报长度，兼顾结论和支撑",
        "20页以上": "适合培训、详案或复杂方案说明",
    },
    "style": {
        "商务专业": "最稳妥，适合管理汇报和方案提报",
        "科技现代": "适合技术、产品、数字化主题",
        "简约清晰": "适合说明、教学、方法论表达",
        "活泼有趣": "适合培训、分享、传播型内容",
    },
    "core_content": {
        "现状/问题/建议": "适合经营复盘、管理汇报、问题诊断",
        "痛点/方案/价值": "适合客户提案、售前方案、价值说明",
        "进展/风险/下一步": "适合项目周报、阶段汇报、推进沟通",
        "背景/目标/路径": "适合主题分享、转型方案、方法论说明",
    },
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
DEFAULT_V2_THEME = "sie_consulting_fixed"
V2_THEMES_DIR = Path(__file__).resolve().parent / "v2" / "themes"
LEGACY_DIMENSION_ALIASES = {
    "template_theme": "theme",
}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_generic_topic(text: str) -> bool:
    if not text:
        return True
    normalized = _normalize_text(text).lower()
    return any(re.fullmatch(pattern, normalized, flags=re.IGNORECASE) for pattern in GENERIC_REQUEST_PATTERNS)


def _normalize_dimension_name(value: str) -> str:
    normalized = _normalize_text(str(value or ""))
    return LEGACY_DIMENSION_ALIASES.get(normalized, normalized)


def _normalize_dimension_names(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        resolved = _normalize_dimension_name(value)
        if resolved and resolved not in normalized:
            normalized.append(resolved)
    return tuple(normalized)


def _available_v2_themes() -> tuple[str, ...]:
    if not V2_THEMES_DIR.exists():
        return (DEFAULT_V2_THEME,)
    names = sorted(path.stem for path in V2_THEMES_DIR.glob("*.json"))
    if DEFAULT_V2_THEME in names:
        names.remove(DEFAULT_V2_THEME)
        names.insert(0, DEFAULT_V2_THEME)
    elif not names:
        names = [DEFAULT_V2_THEME]
    return tuple(names)


def _available_template_names() -> tuple[str, ...]:
    names: list[str] = []
    if DEFAULT_TEMPLATE.exists():
        names.append(DEFAULT_TEMPLATE.stem)
    if TEMPLATES_DIR.exists():
        for path in sorted(TEMPLATES_DIR.glob("*/template.pptx")):
            names.append(path.parent.name)
    unique: list[str] = []
    seen: set[str] = set()
    for name in names:
        normalized = str(name).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return tuple(unique)


def _normalize_template_name(value: str) -> str:
    normalized = _normalize_text(value).strip("\"'")
    if not normalized:
        return ""
    lowered = normalized.lower()
    if lowered.endswith(".pptx"):
        return Path(normalized).stem
    if lowered in {"default", "default template", "sietemplate", "sie template", "default_template"}:
        return DEFAULT_TEMPLATE.stem
    if lowered in {"默认模板", "默认", "sieppt", "sie模板"}:
        return DEFAULT_TEMPLATE.stem
    for name in _available_template_names():
        if lowered == name.lower():
            return name
    return normalized


def _extract_theme(text: str) -> str:
    normalized = _normalize_text(text)
    for theme_name in _available_v2_themes():
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(theme_name)}(?![A-Za-z0-9_])", normalized, flags=re.IGNORECASE):
            return theme_name
    return ""


def _extract_template(text: str) -> str:
    normalized = _normalize_text(text)
    for template_name in _available_template_names():
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(template_name)}(?![A-Za-z0-9_])", normalized, flags=re.IGNORECASE):
            return template_name

    if "模板" not in normalized and ".pptx" not in normalized.lower():
        return ""

    explicit_path = re.search(r"([^\s]+\.pptx)", normalized, flags=re.IGNORECASE)
    if explicit_path:
        return _normalize_template_name(explicit_path.group(1))
    return _normalize_template_name(normalized)


def _theme_summary(requirements: "ClarifierRequirements") -> str:
    if requirements.theme:
        return f"theme:{requirements.theme}"
    return ""


@dataclass(frozen=True)
class ClarifierOption:
    key: str
    value: str
    description: str = ""
    recommended: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "description": self.description,
            "recommended": self.recommended,
        }


@dataclass(frozen=True)
class ClarifierQuestion:
    dimension: str
    prompt: str
    options: tuple[ClarifierOption, ...] = ()
    allow_custom: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "label": DIMENSION_LABELS.get(self.dimension, self.dimension),
            "prompt": self.prompt,
            "options": [option.to_dict() for option in self.options],
            "option_labels": [option.value for option in self.options],
            "allow_custom": self.allow_custom,
        }


@dataclass(frozen=True)
class ClarifierRequirements:
    topic: str = ""
    purpose: str = ""
    audience: str = ""
    style: str = ""
    template: str = ""
    theme: str = ""
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
        if self.topic and not _is_generic_topic(self.topic):
            known["topic"] = self.topic
        if self.purpose:
            known["purpose"] = self.purpose
        if self.audience:
            known["audience"] = self.audience
        slide_summary = self.slide_summary()
        if slide_summary:
            known["slides"] = slide_summary
        if self.style:
            known["style"] = self.style
        theme = _theme_summary(self)
        if theme:
            known["theme"] = theme
        if self.core_content:
            known["core_content"] = self.core_content
        return known

    def merge(self, other: "ClarifierRequirements") -> "ClarifierRequirements":
        return ClarifierRequirements(
            topic=other.topic or self.topic,
            purpose=other.purpose or self.purpose,
            audience=other.audience or self.audience,
            style=other.style or self.style,
            template=other.template or self.template,
            theme=other.theme or self.theme,
            core_content=other.core_content or self.core_content,
            chapters=other.chapters if other.chapters is not None else self.chapters,
            min_slides=other.min_slides if other.min_slides is not None else self.min_slides,
            max_slides=other.max_slides if other.max_slides is not None else self.max_slides,
            slide_hint=other.slide_hint or self.slide_hint,
            raw_request=other.raw_request or self.raw_request,
        )

    def summary_lines(self) -> list[str]:
        lines = []
        if self.theme:
            lines.append(f"Theme: {self.theme}")
        if self.template:
            lines.append(f"Template: {self.template}")
        if self.topic and not _is_generic_topic(self.topic):
            lines.append(f"主题：{self.topic}")
        for dimension, value in self.known_dimensions().items():
            if dimension in {"topic", "theme"}:
                continue
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
    blocking: bool = False
    response_template: str = ""
    skipped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "guide_mode": self.guide_mode,
            "blocking": self.blocking,
            "skipped": self.skipped,
            "message": self.message,
            "response_template": self.response_template,
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
        pending_dimensions=_normalize_dimension_names(tuple(data.get("pending_dimensions", ()))),
        asked_dimensions=_normalize_dimension_names(tuple(data.get("asked_dimensions", ()))),
        skipped=bool(data.get("skipped", False)),
        status=str(data.get("status", "needs_clarification")),
        history=tuple(data.get("history", ())),
    )
