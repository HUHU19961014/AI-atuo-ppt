import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any

from ..config import DEFAULT_AI_SOURCE_CHAR_LIMIT, MAX_BODY_CHAPTERS
from ..deck_spec_io import deck_spec_from_dict
from ..llm_openai import OpenAIResponsesClient, load_openai_responses_config
from ..models import BodyPageSpec, DeckSpec
from ..patterns import infer_pattern
from .deck_planner import compact_text, shorten_for_nav


SUPPORTED_AI_PATTERNS = (
    "general_business",
    "solution_architecture",
    "process_flow",
    "org_governance",
)

PATTERN_COMPATIBILITY_MAP = {
    "policy_timeline": "general_business",
    "pain_points": "general_business",
    "value_benefit": "general_business",
    "solution_architecture": "solution_architecture",
    "process_flow": "process_flow",
    "org_governance": "org_governance",
    "implementation_plan": "process_flow",
    "capability_matrix": "general_business",
    "case_proof": "general_business",
    "action_next_steps": "general_business",
}

EXTERNAL_PLANNER_COMMAND_ENV = "SIE_AUTOPPT_EXTERNAL_PLANNER_CMD"


class ExternalPlannerError(RuntimeError):
    pass


@dataclass(frozen=True)
class AiPlanningRequest:
    topic: str
    chapters: int | None = None
    min_slides: int | None = None
    max_slides: int | None = None
    audience: str = "管理层 + 业务负责人"
    brief: str = ""
    language: str = "zh-CN"


@dataclass(frozen=True)
class AiSlideBounds:
    min_slides: int
    max_slides: int

    @property
    def is_exact(self) -> bool:
        return self.min_slides == self.max_slides


def clamp_ai_slide_limit(value: int) -> int:
    return max(1, min(int(value), MAX_BODY_CHAPTERS))


def infer_slide_range_from_content(topic: str, brief: str) -> tuple[int, int]:
    content = re.sub(r"\s+", "", f"{topic}\n{brief}")
    content_length = len(content)
    if content_length <= 500:
        return 3, 5
    if content_length <= 2000:
        return 6, 10
    return 10, MAX_BODY_CHAPTERS


def resolve_ai_slide_bounds(request: AiPlanningRequest) -> AiSlideBounds:
    exact_slides = request.chapters if request.chapters and request.chapters > 0 else None
    min_slides = request.min_slides if request.min_slides and request.min_slides > 0 else None
    max_slides = request.max_slides if request.max_slides and request.max_slides > 0 else None

    if exact_slides is not None and (min_slides is not None or max_slides is not None):
        raise ValueError("Use either an exact chapter count or a min/max slide range, not both.")

    if exact_slides is not None:
        exact_slides = clamp_ai_slide_limit(exact_slides)
        return AiSlideBounds(min_slides=exact_slides, max_slides=exact_slides)

    inferred_min, inferred_max = infer_slide_range_from_content(request.topic, request.brief)
    resolved_min = clamp_ai_slide_limit(min_slides if min_slides is not None else inferred_min)
    resolved_max = clamp_ai_slide_limit(max_slides if max_slides is not None else inferred_max)
    if resolved_min > resolved_max:
        raise ValueError(f"Invalid AI slide range: min_slides={resolved_min} is greater than max_slides={resolved_max}.")
    return AiSlideBounds(min_slides=resolved_min, max_slides=resolved_max)


def build_ai_outline_schema(slide_bounds: AiSlideBounds) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "cover_title": {
                "type": "string",
                "minLength": 1,
                "maxLength": 40,
            },
            "body_pages": {
                "type": "array",
                "minItems": slide_bounds.min_slides,
                "maxItems": slide_bounds.max_slides,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "minLength": 1, "maxLength": 30},
                        "subtitle": {"type": "string", "maxLength": 60},
                        "bullets": {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 4,
                            "items": {"type": "string", "minLength": 4, "maxLength": 80},
                        },
                        "pattern_id": {
                            "type": "string",
                            "enum": list(PATTERN_COMPATIBILITY_MAP.keys()),
                        },
                        "nav_title": {"type": "string", "maxLength": 10},
                    },
                    "required": ["title", "subtitle", "bullets", "pattern_id", "nav_title"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["cover_title", "body_pages"],
        "additionalProperties": False,
    }


def build_ai_planning_prompts(request: AiPlanningRequest, slide_bounds: AiSlideBounds | None = None) -> tuple[str, str]:
    slide_bounds = slide_bounds or resolve_ai_slide_bounds(request)
    if slide_bounds.is_exact:
        slide_count_rule = f"Return exactly {slide_bounds.min_slides} body pages."
        slide_count_request = str(slide_bounds.min_slides)
        slide_count_output_rule = f"- Produce a cover title plus exactly {slide_bounds.min_slides} body pages."
    else:
        slide_count_rule = (
            f"Return between {slide_bounds.min_slides} and {slide_bounds.max_slides} body pages "
            "based on content density and storyline clarity."
        )
        slide_count_request = f"{slide_bounds.min_slides}-{slide_bounds.max_slides}"
        slide_count_output_rule = (
            f"- Produce a cover title plus {slide_bounds.min_slides}-{slide_bounds.max_slides} body pages.\n"
            "- Choose the actual page count based on content density rather than padding or over-compressing the deck."
        )

    developer_prompt = f"""
You are planning a business PPT outline for an enterprise template-driven renderer.

Your job is to output only structured content decisions. Do not output coordinates, PowerPoint APIs, design instructions, or prose outside the JSON schema.

Hard rules:
- {slide_count_rule}
- Each page must use one pattern_id from the provided enum.
- Prefer these stable patterns when possible:
  - general_business: summary, value points, pain points, key takeaways
  - solution_architecture: layered architecture, capability stack, system landscape
  - process_flow: phase flow, journey, implementation steps, roadmap
  - org_governance: responsibilities, governance, ownership, collaboration
- Keep titles concise.
- Keep subtitles concise and executive-friendly.
- Bullets must be short, specific, and presentation-ready.
- Avoid filler like "进一步提升效率" unless tied to concrete content.
- Mirror the user's language when obvious; default to {request.language}.
""".strip()

    source_brief = request.brief.strip()
    if source_brief:
        source_brief = source_brief[:DEFAULT_AI_SOURCE_CHAR_LIMIT]

    user_prompt = f"""
Plan a PPT deck outline.

Topic:
{request.topic.strip()}

Audience:
{request.audience.strip()}

Requested body pages:
{slide_count_request}

Additional source material:
{source_brief or "None"}

Output rules:
- {slide_count_output_rule}
- Each page should feel distinct and logically sequenced.
- Prefer a storyline like context -> solution -> execution, but adapt to the topic.
- If the source material is sparse, create a sensible executive outline rather than repeating the same point.
""".strip()
    return developer_prompt, user_prompt


def normalize_ai_pattern_id(pattern_id: str, title: str, bullets: list[str]) -> str:
    normalized = PATTERN_COMPATIBILITY_MAP.get(pattern_id, "")
    if normalized in SUPPORTED_AI_PATTERNS:
        return normalized

    inferred = infer_pattern(title, bullets)
    inferred = PATTERN_COMPATIBILITY_MAP.get(inferred, inferred)
    if inferred in SUPPORTED_AI_PATTERNS:
        return inferred
    return "general_business"


def normalize_ai_bullets(bullets: list[Any], title: str) -> list[str]:
    normalized = []
    for item in bullets:
        text = compact_text(str(item).strip(), 80)
        if text:
            normalized.append(text)
    if len(normalized) >= 2:
        return normalized[:4]
    fallback = compact_text(title, 40) or "关键信息"
    while len(normalized) < 2:
        normalized.append(fallback)
    return normalized[:4]


def build_deck_spec_from_ai_outline(data: dict[str, Any], slide_bounds: AiSlideBounds) -> DeckSpec:
    body_pages_data = list(data.get("body_pages", []))
    if not (slide_bounds.min_slides <= len(body_pages_data) <= slide_bounds.max_slides):
        if slide_bounds.is_exact:
            raise ValueError(
                f"AI planner returned {len(body_pages_data)} body pages, expected exactly {slide_bounds.min_slides}."
            )
        raise ValueError(
            f"AI planner returned {len(body_pages_data)} body pages, expected between "
            f"{slide_bounds.min_slides} and {slide_bounds.max_slides}."
        )

    body_pages = []
    for index, page_data in enumerate(body_pages_data, start=1):
        title = compact_text(str(page_data.get("title", "")).strip(), 30)
        if not title:
            title = f"第{index}页"
        subtitle = compact_text(str(page_data.get("subtitle", "")).strip(), 60)
        bullets = normalize_ai_bullets(list(page_data.get("bullets", [])), title)
        pattern_id = normalize_ai_pattern_id(str(page_data.get("pattern_id", "")).strip(), title, bullets)
        nav_title = shorten_for_nav(str(page_data.get("nav_title", "")).strip() or title)
        body_pages.append(
            BodyPageSpec(
                page_key=f"ai_page_{index:02d}",
                title=title,
                subtitle=subtitle,
                bullets=bullets,
                pattern_id=pattern_id,
                nav_title=nav_title,
            )
        )

    cover_title = compact_text(str(data.get("cover_title", "")).strip(), 40) or compact_text(body_pages[0].title, 40)
    return DeckSpec(
        cover_title=cover_title,
        body_pages=body_pages,
    )


def resolve_external_planner_command(planner_command: str | None = None) -> str:
    return (planner_command or os.environ.get(EXTERNAL_PLANNER_COMMAND_ENV, "")).strip()


def build_external_planner_payload(
    planning_request: AiPlanningRequest,
    developer_prompt: str,
    user_prompt: str,
    slide_bounds: AiSlideBounds,
) -> dict[str, Any]:
    return {
        "request": {
            "topic": planning_request.topic,
            "chapters": planning_request.chapters,
            "min_slides": slide_bounds.min_slides,
            "max_slides": slide_bounds.max_slides,
            "audience": planning_request.audience,
            "brief": planning_request.brief,
            "language": planning_request.language,
        },
        "developer_prompt": developer_prompt,
        "user_prompt": user_prompt,
        "outline_schema": build_ai_outline_schema(slide_bounds),
        "output_contract": {
            "accepted_top_level": ["deck_spec", "outline", "cover_title/body_pages"],
            "notes": [
                "Return only JSON on stdout.",
                "If returning deck_spec, keep it compatible with the SIE AutoPPT DeckSpec JSON contract.",
                "If returning outline, keep it compatible with the outline_schema payload.",
            ],
        },
    }


def parse_external_planner_output(raw_text: str, slide_bounds: AiSlideBounds) -> DeckSpec:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ExternalPlannerError(f"External planner returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExternalPlannerError("External planner must return a top-level JSON object.")

    if isinstance(payload.get("deck_spec"), dict):
        return deck_spec_from_dict(payload["deck_spec"])
    if isinstance(payload.get("outline"), dict):
        return build_deck_spec_from_ai_outline(payload["outline"], slide_bounds=slide_bounds)
    return build_deck_spec_from_ai_outline(payload, slide_bounds=slide_bounds)


def _split_windows_command(command: str) -> list[str]:
    import ctypes

    argc = ctypes.c_int()
    command_line_to_argv = ctypes.windll.shell32.CommandLineToArgvW
    command_line_to_argv.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    command_line_to_argv.restype = ctypes.POINTER(ctypes.c_wchar_p)
    local_free = ctypes.windll.kernel32.LocalFree
    local_free.argtypes = [ctypes.c_void_p]
    local_free.restype = ctypes.c_void_p
    argv = command_line_to_argv(command, ctypes.byref(argc))
    if not argv:
        raise ValueError(f"Failed to parse Windows command line: {command}")
    try:
        return [argv[index] for index in range(argc.value)]
    finally:
        local_free(argv)


def parse_external_planner_command(planner_command: str) -> list[str]:
    candidate = planner_command.strip()
    if not candidate:
        raise ValueError("External planner command must not be empty.")

    if candidate.startswith("["):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list) and parsed and all(isinstance(item, str) and item for item in parsed):
            return parsed

    if os.name == "nt":
        return _split_windows_command(candidate)
    return shlex.split(candidate, posix=True)


def plan_deck_spec_with_external_command(
    planning_request: AiPlanningRequest,
    planner_command: str,
) -> DeckSpec:
    slide_bounds = resolve_ai_slide_bounds(planning_request)
    developer_prompt, user_prompt = build_ai_planning_prompts(planning_request, slide_bounds=slide_bounds)
    payload = build_external_planner_payload(planning_request, developer_prompt, user_prompt, slide_bounds)
    command_args = parse_external_planner_command(planner_command)
    try:
        result = subprocess.run(
            command_args,
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            shell=False,
            check=False,
        )
    except OSError as exc:
        raise ExternalPlannerError(f"Failed to launch external planner command: {exc}") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ExternalPlannerError(
            f"External planner command failed with exit code {result.returncode}: {detail or 'no output'}"
        )

    output_text = (result.stdout or "").strip()
    if not output_text:
        raise ExternalPlannerError("External planner command produced no stdout JSON.")
    return parse_external_planner_output(output_text, slide_bounds=slide_bounds)


def plan_deck_spec_with_ai(
    planning_request: AiPlanningRequest,
    model: str | None = None,
    planner_command: str | None = None,
) -> DeckSpec:
    normalized_request = AiPlanningRequest(
        topic=planning_request.topic.strip(),
        chapters=planning_request.chapters,
        min_slides=planning_request.min_slides,
        max_slides=planning_request.max_slides,
        audience=planning_request.audience.strip() or "管理层 + 业务负责人",
        brief=planning_request.brief,
        language=planning_request.language.strip() or "zh-CN",
    )
    if not normalized_request.topic:
        raise ValueError("AI planning topic must not be empty.")
    slide_bounds = resolve_ai_slide_bounds(normalized_request)

    resolved_command = resolve_external_planner_command(planner_command)
    if resolved_command:
        return plan_deck_spec_with_external_command(normalized_request, resolved_command)

    developer_prompt, user_prompt = build_ai_planning_prompts(normalized_request, slide_bounds=slide_bounds)
    client = OpenAIResponsesClient(load_openai_responses_config(model=model))
    raw_outline = client.create_structured_json(
        developer_prompt=developer_prompt,
        user_prompt=user_prompt,
        schema_name="sie_autoppt_outline",
        schema=build_ai_outline_schema(slide_bounds),
    )
    return build_deck_spec_from_ai_outline(raw_outline, slide_bounds=slide_bounds)


def plan_deck_spec_with_llm(planning_request: AiPlanningRequest, model: str | None = None) -> DeckSpec:
    return plan_deck_spec_with_ai(planning_request, model=model)
