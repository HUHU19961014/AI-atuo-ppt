import re


TITLE_DETAIL_SEPARATORS = ("：", ":", " - ", " | ")
SENTENCE_SEPARATORS_PATTERN = r"[.;!?。；！？]+"


def split_title_detail(text: str) -> tuple[str, str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    for sep in TITLE_DETAIL_SEPARATORS:
        if sep in normalized:
            title, detail = normalized.split(sep, 1)
            return title.strip(), detail.strip()
    return normalized, normalized


def compact_text(text: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip(" ,;") + "…"


def concise_text(text: str, max_chars: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    parts = [part.strip() for part in re.split(SENTENCE_SEPARATORS_PATTERN, compact) if part.strip()]
    if not parts:
        return compact_text(compact, max_chars)
    candidate = parts[0]
    if len(parts) > 1 and len(candidate) + len(parts[1]) + 1 <= max_chars:
        candidate = f"{candidate}; {parts[1]}"
    return compact_text(candidate, max_chars)


def short_stage_label(text: str, max_chars: int = 8) -> str:
    compact = re.sub(r"\s+", "", text)
    compact = re.sub(r"\(.*?\)", "", compact)
    return compact[:max_chars] if len(compact) > max_chars else compact


def shorten_for_nav(text: str, max_chars: int = 10) -> str:
    compact = re.sub(r"\s+", "", text).replace("(", "").replace(")", "")
    return compact[:max_chars] if len(compact) > max_chars else compact


__all__ = [
    "compact_text",
    "concise_text",
    "short_stage_label",
    "shorten_for_nav",
    "split_title_detail",
]
