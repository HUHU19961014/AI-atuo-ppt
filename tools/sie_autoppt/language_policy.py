from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguagePolicy:
    code: str
    label: str
    unknown_token: str
    none_token: str
    prompt_constraints: tuple[str, ...]


_LANGUAGE_POLICIES: dict[str, LanguagePolicy] = {
    "zh-CN": LanguagePolicy(
        code="zh-CN",
        label="Simplified Chinese (zh-CN)",
        unknown_token="未知",
        none_token="无",
        prompt_constraints=(
            "All user-facing text must be in Simplified Chinese.",
            "Do not mix English phrases unless they are standard abbreviations (AI, KPI, ROI, API).",
        ),
    ),
    "en-US": LanguagePolicy(
        code="en-US",
        label="English (en-US)",
        unknown_token="unknown",
        none_token="none",
        prompt_constraints=(
            "All user-facing text must be in English.",
            "Do not mix Chinese phrases in titles, goals, or bullets.",
        ),
    ),
}

_LANGUAGE_ALIASES = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "cn": "zh-CN",
    "en": "en-US",
    "en-us": "en-US",
    "en_us": "en-US",
}


def normalize_language_code(value: str | None) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return "zh-CN"
    lowered = candidate.lower().replace("_", "-")
    if lowered in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[lowered]
    for supported in _LANGUAGE_POLICIES:
        if supported.lower() == lowered:
            return supported
    return "zh-CN"


def get_language_policy(language: str | None) -> LanguagePolicy:
    return _LANGUAGE_POLICIES[normalize_language_code(language)]


def format_language_constraints(policy: LanguagePolicy) -> str:
    return "\n".join(f"- {line}" for line in policy.prompt_constraints)


__all__ = [
    "LanguagePolicy",
    "format_language_constraints",
    "get_language_policy",
    "normalize_language_code",
]
