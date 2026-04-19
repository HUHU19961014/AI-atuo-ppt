from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ...config import PROJECT_ROOT


@dataclass(frozen=True)
class TemplateDescriptor:
    template_id: str
    content_type: str
    template_path: str
    styles: tuple[str, ...]
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class TemplateIndex:
    templates: tuple[TemplateDescriptor, ...]

    def filter_by_type(self, content_type: str) -> tuple[TemplateDescriptor, ...]:
        normalized = str(content_type or "").strip().lower()
        return tuple(item for item in self.templates if item.content_type == normalized)


def _infer_content_type(template_key: str, keywords: tuple[str, ...]) -> str:
    key = template_key.lower()
    keywords_blob = " ".join(keywords).lower()
    if "timeline" in key or "roadmap" in key:
        return "timeline"
    if "comparison" in key or "pros_cons" in key or "butterfly" in key:
        return "comparison"
    if "matrix" in key:
        return "matrix"
    if "kpi" in key or "gauge" in key or "bullet_chart" in key:
        return "stats"
    if "image" in key or "icon_grid" in key:
        return "image_grid"
    if "cards" in key or "vertical_list" in key:
        return "cards"
    if "timeline" in keywords_blob or "milestone" in keywords_blob:
        return "timeline"
    if "comparison" in keywords_blob:
        return "comparison"
    return "chart"


def _infer_styles(content_type: str) -> tuple[str, ...]:
    if content_type in {"timeline", "process"}:
        return ("standard", "decorative")
    if content_type in {"comparison", "matrix", "stats"}:
        return ("minimal", "standard")
    if content_type in {"image_grid", "cards"}:
        return ("standard", "decorative")
    return ("minimal", "standard", "decorative")


def _charts_index_path() -> Path:
    return PROJECT_ROOT / "projects" / "ppt-master" / "skills" / "ppt-master" / "templates" / "charts" / "charts_index.json"


def _layouts_index_path() -> Path:
    return PROJECT_ROOT / "projects" / "ppt-master" / "skills" / "ppt-master" / "templates" / "layouts" / "layouts_index.json"


def _infer_layout_content_type(layout_id: str, summary: str, keywords: tuple[str, ...]) -> str:
    blob = f"{layout_id} {summary} {' '.join(keywords)}".lower()
    if "timeline" in blob or "roadmap" in blob:
        return "timeline"
    if "comparison" in blob:
        return "comparison"
    if "matrix" in blob or "quadrant" in blob:
        return "matrix"
    if "dashboard" in blob or "kpi" in blob:
        return "stats"
    if "image" in blob or "photo" in blob:
        return "image_grid"
    if "card" in blob:
        return "cards"
    return "chart"


def _build_builtin_fallback_templates() -> list[TemplateDescriptor]:
    templates: list[TemplateDescriptor] = []
    seed: list[tuple[str, str]] = [
        ("timeline", "timeline"),
        ("comparison", "comparison"),
        ("matrix", "matrix"),
        ("stats", "stats"),
        ("image_grid", "image_grid"),
        ("cards", "cards"),
        ("chart", "chart"),
    ]
    for index in range(1, 43):
        content_type, keyword = seed[(index - 1) % len(seed)]
        template_id = f"builtin::{content_type}_{index:02d}"
        if index % 2 == 0:
            template_path = f"projects/ppt-master/skills/ppt-master/templates/layouts/{content_type}_{index:02d}"
        else:
            template_path = f"projects/ppt-master/skills/ppt-master/templates/charts/{content_type}_{index:02d}.svg"
        templates.append(
            TemplateDescriptor(
                template_id=template_id,
                content_type=content_type,
                template_path=template_path,
                styles=_infer_styles(content_type),
                keywords=(keyword, "builtin", "fallback"),
            )
        )
    return templates


@lru_cache(maxsize=1)
def build_default_template_index() -> TemplateIndex:
    charts_index = _charts_index_path()

    templates: list[TemplateDescriptor] = []
    if charts_index.exists():
        payload = json.loads(charts_index.read_text(encoding="utf-8"))
        charts = payload.get("charts", {})
        if isinstance(charts, dict):
            for key, item in charts.items():
                if not isinstance(item, dict):
                    continue
                template_id = str(key).strip()
                keywords_raw = item.get("keywords", [])
                keywords: list[str] = []
                if isinstance(keywords_raw, list):
                    keywords = [str(word).strip().lower() for word in keywords_raw if str(word).strip()]
                content_type = _infer_content_type(template_id, tuple(keywords))
                templates.append(
                    TemplateDescriptor(
                        template_id=template_id,
                        content_type=content_type,
                        template_path=f"projects/ppt-master/skills/ppt-master/templates/charts/{template_id}.svg",
                        styles=_infer_styles(content_type),
                        keywords=tuple(keywords),
                    )
                )

    layouts_index = _layouts_index_path()
    if layouts_index.exists():
        payload = json.loads(layouts_index.read_text(encoding="utf-8"))
        layouts = payload.get("layouts", {})
        if isinstance(layouts, dict):
            for key, item in layouts.items():
                if not isinstance(item, dict):
                    continue
                layout_id = str(key).strip()
                summary = str(item.get("summary", "")).strip()
                keywords_raw = item.get("keywords", [])
                layout_keywords: list[str] = []
                if isinstance(keywords_raw, list):
                    layout_keywords = [str(word).strip().lower() for word in keywords_raw if str(word).strip()]
                content_type = _infer_layout_content_type(layout_id, summary, tuple(layout_keywords))
                templates.append(
                    TemplateDescriptor(
                        template_id=f"layout::{layout_id}",
                        content_type=content_type,
                        template_path=f"projects/ppt-master/skills/ppt-master/templates/layouts/{layout_id}",
                        styles=_infer_styles(content_type),
                        keywords=tuple(layout_keywords),
                    )
                )

    if not templates:
        templates = _build_builtin_fallback_templates()
    return TemplateIndex(templates=tuple(templates))
