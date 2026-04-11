import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from difflib import SequenceMatcher

from .config import (
    DEFAULT_PATTERN_ASSIST_MODEL,
    DEFAULT_PATTERN_LOW_CONFIDENCE_SCORE,
    DEFAULT_PATTERN_MARGIN_THRESHOLD,
    ENABLE_AI_PATTERN_ASSIST,
    PATTERN_FILE,
)

# NOTE: This module is only used in the legacy HTML input path.
# AI planner flows choose pattern_id directly and only fall back to this matcher
# when normalizing unsupported values or handling historical HTML-based decks.

PATTERN_ALIASES: dict[str, tuple[str, ...]] = {
    "policy_timeline": ("policy", "regulation", "compliance", "timeline", "trend"),
    "pain_points": ("pain", "problem", "issue", "challenge", "risk", "bottleneck"),
    "value_benefit": ("value", "benefit", "roi", "outcome", "gain", "impact"),
    "solution_architecture": (
        "architecture",
        "blueprint",
        "platform",
        "landscape",
        "system",
        "application",
    ),
    "process_flow": ("process", "workflow", "flow", "journey", "stage", "steps"),
    "org_governance": ("governance", "organization", "ownership", "roles", "team", "operating model"),
    "implementation_plan": ("implementation", "rollout", "roadmap", "milestone", "delivery plan"),
    "capability_matrix": ("capability", "matrix", "maturity", "assessment", "scorecard"),
    "case_proof": ("case", "reference", "proof", "evidence", "benchmark"),
    "action_next_steps": ("action", "next step", "recommendation", "summary", "roadmap"),
    "roadmap_timeline": ("roadmap", "timeline", "milestone", "phase", "quarter", "里程碑", "路线图", "阶段目标"),
    "kpi_dashboard": ("kpi", "dashboard", "metric", "scorecard", "target", "指标", "仪表盘", "经营表现"),
    "risk_matrix": ("risk", "matrix", "probability", "impact", "风险", "矩阵", "概率", "影响"),
    "claim_breakdown": ("claim", "breakdown", "amount", "cost", "索赔", "拆解", "金额", "构成"),
}

LAYOUT_PREFERENCE_AXES: dict[str, tuple[str, ...]] = {
    "visual_weight": ("left", "right", "center", "balanced"),
    "density": ("compact", "normal", "spacious"),
    "alignment": ("left", "center", "right"),
}

_DIRECT_PATTERN_HINTS: dict[str, tuple[str, ...]] = {
    "roadmap_timeline": ("路线图", "里程碑", "时间轴", "roadmap", "milestone"),
    "kpi_dashboard": ("仪表盘", "kpi", "dashboard", "scorecard", "经营指标"),
    "risk_matrix": ("风险矩阵", "风险", "概率", "影响", "risk matrix"),
    "claim_breakdown": ("索赔拆解", "金额拆解", "成本拆解", "claim breakdown"),
}


@dataclass(frozen=True)
class PatternInferenceResult:
    pattern_id: str
    best_score: int
    second_best_score: int
    low_confidence: bool
    used_ai_assist: bool = False
    ai_assist_error: str = ""


@lru_cache(maxsize=1)
def load_patterns():
    data = json.loads(PATTERN_FILE.read_text(encoding="utf-8"))
    return data.get("patterns", [])


def supported_pattern_ids() -> tuple[str, ...]:
    pattern_ids: list[str] = []
    for pattern in load_patterns():
        pattern_id = str(pattern.get("id", "")).strip()
        if pattern_id:
            pattern_ids.append(pattern_id)
    return tuple(pattern_ids)


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _text_forms(text: str) -> tuple[str, str]:
    normalized = _normalize_text(text)
    compact = normalized.replace(" ", "")
    return normalized, compact


def _extract_english_tokens(text: str) -> set[str]:
    normalized, _ = _text_forms(text)
    return set(re.findall(r"[a-z0-9]+", normalized))


def _is_close_english_token(token: str, candidates: set[str]) -> bool:
    if len(token) < 5:
        return False
    return any(
        abs(len(token) - len(candidate)) <= 1 and SequenceMatcher(None, token, candidate).ratio() >= 0.84
        for candidate in candidates
    )


def _contains_phrase(phrase: str, normalized_text: str, compact_text: str) -> bool:
    normalized_phrase, compact_phrase = _text_forms(phrase)
    if not normalized_phrase:
        return False
    return normalized_phrase in normalized_text or compact_phrase in compact_text


def _score_alias(alias: str, normalized_text: str, compact_text: str, english_tokens: set[str]) -> int:
    if _contains_phrase(alias, normalized_text, compact_text):
        return 2

    alias_tokens = re.findall(r"[a-z0-9]+", _normalize_text(alias))
    if not alias_tokens:
        return 0
    if all(token in english_tokens for token in alias_tokens):
        return 2
    if len(alias_tokens) == 1 and _is_close_english_token(alias_tokens[0], english_tokens):
        return 1
    return 0


def _is_low_confidence(best_score: int, second_best_score: int) -> bool:
    return best_score < DEFAULT_PATTERN_LOW_CONFIDENCE_SCORE or (best_score - second_best_score) <= DEFAULT_PATTERN_MARGIN_THRESHOLD


def _direct_pattern_match(title: str, bullets: list[str]) -> str:
    combined = f"{title} {' '.join(bullets or [])}".lower()
    for pattern_id, hints in _DIRECT_PATTERN_HINTS.items():
        if any(hint.lower() in combined for hint in hints):
            return pattern_id
    return ""


def _score_patterns(title: str, bullets: list[str]) -> list[tuple[str, int]]:
    title_text = title or ""
    bullet_text = " ".join(bullets or [])

    normalized_title, compact_title = _text_forms(title_text)
    normalized_body, compact_body = _text_forms(f"{title_text} {bullet_text}")
    body_tokens = _extract_english_tokens(f"{title_text} {bullet_text}")

    scores = []
    for pattern in load_patterns():
        pattern_id = pattern.get("id", "general_business")
        score = 0

        for keyword in pattern.get("keywords", []):
            if _contains_phrase(keyword, normalized_title, compact_title):
                score += 4
            elif _contains_phrase(keyword, normalized_body, compact_body):
                score += 3

        for alias in PATTERN_ALIASES.get(pattern_id, ()):
            if _contains_phrase(alias, normalized_title, compact_title):
                score += 3
            else:
                score += _score_alias(alias, normalized_body, compact_body, body_tokens)

        scores.append((pattern_id, score))
    return sorted(scores, key=lambda item: (item[1], item[0] != "general_business"), reverse=True)


def _resolve_pattern_with_llm(title: str, bullets: list[str], candidate_pattern_ids: list[str]) -> str:
    from .llm_openai import OpenAIResponsesClient, load_openai_responses_config

    client = OpenAIResponsesClient(load_openai_responses_config(model=DEFAULT_PATTERN_ASSIST_MODEL))
    developer_prompt = """
Choose the most appropriate PPT layout pattern.

Only decide the semantic layout type. Do not explain. Return only the schema-constrained JSON.
Prefer general_business when the input is too generic.
""".strip()
    user_prompt = f"""
Title:
{title}

Bullets:
{chr(10).join(f"- {item}" for item in bullets)}
""".strip()
    result = client.create_structured_json(
        developer_prompt=developer_prompt,
        user_prompt=user_prompt,
        schema_name="sie_autoppt_pattern_pick",
        schema={
            "type": "object",
            "properties": {
                "pattern_id": {
                    "type": "string",
                    "enum": candidate_pattern_ids,
                }
            },
            "required": ["pattern_id"],
            "additionalProperties": False,
        },
    )
    return str(result["pattern_id"])


def infer_pattern_details(
    title: str,
    bullets: list[str],
    enable_ai_assist: bool | None = None,
    ai_pattern_resolver=None,
) -> PatternInferenceResult:
    direct_match = _direct_pattern_match(title, bullets)
    if direct_match:
        return PatternInferenceResult(
            pattern_id=direct_match,
            best_score=10,
            second_best_score=0,
            low_confidence=False,
            used_ai_assist=False,
        )

    scores = _score_patterns(title, bullets)
    best_id = "general_business"
    best_score = 0
    second_best_score = 0
    if scores:
        best_id, best_score = scores[0]
        second_best_score = scores[1][1] if len(scores) > 1 else 0
    if best_score <= 0:
        best_id = "general_business"
        second_best_score = 0

    low_confidence = _is_low_confidence(best_score, second_best_score)
    should_use_ai_assist = ENABLE_AI_PATTERN_ASSIST if enable_ai_assist is None else enable_ai_assist
    if low_confidence and should_use_ai_assist:
        resolver = ai_pattern_resolver or _resolve_pattern_with_llm
        try:
            resolved = resolver(
                title,
                bullets,
                ["general_business", *[pattern_id for pattern_id, _ in scores]],
            )
        except Exception as exc:
            return PatternInferenceResult(
                pattern_id=best_id,
                best_score=best_score,
                second_best_score=second_best_score,
                low_confidence=low_confidence,
                used_ai_assist=False,
                ai_assist_error=str(exc),
            )
        if isinstance(resolved, str) and resolved:
            return PatternInferenceResult(
                pattern_id=resolved,
                best_score=best_score,
                second_best_score=second_best_score,
                low_confidence=low_confidence,
                used_ai_assist=True,
            )

    return PatternInferenceResult(
        pattern_id=best_id,
        best_score=best_score,
        second_best_score=second_best_score,
        low_confidence=low_confidence,
    )


def infer_pattern(title: str, bullets: list[str]) -> str:
    return infer_pattern_details(title, bullets).pattern_id
