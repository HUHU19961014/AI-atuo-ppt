from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import BodyPageSpec, DeckSpec
from .visual_html_renderer import render_visual_spec_to_html
from .visual_rule_config import VisualRuleConfig, load_visual_rule_config_from_path
from .visual_score import review_visual_draft_with_ai, score_visual_draft
from .visual_screenshot import capture_html_screenshot
from .visual_spec import VisualComponent, VisualIntent, VisualLayout, VisualSpec

RISK_KEYWORDS = (
    "risk",
    "audit",
    "compliance risk",
    "\u98ce\u9669",
    "\u5ba1\u8ba1",
    "\u4e0d\u5408\u89c4",
    "\u6574\u6539",
    "\u5904\u7f5a",
)
PROOF_PATTERN_IDS = {"claim_breakdown", "kpi_dashboard", "comparison_upgrade"}


@dataclass(frozen=True)
class VisualDraftArtifacts:
    visual_spec_path: Path
    preview_html_path: Path
    preview_png_path: Path
    visual_score_path: Path
    ai_review_path: Path
    rule_score: dict[str, Any]
    ai_review: dict[str, Any]


def _contains_risk_language(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in RISK_KEYWORDS)


def _join_payload_text(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _choose_layout(page: BodyPageSpec, layout_hint: str) -> str:
    if layout_hint and layout_hint != "auto":
        return layout_hint
    merged_text = " ".join([page.title, page.subtitle, *page.bullets, _join_payload_text(dict(page.payload))]).strip()
    if _contains_risk_language(merged_text):
        return "risk_to_value"
    payload = dict(page.payload)
    if page.pattern_id in PROOF_PATTERN_IDS or any(key in payload for key in ("claims", "metrics", "left_cards", "right_cards")):
        return "sales_proof"
    return "executive_summary"


def _extract_cards_from_payload(payload: dict[str, object], key: str) -> list[dict[str, str]]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        return []
    cards: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        cards.append(
            {
                "label": str(item.get("label") or item.get("title") or "").strip(),
                "value": str(item.get("value") or "").strip(),
                "detail": str(item.get("detail") or "").strip(),
            }
        )
    return cards


def build_visual_spec_from_deck_spec(deck_spec: DeckSpec, page_index: int = 0, layout_hint: str = "auto") -> VisualSpec:
    if page_index < 0 or page_index >= len(deck_spec.body_pages):
        raise ValueError(f"page_index {page_index} out of range for {len(deck_spec.body_pages)} pages")
    page = deck_spec.body_pages[page_index]
    payload = dict(page.payload)
    layout_type = _choose_layout(page, layout_hint)
    components: list[VisualComponent] = [VisualComponent(type="headline", text=page.title)]
    subheadline_text = page.subtitle.strip() or str(payload.get("headline") or "").strip()
    if subheadline_text:
        components.append(VisualComponent(type="subheadline", text=subheadline_text))

    hero_text = (
        str(payload.get("summary") or "").strip()
        or (page.bullets[0].strip() if page.bullets else page.title)
    )
    components.append(VisualComponent(type="hero_claim", text=hero_text))

    cards = (
        _extract_cards_from_payload(payload, "claims")
        + _extract_cards_from_payload(payload, "metrics")
        + _extract_cards_from_payload(payload, "cards")
        + _extract_cards_from_payload(payload, "items")
        + _extract_cards_from_payload(payload, "left_cards")
        + _extract_cards_from_payload(payload, "right_cards")
    )
    if not cards:
        for bullet in page.bullets[:4]:
            cards.append({"label": "", "value": bullet.strip(), "detail": ""})

    for card in cards[:4]:
        card_type = "risk_card" if _contains_risk_language(" ".join(card.values())) else "proof_card"
        components.append(
            VisualComponent(
                type=card_type,
                label=card["label"],
                value=card["value"],
                detail=card["detail"],
            )
        )

    # Risk bullets should be reflected explicitly as risk cards.
    risk_bullets = [bullet.strip() for bullet in page.bullets if _contains_risk_language(bullet)]
    existing_risk_card_count = sum(1 for component in components if component.type == "risk_card")
    for bullet in risk_bullets[: max(0, 4 - existing_risk_card_count)]:
        components.append(VisualComponent(type="risk_card", text=bullet))

    value_band_text = str(payload.get("footer") or payload.get("footer_text") or payload.get("bottom_banner") or "").strip()
    if not value_band_text and len(page.bullets) >= 2:
        value_band_text = page.bullets[-1]
    if value_band_text:
        components.append(VisualComponent(type="value_band", text=value_band_text))
    if page.nav_title:
        components.append(VisualComponent(type="footer_note", text=page.nav_title))

    return VisualSpec(
        slide_id=page.page_key or f"page_{page_index + 1}",
        layout=VisualLayout(type=layout_type),
        intent=VisualIntent(core_message=hero_text),
        components=components,
    )


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _apply_simple_fixes(spec: VisualSpec, fixes: list[str]) -> VisualSpec:
    updated_components = list(spec.components)
    combined = " ".join(fixes).lower()
    if "reduce proof cards" in combined or "过密" in combined:
        proof_seen = 0
        clipped: list[VisualComponent] = []
        for component in updated_components:
            if component.type == "proof_card":
                proof_seen += 1
                if proof_seen > 3:
                    continue
            clipped.append(component)
        updated_components = clipped
    if "increase contrast" in combined or "主张" in combined:
        for index, component in enumerate(updated_components):
            if component.type == "hero_claim":
                updated_components[index] = VisualComponent(
                    type=component.type,
                    role=component.role,
                    text=f"{component.text}（核心结论）",
                    label=component.label,
                    value=component.value,
                    detail=component.detail,
                )
                break
    return VisualSpec(
        schema_version=spec.schema_version,
        slide_id=spec.slide_id,
        canvas=spec.canvas,
        brand=spec.brand,
        intent=spec.intent,
        layout=spec.layout,
        components=updated_components,
    )


def _copy_if_needed(src: Path, dst: Path) -> None:
    if src.resolve() == dst.resolve():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _run_single_round(
    *,
    spec: VisualSpec,
    output_dir: Path,
    stem: str,
    browser_path: str,
    model: str,
    with_ai_review: bool,
    rule_config: VisualRuleConfig,
) -> tuple[Path, Path, Path, Path, Path, dict[str, Any], dict[str, Any], VisualSpec]:
    visual_spec_path = _write_json(output_dir / f"{stem}.visual_spec.json", spec.to_dict())
    html_path = output_dir / f"{stem}.preview.html"
    html_content = render_visual_spec_to_html(spec)
    html_path.write_text(html_content, encoding="utf-8")
    png_path = output_dir / f"{stem}.preview.png"
    capture_html_screenshot(
        html_path=html_path,
        screenshot_path=png_path,
        width=1280,
        height=720,
        browser_path=browser_path,
    )
    rule_score_result = score_visual_draft(spec, html_content, png_path, rule_config=rule_config)
    if hasattr(rule_score_result, "to_dict"):
        rule_score = rule_score_result.to_dict()
    elif isinstance(rule_score_result, dict):
        rule_score = dict(rule_score_result)
    else:
        rule_score = {"score": int(getattr(rule_score_result, "score", 0)), "level": str(getattr(rule_score_result, "level", "")), "issues": list(getattr(rule_score_result, "issues", []))}

    ai_review: dict[str, Any]
    if with_ai_review:
        try:
            ai_review_result = review_visual_draft_with_ai(spec, html_path, png_path, model=model)
            if hasattr(ai_review_result, "to_dict"):
                ai_review = ai_review_result.to_dict()
            elif isinstance(ai_review_result, dict):
                ai_review = dict(ai_review_result)
            else:
                ai_review = {
                    "score": int(getattr(ai_review_result, "score", 0)),
                    "decision": str(getattr(ai_review_result, "decision", "")),
                    "summary": str(getattr(ai_review_result, "summary", "")),
                    "strengths": list(getattr(ai_review_result, "strengths", [])),
                    "issues": list(getattr(ai_review_result, "issues", [])),
                    "fixes": list(getattr(ai_review_result, "fixes", [])),
                }
            ai_review["status"] = "ok"
        except Exception as exc:
            ai_review = {
                "status": "failed",
                "score": 0,
                "decision": "unavailable",
                "summary": "AI visual review unavailable; rule score still generated.",
                "strengths": [],
                "issues": [str(exc)],
                "fixes": [],
            }
    else:
        ai_review = {
            "status": "skipped",
            "score": 0,
            "decision": "skipped",
            "summary": "AI visual review skipped. Enable --with-ai-review to run model-based review.",
            "strengths": [],
            "issues": [],
            "fixes": [],
        }
    visual_score_path = _write_json(output_dir / f"{stem}.visual_score.json", rule_score)
    ai_review_path = _write_json(output_dir / f"{stem}.ai_visual_review.json", ai_review)
    return visual_spec_path, html_path, png_path, visual_score_path, ai_review_path, rule_score, ai_review, spec


def generate_visual_draft_artifacts(
    *,
    deck_spec: DeckSpec,
    output_dir: Path,
    output_name: str,
    browser_path: str = "",
    model: str = "",
    page_index: int = 0,
    layout_hint: str = "auto",
    with_ai_review: bool = False,
    visual_rules_path: str = "",
) -> VisualDraftArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    rule_config = load_visual_rule_config_from_path(visual_rules_path)
    first_spec = build_visual_spec_from_deck_spec(deck_spec, page_index=page_index, layout_hint=layout_hint)
    (
        visual_spec_path,
        preview_html_path,
        preview_png_path,
        visual_score_path,
        ai_review_path,
        rule_score,
        ai_review,
        active_spec,
    ) = _run_single_round(
        spec=first_spec,
        output_dir=output_dir,
        stem=output_name,
        browser_path=browser_path,
        model=model,
        with_ai_review=with_ai_review,
        rule_config=rule_config,
    )

    if int(rule_score.get("score", 0)) < rule_config.scoring.auto_revise_threshold and not with_ai_review:
        raise RuntimeError(
            f"visual-draft score is below {rule_config.scoring.auto_revise_threshold}; "
            "enable --with-ai-review for one auto-revision round."
        )

    if int(rule_score.get("score", 0)) < rule_config.scoring.auto_revise_threshold and with_ai_review:
        round2_spec = _apply_simple_fixes(active_spec, list(ai_review.get("fixes", [])))
        (
            visual_spec_path,
            preview_html_path,
            preview_png_path,
            visual_score_path,
            ai_review_path,
            rule_score,
            ai_review,
            _,
        ) = _run_single_round(
            spec=round2_spec,
            output_dir=output_dir,
            stem=f"{output_name}.round2",
            browser_path=browser_path,
            model=model,
            with_ai_review=with_ai_review,
            rule_config=rule_config,
        )

        _copy_if_needed(visual_spec_path, output_dir / f"{output_name}.visual_spec.json")
        _copy_if_needed(preview_html_path, output_dir / f"{output_name}.preview.html")
        _copy_if_needed(preview_png_path, output_dir / f"{output_name}.preview.png")
        _copy_if_needed(visual_score_path, output_dir / f"{output_name}.visual_score.json")
        _copy_if_needed(ai_review_path, output_dir / f"{output_name}.ai_visual_review.json")

        if int(rule_score.get("score", 0)) < rule_config.scoring.auto_revise_threshold:
            raise RuntimeError(
                f"visual-draft score is still below {rule_config.scoring.auto_revise_threshold} after round2 iteration."
            )

        return VisualDraftArtifacts(
            visual_spec_path=output_dir / f"{output_name}.visual_spec.json",
            preview_html_path=output_dir / f"{output_name}.preview.html",
            preview_png_path=output_dir / f"{output_name}.preview.png",
            visual_score_path=output_dir / f"{output_name}.visual_score.json",
            ai_review_path=output_dir / f"{output_name}.ai_visual_review.json",
            rule_score=rule_score,
            ai_review=ai_review,
        )

    return VisualDraftArtifacts(
        visual_spec_path=visual_spec_path,
        preview_html_path=preview_html_path,
        preview_png_path=preview_png_path,
        visual_score_path=visual_score_path,
        ai_review_path=ai_review_path,
        rule_score=rule_score,
        ai_review=ai_review,
    )
