import json
import re
import unicodedata
from functools import lru_cache
from difflib import SequenceMatcher

from .config import PATTERN_FILE

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
}


@lru_cache(maxsize=1)
def load_patterns():
    data = json.loads(PATTERN_FILE.read_text(encoding="utf-8"))
    return data.get("patterns", [])


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


def infer_pattern(title: str, bullets: list[str]) -> str:
    title_text = title or ""
    bullet_text = " ".join(bullets or [])

    normalized_title, compact_title = _text_forms(title_text)
    normalized_body, compact_body = _text_forms(f"{title_text} {bullet_text}")
    body_tokens = _extract_english_tokens(f"{title_text} {bullet_text}")

    best_id = "general_business"
    best_score = 0

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

        if score > best_score:
            best_id = pattern_id
            best_score = score

    return best_id
