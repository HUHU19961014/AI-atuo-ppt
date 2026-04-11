from __future__ import annotations

from html import escape

from .visual_spec import VisualComponent, VisualSpec


def _find_first(components: list[VisualComponent], component_type: str) -> VisualComponent | None:
    for component in components:
        if component.type == component_type:
            return component
    return None


def _find_all(components: list[VisualComponent], component_type: str) -> list[VisualComponent]:
    return [component for component in components if component.type == component_type]


def _card_html(component: VisualComponent, role: str) -> str:
    label = f'<p class="label">{escape(component.label)}</p>' if component.label else ""
    value = f'<p class="value">{escape(component.value)}</p>' if component.value else ""
    text = f'<p class="text">{escape(component.text)}</p>' if component.text else ""
    detail = f'<p class="detail">{escape(component.detail)}</p>' if component.detail else ""
    return f'<article class="card" data-role="{role}">{label}{value}{text}{detail}</article>'


def _render_sales_proof(spec: VisualSpec) -> str:
    hero = _find_first(spec.components, "hero_claim")
    cards = _find_all(spec.components, "proof_card")[:4]
    hero_text = escape(hero.text) if hero else ""
    cards_html = "".join(_card_html(card, "proof-card") for card in cards)
    return (
        f'<div class="hero-claim" data-role="main-claim">{hero_text}</div>'
        f'<div class="cards-grid" data-role="proof-grid">{cards_html}</div>'
    )


def _render_risk_to_value(spec: VisualSpec) -> str:
    hero = _find_first(spec.components, "hero_claim")
    risks = _find_all(spec.components, "risk_card")[:4]
    proofs = _find_all(spec.components, "proof_card")[:4]
    left_html = "".join(_card_html(card, "risk-card") for card in risks)
    right_html = "".join(_card_html(card, "proof-card") for card in proofs)
    hero_text = escape(hero.text) if hero else ""
    return (
        '<div class="three-col">'
        f'<div class="col risk" data-role="risk-col">{left_html}</div>'
        f'<div class="col center"><div class="hero-claim" data-role="main-claim">{hero_text}</div></div>'
        f'<div class="col value" data-role="value-col">{right_html}</div>'
        "</div>"
    )


def _render_executive_summary(spec: VisualSpec) -> str:
    hero = _find_first(spec.components, "hero_claim")
    cards = _find_all(spec.components, "proof_card")[:4]
    band = _find_first(spec.components, "value_band")
    hero_text = escape(hero.text) if hero else ""
    cards_html = "".join(_card_html(card, "proof-card") for card in cards)
    band_html = f'<div class="value-band" data-role="value-band">{escape(band.text)}</div>' if band else ""
    return (
        f'<div class="hero-claim" data-role="main-claim">{hero_text}</div>'
        f'<div class="metrics-row" data-role="metrics-row">{cards_html}</div>'
        f"{band_html}"
    )


def render_visual_spec_to_html(spec: VisualSpec) -> str:
    headline = _find_first(spec.components, "headline")
    subheadline = _find_first(spec.components, "subheadline")
    footer_note = _find_first(spec.components, "footer_note")
    body_html = {
        "sales_proof": _render_sales_proof,
        "risk_to_value": _render_risk_to_value,
        "executive_summary": _render_executive_summary,
    }[spec.layout.type](spec)

    title_html = escape(headline.text) if headline else escape(spec.slide_id)
    subtitle_html = (
        f'<p class="subtitle" data-role="subtitle">{escape(subheadline.text)}</p>' if subheadline else ""
    )
    footer_html = (
        f'<footer class="slide-footer" data-role="footer-note">{escape(footer_note.text)}</footer>'
        if footer_note
        else ""
    )
    return (
        "<!doctype html>"
        '<html lang="zh-CN"><head><meta charset="utf-8"><title>Visual Draft</title>'
        "<style>"
        "html,body{margin:0;padding:0;background:#E9EEF2;font-family:'Microsoft YaHei',sans-serif;}"
        ".slide{width:1280px;height:720px;overflow: hidden;box-sizing:border-box;background:#FFFFFF;color:#1F2933;"
        "position:relative;border:1px solid #DDE4EA;}"
        ".sie-header{height:92px;padding:28px 72px 16px 72px;border-bottom:1px solid #E6EBF0;display:flex;"
        "align-items:flex-start;justify-content:space-between;}"
        ".sie-header h1{margin:0;font-size:36px;line-height:1.2;font-weight:700;color:#1F2933;}"
        ".subtitle{margin:10px 0 0 0;font-size:20px;line-height:1.35;color:#52616B;}"
        ".logo{font-size:20px;font-weight:700;color:#AD053D;}"
        ".slide-body{position:absolute;left:72px;right:72px;top:108px;bottom:54px;display:flex;flex-direction:column;"
        "gap:18px;box-sizing:border-box;}"
        ".hero-claim{font-size:34px;line-height:1.2;font-weight:700;color:#AD053D;}"
        ".cards-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;}"
        ".card{background:#F5F7FA;border:1px solid #E3EAF1;border-radius:6px;padding:12px 14px;}"
        ".card .label{margin:0 0 6px 0;color:#52616B;font-size:16px;line-height:1.3;}"
        ".card .value{margin:0 0 6px 0;color:#1F2933;font-size:22px;line-height:1.2;font-weight:700;}"
        ".card .text,.card .detail{margin:0;color:#52616B;font-size:16px;line-height:1.35;}"
        ".three-col{display:grid;grid-template-columns:1fr 1.15fr 1fr;gap:14px;height:100%;}"
        ".three-col .col{display:flex;flex-direction:column;gap:10px;}"
        ".three-col .center{justify-content:center;padding:0 8px;}"
        ".metrics-row{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;}"
        ".value-band{margin-top:auto;background:#AD053D;color:#FFFFFF;padding:12px 16px;border-radius:6px;"
        "font-size:20px;line-height:1.3;font-weight:600;}"
        ".slide-footer{position:absolute;left:72px;right:72px;bottom:18px;color:#52616B;font-size:16px;line-height:1.3;}"
        "</style></head><body>"
        f'<section class="slide" data-layout="{escape(spec.layout.type)}" data-template="{escape(spec.brand.template)}">'
        '<header class="sie-header"><div><h1 data-role="title">'
        f"{title_html}</h1>{subtitle_html}</div>"
        '<div class="logo" data-role="logo">SiE 赛意</div></header>'
        f'<main class="slide-body">{body_html}</main>{footer_html}</section></body></html>'
    )
