from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..llm_openai import OpenAIResponsesClient, load_openai_responses_config
from ..plugins import resolve_model_adapter
from .io import is_semantic_deck_document, load_deck_document, load_semantic_document, write_deck_document, write_semantic_document
from .ppt_engine import RenderArtifacts, generate_ppt
from .quality_checks import QualityGateResult, quality_gate
from .schema import DeckDocument, validate_deck_payload

try:
    from jsonpath_ng.ext import parse as jsonpath_parse
except Exception:  # pragma: no cover - optional dependency fallback
    jsonpath_parse = None

RATING_LABELS = ("优秀", "合格", "可用初稿", "质量偏弱", "不合格")


@dataclass(frozen=True)
class ReviewDimensionDefinition:
    key: str
    label: str
    description: str
    high_score: str
    low_score: str


BASELINE_REVIEW_DIMENSIONS = (
    ReviewDimensionDefinition("structure", "结构完整性", "结构与页数合理性、节奏自然度", "结构成熟、节奏自然、适合正式汇报", "结构混乱、页数明显失衡"),
    ReviewDimensionDefinition("title_quality", "标题质量", "标题是否结论导向、自然、非目录化", "标题结论导向明确，中文 <= 20 字", "多数标题像机器生成，或大量目录化措辞"),
    ReviewDimensionDefinition("content_density", "内容密度", "内容密度与表达质量", "每页通常 3-4 条 bullet，精炼，支持高效汇报", "内容过密或过疏，阅读负担重"),
    ReviewDimensionDefinition("layout_stability", "布局稳定性", "版式稳定性与溢出风险", "无明显溢出、压叠、错位", "多页明显异常，无法交付"),
    ReviewDimensionDefinition("deliverability", "可交付性", "整体是否达到交付水平", "基本达到正式交付水平", "需要大幅重写"),
)
EXTENDED_REVIEW_DIMENSIONS = BASELINE_REVIEW_DIMENSIONS + (
    ReviewDimensionDefinition("brand_consistency", "品牌一致性", "配色、字体、视觉语言是否统一", "配色字体符合主题规范，风格稳定", "风格混乱，像多套模板拼接"),
    ReviewDimensionDefinition("data_visualization", "数据可视化", "指标、图表、数据呈现是否清晰专业", "数据表达清楚，有来源意识，视觉编码恰当", "数据堆砌或图表含义不清"),
    ReviewDimensionDefinition("info_hierarchy", "信息层级", "重点、主次和阅读路径是否清晰", "核心信息突出，层级清楚", "信息层级模糊，读者难以抓重点"),
    ReviewDimensionDefinition("audience_fit", "受众适配", "内容深度、措辞和节奏是否适合目标受众", "符合目标受众阅读习惯和决策场景", "受众错配，体验差"),
)
VISUAL_REVIEW_DIMENSIONS = EXTENDED_REVIEW_DIMENSIONS
DEFAULT_PREVIEW_EXPORT_TIMEOUT_SEC = 120


class StructuredJsonProvider(Protocol):
    def create_structured_json_with_user_items(self, **kwargs) -> dict[str, Any]:
        ...


class OpenAIVisualReviewProvider:
    def __init__(self, model: str | None = None):
        adapter_name = str(
            os.environ.get("SIE_AUTOPPT_VISION_MODEL_ADAPTER", "") or os.environ.get("SIE_AUTOPPT_MODEL_ADAPTER", "")
        ).strip().lower()
        if adapter_name:
            adapter_factory = resolve_model_adapter(adapter_name)
            if adapter_factory is None:
                raise ValueError(f"Unknown model adapter for visual review: {adapter_name}")
            self.client = adapter_factory(model)
        else:
            self.client = OpenAIResponsesClient(load_openai_responses_config(model=model))

    def create_structured_json_with_user_items(self, **kwargs) -> dict[str, Any]:
        return self.client.create_structured_json_with_user_items(**kwargs)


def _build_review_scorecard_text(dimensions: tuple[ReviewDimensionDefinition, ...] = VISUAL_REVIEW_DIMENSIONS) -> str:
    lines = [f"请按以下 {len(dimensions)} 个维度对整套 PPT 进行评分，每项 1-5 分：", ""]
    for index, dimension in enumerate(dimensions, start=1):
        lines.extend(
            [
                f"{index}. {dimension.key}：{dimension.label}",
                f"- 评估重点：{dimension.description}",
                f"- 5分：{dimension.high_score}",
                f"- 1分：{dimension.low_score}",
                "",
            ]
        )
    lines.extend(
        [
            "视觉检查重点：",
            "- 文字是否溢出边界",
            "- 图文是否压叠",
            "- 字体是否过小（正文建议 >= 16pt）",
            "- 背景与文字对比度是否足够",
            "- 目录页序号/标题是否对齐",
            "",
            "输出 JSON 时必须：",
            f"- total 为 {len(dimensions)} 项分数求和",
            "- rating 仅允许：优秀 / 合格 / 可用初稿 / 质量偏弱 / 不合格",
            "- page_issues 只写具体页问题，page 从 1 开始",
            "- blocker 表示已经影响交付或必须进入自动修复",
            "- warning 表示仍可继续人工润色",
            "- summary 用 2-3 句中文概括整体判断",
        ]
    )
    return "\n".join(lines).strip()


REVIEW_SCORECARD_TEXT = _build_review_scorecard_text()
PATCH_WORKFLOW_TEXT = """
根据刚才的评审结果，请仅针对 blocker 级别的问题生成 DeckSpec JSON 修复 Patch。

要求：
- 每个 blocker 至少对应一个 patch 对象
- 优先使用最小可执行修改：标题改写、bullet 压缩、字段替换、布局字段调整
- field 使用 DeckSpec JSON 路径，例如 slides[2].title 或 slides[2].left.items[0]
- 不要为 warning 生成 patch
- 只输出符合 schema 的 JSON，不要附加解释
""".strip()
PREVIEW_EXPORT_FALLBACK_NOTE = (
    "未找到 LibreOffice/soffice，已跳过 PNG 预览导出；本次 review 仅基于 DeckSpec 内容，"
    "layout_stability 与 deliverability 的判断可靠性会降低。"
)


@dataclass(frozen=True)
class VisualReviewArtifacts:
    review_path: Path
    patch_path: Path
    deck_path: Path
    pptx_path: Path
    preview_dir: Path
    final_review_path: Path
    final_patch_path: Path
    semantic_source_path: Path | None = None
    preview_mode: str = "content_only"


@dataclass(frozen=True)
class SingleReviewArtifacts:
    review_path: Path
    patch_path: Path
    deck_path: Path
    pptx_path: Path
    preview_dir: Path
    semantic_source_path: Path | None = None
    preview_mode: str = "content_only"


def build_visual_review_schema(
    dimensions: tuple[ReviewDimensionDefinition, ...] = VISUAL_REVIEW_DIMENSIONS,
) -> dict[str, Any]:
    score_properties = {dimension.key: {"type": "integer", "minimum": 1, "maximum": 5} for dimension in dimensions}
    return {
        "type": "object",
        "properties": {
            "scores": {
                "type": "object",
                "properties": score_properties,
                "required": list(score_properties),
                "additionalProperties": False,
            },
            "total": {"type": "integer", "minimum": len(dimensions), "maximum": len(dimensions) * 5},
            "rating": {"type": "string", "enum": list(RATING_LABELS)},
            "page_issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer", "minimum": 1, "maximum": 50},
                        "level": {"type": "string", "enum": ["blocker", "warning"]},
                        "dimension": {"type": "string", "enum": [dimension.key for dimension in dimensions]},
                        "issue": {"type": "string", "minLength": 2, "maxLength": 120},
                        "suggestion": {"type": "string", "minLength": 2, "maxLength": 120},
                    },
                    "required": ["page", "level", "dimension", "issue", "suggestion"],
                    "additionalProperties": False,
                },
            },
            "summary": {"type": "string", "minLength": 8, "maxLength": 240},
        },
        "required": ["scores", "total", "rating", "page_issues", "summary"],
        "additionalProperties": False,
    }


def build_patch_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "patches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer", "minimum": 1, "maximum": 50},
                        "field": {"type": "string", "minLength": 4, "maxLength": 80},
                        "old_value": {"type": ["string", "number", "boolean", "null"]},
                        "new_value": {"type": ["string", "number", "boolean", "null"]},
                        "reason": {"type": "string", "minLength": 4, "maxLength": 160},
                    },
                    "required": ["page", "field", "old_value", "new_value", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["patches"],
        "additionalProperties": False,
    }


def _review_developer_prompt() -> str:
    return (
        "You are a strict PPT visual QA reviewer. "
        "You will receive DeckSpec JSON plus slide PNG previews in page order. "
        "Use the slide images as the primary source for layout_stability and overflow judgment. "
        "Do not only judge layout: also inspect narrative closure, evidence sufficiency, repeated pages, and whether the opening and ending pages are presentation-ready. "
        "You will also receive rule-based quality-gate findings; treat them as prior signals that must be checked, not ignored. "
        "Be conservative: only give 5 when the quality is clearly strong. "
        "Return only JSON that matches the schema.\n\n"
        + REVIEW_SCORECARD_TEXT
    )


def _patch_developer_prompt() -> str:
    return (
        "You are a PPT repair planner. "
        "Given a DeckSpec JSON plus a visual review result JSON, output minimal JSON patches only for blocker-level issues. "
        "Prefer content shortening, title rewriting, bullet trimming, and layout field changes that can be applied directly to the deck JSON. "
        "Use field paths like slides[2].title, slides[2].content[1], slides[2].left.items[0]. "
        "Return only JSON matching the schema.\n\n"
        + PATCH_WORKFLOW_TEXT
    )


def _score_rating(total: int, *, max_score: int = 25) -> str:
    ratio = total / max(max_score, 1)
    if ratio >= 0.84:
        return "优秀"
    if ratio >= 0.64:
        return "合格"
    if ratio >= 0.44:
        return "可用初稿"
    if ratio >= 0.24:
        return "质量偏弱"
    return "不合格"


def export_slide_previews(pptx_path: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    system = platform.system().lower()
    if system == "windows":
        script = (
            "$pptPath = Resolve-Path $args[0];"
            "$outDir = $args[1];"
            "New-Item -ItemType Directory -Path $outDir -Force | Out-Null;"
            "$ppt = New-Object -ComObject PowerPoint.Application;"
            "$ppt.Visible = -1;"
            "$pres = $ppt.Presentations.Open($pptPath.Path, $false, $false, $false);"
            "$idx = 1;"
            "foreach ($slide in $pres.Slides) {"
            "  $target = Join-Path $outDir ('slide' + $idx + '.png');"
            "  $slide.Export($target, 'PNG', 1920, 1080);"
            "  $idx += 1"
            "};"
            "$pres.Close();"
            "$ppt.Quit();"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script, str(pptx_path), str(output_dir)],
                text=True,
                capture_output=True,
                check=False,
                timeout=DEFAULT_PREVIEW_EXPORT_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Failed to export slide previews: timed out after {DEFAULT_PREVIEW_EXPORT_TIMEOUT_SEC}s") from exc
        if result.returncode != 0:
            raise RuntimeError(f"Failed to export slide previews: {(result.stderr or result.stdout).strip()}")
    else:
        if shutil.which("soffice") is None:
            return []
        try:
            result = subprocess.run(
                ["soffice", "--headless", "--convert-to", "png", "--outdir", str(output_dir), str(pptx_path)],
                text=True,
                capture_output=True,
                check=False,
                timeout=DEFAULT_PREVIEW_EXPORT_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Failed to export slide previews: timed out after {DEFAULT_PREVIEW_EXPORT_TIMEOUT_SEC}s") from exc
        if result.returncode != 0:
            raise RuntimeError(f"Failed to export slide previews: {(result.stderr or result.stdout).strip()}")

    previews = sorted(output_dir.glob("slide*.png"))
    if not previews:
        raise RuntimeError(f"No slide previews were generated for {pptx_path}")
    return previews


def _build_preview_fallback_note(reason: str | None = None) -> str:
    if not reason:
        return PREVIEW_EXPORT_FALLBACK_NOTE
    return f"{PREVIEW_EXPORT_FALLBACK_NOTE} 导出错误：{reason}"


def _safe_export_slide_previews(pptx_path: Path, output_dir: Path) -> tuple[list[Path], str | None]:
    try:
        previews = export_slide_previews(pptx_path, output_dir)
    except Exception as exc:
        return [], _build_preview_fallback_note(str(exc).strip())
    if previews:
        return previews, None
    return [], PREVIEW_EXPORT_FALLBACK_NOTE


def _merge_summary_note(summary: str, note: str | None, *, max_length: int = 240) -> str:
    summary_text = summary.strip()
    if not note:
        return summary_text
    merged = f"{summary_text} 注：{note}".strip() if summary_text else note
    if len(merged) <= max_length:
        return merged
    if not summary_text:
        return note[:max_length].rstrip()
    reserved = len(summary_text) + len(" 注：")
    if reserved >= max_length:
        return summary_text[:max_length].rstrip()
    return f"{summary_text} 注：{note[: max_length - reserved].rstrip()}"


def _resolve_preview_mode(previews: list[Path]) -> str:
    if not previews:
        return "content_only"
    return "powerpoint" if platform.system().lower() == "windows" else "soffice"


def _build_quality_gate_note(result: QualityGateResult, *, limit: int = 8) -> str:
    issues = list(result.all_issues())
    if not issues:
        return (
            "Rule-based quality gate found no issues. "
            f"auto_score={result.auto_score}, review_required={str(result.review_required).lower()}."
        )

    lines = [
        (
            "Rule-based quality gate findings "
            f"(warnings={result.summary['warning_count']}, high={result.summary['high_count']}, errors={result.summary['error_count']}, "
            f"auto_score={result.auto_score}, review_required={str(result.review_required).lower()}):"
        )
    ]
    for issue in issues[:limit]:
        lines.append(f"- [{issue.slide_id}] [{issue.warning_level}] {issue.message}")
    if len(issues) > limit:
        lines.append(f"- ... {len(issues) - limit} more issue(s)")
    return "\n".join(lines)


def _build_review_user_items(
    deck: DeckDocument,
    previews: list[Path],
    *,
    quality_gate_note: str,
    preview_note: str | None = None,
) -> list[dict[str, Any]]:
    preview_guidance = (
        "下面将按页码顺序提供 PNG 预览图。"
        if previews
        else "本次没有可用的 PNG 预览图，请基于 DeckSpec 内容评估结构、标题与内容，并对 layout_stability 与 deliverability 保守打分。"
    )
    note_text = f"\n\n注意：{preview_note}" if preview_note else ""
    items: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                f"请严格按照既定 {len(VISUAL_REVIEW_DIMENSIONS)} 维评分标准评审这套 PPT。下面先给出 DeckSpec JSON：\n"
                + json.dumps(deck.model_dump(mode="json"), ensure_ascii=False, indent=2)
                + "\n\n"
                + quality_gate_note
                + "\n\n"
                + preview_guidance
                + note_text
            ),
        }
    ]
    for index, preview in enumerate(previews, start=1):
        items.append({"type": "text", "text": f"第 {index} 页预览"})
        items.append({"type": "image_path", "path": str(preview)})
    return items


def _normalize_visual_scores(scores: Any) -> dict[str, int]:
    source = scores if isinstance(scores, dict) else {}
    normalized: dict[str, int] = {}
    for dimension in VISUAL_REVIEW_DIMENSIONS:
        try:
            value = int(source.get(dimension.key, 3))
        except (TypeError, ValueError):
            value = 3
        normalized[dimension.key] = min(5, max(1, value))
    return normalized


def review_rendered_deck(
    deck: DeckDocument,
    previews: list[Path],
    *,
    model: str | None = None,
    preview_note: str | None = None,
    provider: StructuredJsonProvider | None = None,
) -> dict[str, Any]:
    active_provider = provider or OpenAIVisualReviewProvider(model=model)
    gate_result = quality_gate(deck)
    preview_mode = _resolve_preview_mode(previews)
    result = active_provider.create_structured_json_with_user_items(
        developer_prompt=_review_developer_prompt(),
        user_items=_build_review_user_items(
            deck,
            previews,
            quality_gate_note=_build_quality_gate_note(gate_result),
            preview_note=preview_note,
        ),
        schema_name="ppt_visual_review",
        schema=build_visual_review_schema(),
    )
    scores = _normalize_visual_scores(result.get("scores", {}))
    total = sum(scores.values())
    result["scores"] = scores
    result["total"] = total
    result["rating"] = _score_rating(total, max_score=len(VISUAL_REVIEW_DIMENSIONS) * 5)
    result["preview_mode"] = preview_mode
    result["summary"] = _merge_summary_note(str(result.get("summary", "")), preview_note)
    return result


def _blocker_issues(review_result: dict[str, Any]) -> list[dict[str, Any]]:
    return [issue for issue in review_result.get("page_issues", []) if issue.get("level") == "blocker"]


def generate_blocker_patches(
    deck: DeckDocument,
    review_result: dict[str, Any],
    *,
    model: str | None = None,
    provider: StructuredJsonProvider | None = None,
) -> dict[str, Any]:
    blockers = _blocker_issues(review_result)
    if not blockers:
        return {"patches": []}

    active_provider = provider or OpenAIVisualReviewProvider(model=model)
    user_items = [
        {
            "type": "text",
            "text": (
                "DeckSpec JSON:\n"
                + json.dumps(deck.model_dump(mode="json"), ensure_ascii=False, indent=2)
                + "\n\nVisual review JSON:\n"
                + json.dumps(review_result, ensure_ascii=False, indent=2)
                + "\n\nOnly generate patches for blocker issues."
            ),
        }
    ]
    return active_provider.create_structured_json_with_user_items(
        developer_prompt=_patch_developer_prompt(),
        user_items=user_items,
        schema_name="ppt_repair_patches",
        schema=build_patch_schema(),
    )


def _parse_field_path(path: str) -> list[str | int]:
    normalized = path.strip()
    if normalized.startswith("$."):
        normalized = normalized[2:]
    elif normalized == "$":
        normalized = ""

    tokens: list[str | int] = []
    buffer = ""
    index_buffer = ""
    in_index = False
    for char in normalized:
        if char == "." and not in_index:
            if buffer:
                tokens.append(buffer)
                buffer = ""
            continue
        if char == "[":
            if buffer:
                tokens.append(buffer)
                buffer = ""
            in_index = True
            index_buffer = ""
            continue
        if char == "]":
            if not in_index:
                raise ValueError(f"Invalid field path: {path}")
            if not index_buffer.isdigit():
                raise ValueError(f"Invalid list index in field path: {path}")
            tokens.append(int(index_buffer))
            in_index = False
            continue
        if in_index:
            index_buffer += char
        else:
            buffer += char
    if in_index:
        raise ValueError(f"Unclosed list index in field path: {normalized or path}")
    if buffer:
        tokens.append(buffer)
    return tokens


def _normalize_patch_jsonpath(path: str, patch_number: int) -> tuple[str, int]:
    raw_path = path.strip()
    if not raw_path:
        raise ValueError(f"Patch {patch_number} field path must not be empty.")
    normalized = raw_path if raw_path.startswith("$") else f"$.{raw_path}"
    slide_match = re.match(r"^\$\.slides\[(\d+)\](?:\.|$)", normalized)
    if not slide_match:
        raise ValueError(f"Patch {patch_number} must target a slide field under slides[n].")
    return normalized, int(slide_match.group(1))


def _resolve_patch_reference(payload: dict[str, Any], path: str, patch_number: int) -> tuple[str, int, Any]:
    normalized_path, slide_index = _normalize_patch_jsonpath(path, patch_number)
    if jsonpath_parse is not None:
        try:
            expression = jsonpath_parse(normalized_path)
        except Exception as exc:
            raise ValueError(f"Patch {patch_number} points to an invalid field path: {path}") from exc
        matches = expression.find(payload)
        if not matches:
            raise ValueError(f"Patch {patch_number} points to an invalid final field: {path}")
        if len(matches) != 1:
            raise ValueError(f"Patch {patch_number} field path must resolve to exactly one value: {path}")
        return normalized_path, slide_index, matches[0].value

    tokens = _parse_field_path(normalized_path)
    if not tokens:
        raise ValueError(f"Patch {patch_number} field path must not be empty.")
    if len(tokens) < 2 or tokens[0] != "slides" or not isinstance(tokens[1], int):
        raise ValueError(f"Patch {patch_number} must target a slide field under slides[n].")

    cursor: Any = payload
    try:
        for token in tokens[:-1]:
            cursor = cursor[token]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Patch {patch_number} points to an invalid field path: {path}") from exc

    final_token = tokens[-1]
    try:
        current_value = cursor[final_token]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Patch {patch_number} points to an invalid final field: {path}") from exc
    return normalized_path, slide_index, current_value


def apply_patch_set(deck: DeckDocument, patch_set: dict[str, Any]) -> DeckDocument:
    payload = deck.model_dump(mode="json")
    for patch_number, patch in enumerate(patch_set.get("patches", []), start=1):
        path = str(patch["field"]).strip()
        normalized_path, slide_index, current_value = _resolve_patch_reference(payload, path, patch_number)
        expected_page = patch.get("page")
        if isinstance(expected_page, int) and expected_page != slide_index + 1:
            raise ValueError(
                f"Patch {patch_number} page={expected_page} does not match field path slide index {slide_index + 1}."
            )
        if "old_value" in patch and current_value != patch["old_value"]:
            raise ValueError(
                f"Patch {patch_number} old_value mismatch for {path}: expected {patch['old_value']!r}, found {current_value!r}."
            )
        if jsonpath_parse is not None:
            jsonpath_parse(normalized_path).update(payload, patch["new_value"])
            continue

        tokens = _parse_field_path(normalized_path)
        cursor: Any = payload
        for token in tokens[:-1]:
            cursor = cursor[token]
        cursor[tokens[-1]] = patch["new_value"]
    return validate_deck_payload(payload).deck


def _write_json(payload: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _preserve_semantic_source(deck_path: Path, output_dir: Path, target_name: str) -> Path | None:
    if not is_semantic_deck_document(deck_path):
        return None
    return write_semantic_document(load_semantic_document(deck_path), output_dir / target_name)


def iterate_visual_review(
    *,
    deck_path: Path,
    output_dir: Path,
    model: str | None = None,
    max_rounds: int = 2,
    theme_name: str | None = None,
) -> VisualReviewArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    semantic_source_path = _preserve_semantic_source(deck_path, output_dir, "review_input.semantic.json")
    current_deck = load_deck_document(deck_path)
    current_deck_path = deck_path
    final_review_path = output_dir / "review_round_0.json"
    final_patch_path = output_dir / "patches_round_0.json"
    final_pptx_path = output_dir / "review_round_0.pptx"
    final_preview_dir = output_dir / "previews_round_0"
    final_preview_mode = "content_only"

    for round_index in range(1, max_rounds + 1):
        pptx_path = output_dir / f"review_round_{round_index}.pptx"
        log_path = output_dir / f"review_round_{round_index}.log.txt"
        deck_out_path = output_dir / f"review_round_{round_index}.deck.json"
        render_artifacts: RenderArtifacts = generate_ppt(
            current_deck,
            output_path=pptx_path,
            theme_name=theme_name,
            log_path=log_path,
            deck_output_path=deck_out_path,
        )
        if not deck_out_path.exists():
            write_deck_document(render_artifacts.final_deck, deck_out_path)
        preview_dir = output_dir / f"previews_round_{round_index}"
        previews, preview_note = _safe_export_slide_previews(render_artifacts.output_path, preview_dir)
        review_result = review_rendered_deck(
            render_artifacts.final_deck,
            previews,
            model=model,
            preview_note=preview_note,
        )
        review_path = _write_json(review_result, output_dir / f"review_round_{round_index}.json")
        patch_set = generate_blocker_patches(render_artifacts.final_deck, review_result, model=model)
        patch_path = _write_json(patch_set, output_dir / f"patches_round_{round_index}.json")
        blockers = _blocker_issues(review_result)

        final_review_path = review_path
        final_patch_path = patch_path
        final_pptx_path = render_artifacts.output_path
        final_preview_dir = preview_dir
        final_preview_mode = review_result.get("preview_mode", _resolve_preview_mode(previews))

        if blockers and not patch_set.get("patches"):
            raise RuntimeError(
                f"Visual review round {round_index} still has {len(blockers)} blocker issue(s), but no repair patches were generated."
            )

        if not patch_set.get("patches"):
            current_deck = render_artifacts.final_deck
            current_deck_path = deck_out_path
            break

        try:
            current_deck = apply_patch_set(render_artifacts.final_deck, patch_set)
        except ValueError as exc:
            raise RuntimeError(f"Failed to apply repair patches in visual review round {round_index}: {exc}") from exc
        current_deck_path = write_deck_document(current_deck, output_dir / f"review_round_{round_index}_patched.deck.json")

    return VisualReviewArtifacts(
        review_path=final_review_path,
        patch_path=final_patch_path,
        deck_path=current_deck_path,
        pptx_path=final_pptx_path,
        preview_dir=final_preview_dir,
        final_review_path=final_review_path,
        final_patch_path=final_patch_path,
        semantic_source_path=semantic_source_path,
        preview_mode=final_preview_mode,
    )


def review_deck_once(
    *,
    deck_path: Path,
    output_dir: Path,
    model: str | None = None,
    theme_name: str | None = None,
) -> SingleReviewArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    semantic_source_path = _preserve_semantic_source(deck_path, output_dir, "review_once.semantic.json")
    deck = load_deck_document(deck_path)
    pptx_path = output_dir / "review_once.pptx"
    log_path = output_dir / "review_once.log.txt"
    deck_out_path = output_dir / "review_once.deck.json"
    render_artifacts = generate_ppt(
        deck,
        output_path=pptx_path,
        theme_name=theme_name,
        log_path=log_path,
        deck_output_path=deck_out_path,
    )
    if not deck_out_path.exists():
        write_deck_document(render_artifacts.final_deck, deck_out_path)
    preview_dir = output_dir / "previews_review_once"
    previews, preview_note = _safe_export_slide_previews(render_artifacts.output_path, preview_dir)
    review_result = review_rendered_deck(
        render_artifacts.final_deck,
        previews,
        model=model,
        preview_note=preview_note,
    )
    review_path = _write_json(review_result, output_dir / "review_once.json")
    patch_set = generate_blocker_patches(render_artifacts.final_deck, review_result, model=model)
    patch_path = _write_json(patch_set, output_dir / "patches_review_once.json")
    return SingleReviewArtifacts(
        review_path=review_path,
        patch_path=patch_path,
        deck_path=deck_out_path,
        pptx_path=render_artifacts.output_path,
        preview_dir=preview_dir,
        semantic_source_path=semantic_source_path,
        preview_mode=review_result.get("preview_mode", _resolve_preview_mode(previews)),
    )
