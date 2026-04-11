from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .quality_checks import ContentWarning, QualityGateResult, quality_gate
from .rule_config import load_v2_rule_config
from .schema import ValidatedDeck, validate_deck_payload


TITLE_LIMIT = 24
BULLET_LIMIT = 32
TITLE_CONTENT_TARGET = 6
TITLE_IMAGE_TARGET = 4
TWO_COLUMNS_TARGET = 5
RULE_CONFIG = load_v2_rule_config()

FIXABLE_PATTERNS = (
    "title contains",
    "appears to be directory-style",
    "generic-background oriented",
    "generic closing or thanks",
    "last slide does not clearly express a recommendation, decision, roadmap, or next step",
    "title repeats an earlier page",
    "adjacent slides repeat",
    "bullet items",
    "bullet ",
    "title_image has",
    "title_image content",
    "left column has",
    "right column has",
    "item count gap",
)

FILLER_PATTERNS = tuple(re.compile(pattern) for pattern in RULE_CONFIG.rewrite.filler_patterns)
FILLER_SAFE_PHRASES = RULE_CONFIG.rewrite.filler_safe_phrases

DIRECTORY_STYLE_WARNING = "appears to be directory-style"
GENERIC_OPENING_WARNING = "generic-background oriented"
GENERIC_CLOSING_WARNING = "generic closing or thanks"
LAST_SLIDE_ACTION_WARNING = "last slide does not clearly express a recommendation, decision, roadmap, or next step"
REPEATED_TITLE_WARNING = "title repeats an earlier page"
REPEATED_ADJACENT_WARNING = "adjacent slides repeat"
CONCLUSION_MARKERS = (
    "需要",
    "需",
    "应",
    "将",
    "已",
    "已经",
    "正在",
    "不是",
    "而是",
    "成为",
    "转向",
    "推动",
    "提升",
    "恢复",
    "守住",
    "聚焦",
    "建立",
    "形成",
    "支撑",
    "依赖",
    "本质",
    "意味着",
)
TITLE_SPLIT_PATTERN = re.compile(r"[，,。；;：:、]")
PHASE_PREFIX_PATTERN = re.compile(r"^第[一二三四五六七八九十0-9]+阶段")


@dataclass(frozen=True)
class RewriteAction:
    slide_id: str
    field: str
    action: str
    before: Any
    after: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "slide_id": self.slide_id,
            "field": self.field,
            "action": self.action,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True)
class RewriteDeckResult:
    attempted: bool
    applied: bool
    validated_deck: ValidatedDeck | None
    initial_quality_gate: QualityGateResult
    final_quality_gate: QualityGateResult
    actions: tuple[RewriteAction, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempted": self.attempted,
            "applied": self.applied,
            "action_count": len(self.actions),
            "rewritten_slide_ids": sorted({action.slide_id for action in self.actions}),
            "initial_summary": self.initial_quality_gate.summary,
            "final_summary": self.final_quality_gate.summary,
            "notes": list(self.notes),
            "actions": [action.to_dict() for action in self.actions],
        }


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip())


def _strip_parenthetical(text: str) -> str:
    return re.sub(r"[\(（][^\)）]{0,20}[\)）]", "", text)


def _cleanup_text(text: str) -> str:
    cleaned = _normalize_text(text)
    cleaned = cleaned.strip(" ,，;；:：/、")
    cleaned = re.sub(r"[，,；;]{2,}", "；", cleaned)
    cleaned = re.sub(r"[:：]{2,}", "：", cleaned)
    return cleaned or _normalize_text(text)


def _truncate_text(text: str, max_length: int) -> str:
    normalized = _cleanup_text(text)
    if len(normalized) <= max_length:
        return normalized
    clipped = normalized[:max_length].rstrip(" ,，;；:：/、")
    return clipped or normalized[:max_length]


def _strip_filler_patterns(text: str) -> str:
    protected = text
    replacements: dict[str, str] = {}
    for index, phrase in enumerate(FILLER_SAFE_PHRASES):
        if not phrase:
            continue
        placeholder = f"__SAFE_FILLER_{index}__"
        if phrase in protected:
            protected = protected.replace(phrase, placeholder)
            replacements[placeholder] = phrase

    stripped = protected
    for pattern in FILLER_PATTERNS:
        stripped = pattern.sub("", stripped)

    for placeholder, phrase in replacements.items():
        stripped = stripped.replace(placeholder, phrase)
    return stripped


def _compress_text(text: str, max_length: int) -> str:
    normalized = _cleanup_text(_strip_parenthetical(text))
    candidates = [normalized]

    fragment_parts = [part.strip() for part in re.split(r"[；;，,。！？!?:：/、]", normalized) if part.strip()]
    if fragment_parts:
        candidates.append("；".join(fragment_parts[:2]))
        candidates.append(fragment_parts[0])

    reduced = _strip_filler_patterns(normalized)
    candidates.append(_cleanup_text(reduced))

    for candidate in candidates:
        if candidate and len(candidate) <= max_length:
            return candidate

    compact = min((candidate for candidate in candidates if candidate), key=len, default=normalized)
    return _truncate_text(compact, max_length)


def _split_title_fragments(text: str) -> list[str]:
    return [fragment.strip(" ，,。；;：:、") for fragment in TITLE_SPLIT_PATTERN.split(text) if fragment.strip(" ，,。；;：:、")]


def _is_conclusion_like(text: str) -> bool:
    return any(marker in text for marker in CONCLUSION_MARKERS)


def _strip_phase_prefix(text: str) -> str:
    cleaned = PHASE_PREFIX_PATTERN.sub("", _normalize_text(text)).lstrip(" ：:，,、")
    return cleaned or _normalize_text(text)


def _compress_title_text(text: str, max_length: int) -> str:
    normalized = _cleanup_text(_strip_parenthetical(_strip_phase_prefix(text)))
    if len(normalized) <= max_length:
        return normalized

    fragments = _split_title_fragments(normalized)
    conclusion_fragments = [fragment for fragment in fragments if len(fragment) <= max_length and _is_conclusion_like(fragment)]
    if conclusion_fragments:
        return max(conclusion_fragments, key=len)

    concise_fragments = [fragment for fragment in fragments if len(fragment) <= max_length]
    if concise_fragments:
        return max(concise_fragments, key=len)

    return _compress_text(normalized, max_length)


def _merge_items(items: list[str], target_count: int, max_length: int) -> list[str]:
    merged = [_cleanup_text(item) for item in items if _cleanup_text(item)]
    while len(merged) > target_count and len(merged) >= 2:
        tail_right = merged.pop()
        tail_left = merged.pop()
        merged.append(_compress_text(f"{tail_left}；{tail_right}", max_length))
    return merged


def _compress_items(items: list[str], max_length: int) -> list[str]:
    return [_compress_text(item, max_length) if len(_normalize_text(item)) > max_length else _cleanup_text(item) for item in items]


def _is_fixable_issue(issue: ContentWarning) -> bool:
    return any(pattern in issue.message for pattern in FIXABLE_PATTERNS)


def _group_issues_by_slide(issues: tuple[ContentWarning, ...]) -> dict[str, list[ContentWarning]]:
    grouped: dict[str, list[ContentWarning]] = {}
    for issue in issues:
        if not _is_fixable_issue(issue):
            continue
        grouped.setdefault(issue.slide_id, []).append(issue)
    return grouped


def _title_candidates(slide: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    subtitle = _normalize_text(str(slide.get("subtitle", "")))
    if subtitle:
        candidates.append(subtitle)

    layout = str(slide.get("layout", ""))
    if layout in {"title_content", "title_image"}:
        candidates.extend(_normalize_text(item) for item in slide.get("content", []) if _normalize_text(item))
    elif layout == "two_columns":
        left = slide.get("left", {}) if isinstance(slide.get("left"), dict) else {}
        right = slide.get("right", {}) if isinstance(slide.get("right"), dict) else {}
        candidates.extend(_normalize_text(item) for item in left.get("items", []) if _normalize_text(item))
        candidates.extend(_normalize_text(item) for item in right.get("items", []) if _normalize_text(item))

    return candidates


def _derive_directory_style_title(slide: dict[str, Any]) -> str:
    original_title = _normalize_text(str(slide.get("title", "")))
    for candidate in _title_candidates(slide):
        rewritten = _compress_title_text(candidate, TITLE_LIMIT)
        if rewritten and rewritten != original_title:
            return rewritten
    return ""


def _derive_last_slide_action_title(previous_slide: dict[str, Any], language: str) -> str:
    prefix = "下一步："
    if not str(language or "").lower().startswith("zh"):
        prefix = "Next step: "

    body_limit = max(8, TITLE_LIMIT - len(prefix))
    for candidate in _title_candidates(previous_slide):
        rewritten = _compress_title_text(candidate, body_limit)
        if rewritten:
            return _truncate_text(f"{prefix}{rewritten}", TITLE_LIMIT)

    previous_title = _normalize_text(str(previous_slide.get("title", "")))
    if previous_title:
        rewritten = _compress_title_text(previous_title, body_limit)
        if rewritten:
            return _truncate_text(f"{prefix}{rewritten}", TITLE_LIMIT)
    return ""


def _slide_signature_items(slide: dict[str, Any]) -> set[str]:
    layout = str(slide.get("layout", ""))
    signatures: set[str] = set()
    if layout in {"title_content", "title_image"}:
        for item in slide.get("content", []):
            normalized = _normalize_text(str(item))
            if normalized:
                signatures.add(normalized)
    elif layout == "two_columns":
        for column_name in ("left", "right"):
            column = slide.get(column_name, {})
            if not isinstance(column, dict):
                continue
            for item in column.get("items", []):
                normalized = _normalize_text(str(item))
                if normalized:
                    signatures.add(normalized)
    return signatures


def _remove_adjacent_repeated_content(
    previous_slide: dict[str, Any],
    current_slide: dict[str, Any],
    actions: list[RewriteAction],
) -> dict[str, Any]:
    previous_signatures = _slide_signature_items(previous_slide)
    if not previous_signatures:
        return current_slide

    slide_id = str(current_slide.get("slide_id", "unknown"))
    updated = dict(current_slide)
    layout = str(updated.get("layout", ""))

    if layout in {"title_content", "title_image"}:
        content = list(updated.get("content", []))
        deduped = [item for item in content if _normalize_text(str(item)) not in previous_signatures]
        if deduped and deduped != content:
            actions.append(
                RewriteAction(
                    slide_id=slide_id,
                    field="content",
                    action="remove_adjacent_repeated_content",
                    before=content,
                    after=deduped,
                )
            )
            updated["content"] = deduped
        return updated

    if layout == "two_columns":
        changed = False
        for column_name in ("left", "right"):
            column = updated.get(column_name, {})
            if not isinstance(column, dict):
                continue
            items = list(column.get("items", []))
            deduped = [item for item in items if _normalize_text(str(item)) not in previous_signatures]
            if deduped and deduped != items:
                actions.append(
                    RewriteAction(
                        slide_id=slide_id,
                        field=f"{column_name}.items",
                        action="remove_adjacent_repeated_content",
                        before=items,
                        after=deduped,
                    )
                )
                column["items"] = deduped
                updated[column_name] = column
                changed = True
        if changed:
            return updated

    return current_slide


def _rewrite_last_slide_with_context(
    previous_slide: dict[str, Any],
    current_slide: dict[str, Any],
    issue_messages: list[str],
    actions: list[RewriteAction],
    *,
    language: str,
) -> dict[str, Any]:
    if str(current_slide.get("layout", "")) not in {"title_only", "section_break"}:
        return current_slide

    candidate = _derive_last_slide_action_title(previous_slide, language)
    if not candidate:
        return current_slide

    current_title = str(current_slide.get("title", ""))
    if candidate == current_title:
        return current_slide

    action_name = "rewrite_last_slide_to_next_step"
    if any(GENERIC_CLOSING_WARNING in message for message in issue_messages):
        action_name = "rewrite_generic_closing_to_next_step"

    slide_id = str(current_slide.get("slide_id", "unknown"))
    updated = dict(current_slide)
    actions.append(
        RewriteAction(
            slide_id=slide_id,
            field="title",
            action=action_name,
            before=current_title,
            after=candidate,
        )
    )
    updated["title"] = candidate
    _refine_title_related_content(updated, actions)
    return updated


def _refine_title_related_content(slide: dict[str, Any], actions: list[RewriteAction]) -> None:
    slide_id = str(slide.get("slide_id", "unknown"))
    title = _normalize_text(str(slide.get("title", "")))
    layout = str(slide.get("layout", ""))

    if layout == "section_break":
        subtitle = _normalize_text(str(slide.get("subtitle", "")))
        if not subtitle:
            return
        if subtitle == title:
            actions.append(
                RewriteAction(
                    slide_id=slide_id,
                    field="subtitle",
                    action="drop_duplicate_subtitle_after_title_rewrite",
                    before=subtitle,
                    after="",
                )
            )
            slide["subtitle"] = None
            return
        fragments = _split_title_fragments(subtitle)
        supporting_fragment = next((fragment for fragment in fragments if fragment != title), "")
        if supporting_fragment and title in fragments and supporting_fragment != subtitle:
            actions.append(
                RewriteAction(
                    slide_id=slide_id,
                    field="subtitle",
                    action="refine_subtitle_after_title_rewrite",
                    before=subtitle,
                    after=supporting_fragment,
                )
            )
            slide["subtitle"] = supporting_fragment
        return

    if layout in {"title_content", "title_image"}:
        content = list(slide.get("content", []))
        deduped = [item for item in content if _normalize_text(item) != title]
        if deduped and deduped != content:
            actions.append(
                RewriteAction(
                    slide_id=slide_id,
                    field="content",
                    action="remove_title_duplicate_item",
                    before=content,
                    after=deduped,
                )
            )
            slide["content"] = deduped
        return

    if layout == "two_columns":
        for column_name in ("left", "right"):
            column = slide.get(column_name, {})
            if not isinstance(column, dict):
                continue
            items = list(column.get("items", []))
            deduped = [item for item in items if _normalize_text(item) != title]
            if deduped and deduped != items:
                actions.append(
                    RewriteAction(
                        slide_id=slide_id,
                        field=f"{column_name}.items",
                        action="remove_title_duplicate_item",
                        before=items,
                        after=deduped,
                    )
                )
                column["items"] = deduped
                slide[column_name] = column


def _rewrite_title(slide: dict[str, Any], issue_messages: list[str], actions: list[RewriteAction]) -> str:
    slide_id = str(slide.get("slide_id", "unknown"))
    title = str(slide.get("title", ""))
    rewritten = title

    if any(
        pattern in message
        for message in issue_messages
        for pattern in (
            DIRECTORY_STYLE_WARNING,
            GENERIC_OPENING_WARNING,
            GENERIC_CLOSING_WARNING,
            REPEATED_TITLE_WARNING,
        )
    ):
        candidate = _derive_directory_style_title(slide)
        if candidate and candidate != rewritten:
            action_name = "rewrite_directory_style_title"
            if any(GENERIC_OPENING_WARNING in message for message in issue_messages):
                action_name = "rewrite_generic_opening_title"
            elif any(GENERIC_CLOSING_WARNING in message for message in issue_messages):
                action_name = "rewrite_generic_closing_title"
            elif any(REPEATED_TITLE_WARNING in message for message in issue_messages):
                action_name = "rewrite_repeated_title"
            actions.append(
                RewriteAction(
                    slide_id=slide_id,
                    field="title",
                    action=action_name,
                    before=rewritten,
                    after=candidate,
                )
            )
            rewritten = candidate

    compressed = _compress_title_text(rewritten, TITLE_LIMIT)
    if compressed != rewritten:
        actions.append(
            RewriteAction(
                slide_id=slide_id,
                field="title",
                action="compress_title",
                before=rewritten,
                after=compressed,
            )
        )
    return compressed


def _rewrite_content_items(
    slide_id: str,
    items: list[str],
    *,
    max_length: int,
    target_count: int,
    actions: list[RewriteAction],
    field: str,
) -> list[str]:
    updated = list(items)
    compressed = _compress_items(updated, max_length)
    if compressed != updated:
        actions.append(
            RewriteAction(
                slide_id=slide_id,
                field=field,
                action="compress_items",
                before=updated,
                after=compressed,
            )
        )
        updated = compressed

    merged = _merge_items(updated, target_count, max_length)
    if merged != updated:
        actions.append(
            RewriteAction(
                slide_id=slide_id,
                field=field,
                action="merge_items",
                before=updated,
                after=merged,
            )
        )
        updated = merged
    return updated


def _rewrite_two_columns(slide: dict[str, Any], actions: list[RewriteAction]) -> dict[str, Any]:
    updated = dict(slide)
    left = dict(updated["left"])
    right = dict(updated["right"])

    left_items = _compress_items(list(left["items"]), BULLET_LIMIT)
    right_items = _compress_items(list(right["items"]), BULLET_LIMIT)

    if left_items != left["items"]:
        actions.append(
            RewriteAction(
                slide_id=slide["slide_id"],
                field="left.items",
                action="compress_items",
                before=list(left["items"]),
                after=left_items,
            )
        )
    if right_items != right["items"]:
        actions.append(
            RewriteAction(
                slide_id=slide["slide_id"],
                field="right.items",
                action="compress_items",
                before=list(right["items"]),
                after=right_items,
            )
        )

    while len(left_items) > TWO_COLUMNS_TARGET:
        next_items = _merge_items(left_items, len(left_items) - 1, BULLET_LIMIT)
        if next_items == left_items:
            break
        actions.append(
            RewriteAction(
                slide_id=slide["slide_id"],
                field="left.items",
                action="merge_items",
                before=left_items,
                after=next_items,
            )
        )
        left_items = next_items

    while len(right_items) > TWO_COLUMNS_TARGET:
        next_items = _merge_items(right_items, len(right_items) - 1, BULLET_LIMIT)
        if next_items == right_items:
            break
        actions.append(
            RewriteAction(
                slide_id=slide["slide_id"],
                field="right.items",
                action="merge_items",
                before=right_items,
                after=next_items,
            )
        )
        right_items = next_items

    while abs(len(left_items) - len(right_items)) > 3:
        if len(left_items) > len(right_items):
            next_items = _merge_items(left_items, len(left_items) - 1, BULLET_LIMIT)
            if next_items == left_items:
                break
            actions.append(
                RewriteAction(
                    slide_id=slide["slide_id"],
                    field="left.items",
                    action="rebalance_items",
                    before=left_items,
                    after=next_items,
                )
            )
            left_items = next_items
        else:
            next_items = _merge_items(right_items, len(right_items) - 1, BULLET_LIMIT)
            if next_items == right_items:
                break
            actions.append(
                RewriteAction(
                    slide_id=slide["slide_id"],
                    field="right.items",
                    action="rebalance_items",
                    before=right_items,
                    after=next_items,
                )
            )
            right_items = next_items

    left["items"] = left_items
    right["items"] = right_items
    updated["left"] = left
    updated["right"] = right
    return updated


def rewrite_slide(slide_data: dict[str, Any], issues: list[ContentWarning]) -> tuple[dict[str, Any], tuple[RewriteAction, ...]]:
    updated = dict(slide_data)
    actions: list[RewriteAction] = []
    issue_messages = [issue.message for issue in issues]
    layout = updated.get("layout", "")
    slide_id = str(updated.get("slide_id", "unknown"))

    if any(
        any(
            token in message
            for token in (
                "title contains",
                DIRECTORY_STYLE_WARNING,
                GENERIC_OPENING_WARNING,
                GENERIC_CLOSING_WARNING,
                LAST_SLIDE_ACTION_WARNING,
                REPEATED_TITLE_WARNING,
            )
        )
        for message in issue_messages
    ):
        updated["title"] = _rewrite_title(updated, issue_messages, actions)
        _refine_title_related_content(updated, actions)

    if layout == "title_content":
        content = list(updated.get("content", []))
        if any("bullet" in message for message in issue_messages):
            updated["content"] = _rewrite_content_items(
                slide_id,
                content,
                max_length=BULLET_LIMIT,
                target_count=TITLE_CONTENT_TARGET,
                actions=actions,
                field="content",
            )
    elif layout == "title_image":
        content = list(updated.get("content", []))
        if any("title_image has" in message or "title_image content" in message for message in issue_messages):
            updated["content"] = _rewrite_content_items(
                slide_id,
                content,
                max_length=BULLET_LIMIT,
                target_count=TITLE_IMAGE_TARGET,
                actions=actions,
                field="content",
            )
    elif layout == "two_columns":
        if any("column has" in message or "item count gap" in message for message in issue_messages):
            updated = _rewrite_two_columns(updated, actions)

    return updated, tuple(actions)


def rewrite_deck(
    validated_deck: ValidatedDeck | None,
    quality_result: QualityGateResult,
) -> RewriteDeckResult:
    if validated_deck is None:
        return RewriteDeckResult(
            attempted=False,
            applied=False,
            validated_deck=None,
            initial_quality_gate=quality_result,
            final_quality_gate=quality_result,
            notes=("schema validation failed; rewrite skipped",),
        )

    issues_by_slide = _group_issues_by_slide(quality_result.all_issues())
    if not issues_by_slide:
        return RewriteDeckResult(
            attempted=False,
            applied=False,
            validated_deck=validated_deck,
            initial_quality_gate=quality_result,
            final_quality_gate=quality_result,
            notes=("no fixable quality issues found",),
        )

    payload = validated_deck.deck.model_dump(mode="json")
    language = str(payload.get("meta", {}).get("language", "zh-CN"))
    slide_actions: list[RewriteAction] = []
    rewritten_slides: list[dict[str, Any]] = []

    for slide in payload["slides"]:
        slide_id = str(slide.get("slide_id", ""))
        if slide_id not in issues_by_slide:
            rewritten_slides.append(slide)
            continue
        rewritten_slide, actions = rewrite_slide(slide, issues_by_slide[slide_id])
        slide_actions.extend(actions)
        rewritten_slides.append(rewritten_slide)

    last_index = len(rewritten_slides) - 1
    for index, slide in enumerate(rewritten_slides):
        slide_id = str(slide.get("slide_id", ""))
        issue_messages = [issue.message for issue in issues_by_slide.get(slide_id, [])]
        if index == last_index and index > 0 and any(
            token in message for message in issue_messages for token in (GENERIC_CLOSING_WARNING, LAST_SLIDE_ACTION_WARNING)
        ):
            rewritten_slide = _rewrite_last_slide_with_context(
                rewritten_slides[index - 1],
                slide,
                issue_messages,
                slide_actions,
                language=language,
            )
            rewritten_slides[index] = rewritten_slide
            slide = rewritten_slide
        if index > 0 and any(REPEATED_ADJACENT_WARNING in message for message in issue_messages):
            rewritten_slide = _remove_adjacent_repeated_content(rewritten_slides[index - 1], slide, slide_actions)
            rewritten_slides[index] = rewritten_slide

    if not slide_actions:
        return RewriteDeckResult(
            attempted=True,
            applied=False,
            validated_deck=validated_deck,
            initial_quality_gate=quality_result,
            final_quality_gate=quality_result,
            notes=("fixable issues were detected but no safe rewrite was produced",),
        )

    rewritten_payload = {"meta": payload["meta"], "slides": rewritten_slides}
    rewritten_validated = validate_deck_payload(rewritten_payload)
    final_quality = quality_gate(rewritten_validated)
    if final_quality.summary["high_count"] > 0 or final_quality.summary["error_count"] > 0:
        final_quality = replace(final_quality, review_required=True)

    return RewriteDeckResult(
        attempted=True,
        applied=True,
        validated_deck=rewritten_validated,
        initial_quality_gate=quality_result,
        final_quality_gate=final_quality,
        actions=tuple(slide_actions),
        notes=("rewrite pass completed",),
    )


def write_rewrite_log(result: RewriteDeckResult, output_path: str | Path) -> Path:
    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target_path
