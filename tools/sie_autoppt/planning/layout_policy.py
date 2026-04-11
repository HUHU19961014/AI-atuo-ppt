from __future__ import annotations

from dataclasses import dataclass, field

from .content_profiler import ContentProfile


@dataclass(frozen=True)
class LayoutDecision:
    pattern_id: str
    layout_variant: str | None
    max_items_per_page: int
    layout_hints: dict[str, object] = field(default_factory=dict)


DEFAULT_ITEM_COUNTS = (3, 5, 9)


def choose_capacity(content_profile: ContentProfile, preferred_item_counts: tuple[int, ...] = DEFAULT_ITEM_COUNTS) -> int:
    counts = tuple(sorted(preferred_item_counts or DEFAULT_ITEM_COUNTS))
    if content_profile.item_count <= counts[0]:
        capacity = counts[0]
    elif content_profile.item_count <= counts[1]:
        capacity = counts[1]
    else:
        capacity = counts[-1]

    if content_profile.density == "dense" or content_profile.has_long_item:
        if capacity >= counts[-1] and len(counts) >= 2:
            capacity = counts[1]
        elif capacity >= counts[1]:
            capacity = counts[0]
    return capacity


def decide_layout_variant(
    pattern_id: str,
    capacity: int,
    pattern_variants: dict[str, tuple[dict[str, object], ...]] | None = None,
) -> str | None:
    if not pattern_variants:
        return None
    for variant in pattern_variants.get(pattern_id, ()):
        if int(variant.get("capacity", 0)) == int(capacity):
            return str(variant["id"])
    return None


def resolve_layout_decision(
    *,
    requested_pattern_id: str,
    fallback_pattern_id: str,
    content_profile: ContentProfile,
    preferred_item_counts: tuple[int, ...] = DEFAULT_ITEM_COUNTS,
    available_layout_variants: set[str] | None = None,
    pattern_variants: dict[str, tuple[dict[str, object], ...]] | None = None,
) -> LayoutDecision:
    pattern_id = requested_pattern_id or fallback_pattern_id
    capacity = choose_capacity(content_profile, preferred_item_counts=preferred_item_counts)
    desired_layout_variant = decide_layout_variant(pattern_id, capacity, pattern_variants=pattern_variants)
    resolved_layout_variant = desired_layout_variant
    if desired_layout_variant and available_layout_variants is not None and desired_layout_variant not in available_layout_variants:
        resolved_layout_variant = None
    return LayoutDecision(
        pattern_id=pattern_id,
        layout_variant=resolved_layout_variant,
        max_items_per_page=capacity,
        layout_hints={
            "density": content_profile.density,
            "item_count": content_profile.item_count,
            "avg_chars": content_profile.avg_chars,
            "max_chars": content_profile.max_chars,
            "desired_capacity": capacity,
            "desired_layout_variant": desired_layout_variant or "",
        },
    )
