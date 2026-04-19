from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RunMetadata(BaseModel):
    run_id: str = Field(min_length=1)
    mode: Literal["internal_batch"] = "internal_batch"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InputSource(BaseModel):
    source_ref: str = Field(min_length=1)
    type: Literal["text", "link", "image", "attachment", "structured_data"]
    path: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    mime_type: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    safe: bool


class InputEnvelope(BaseModel):
    run_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    mode: Literal["internal_batch"] = "internal_batch"
    inputs: list[InputSource]


class SourceIndexEntry(BaseModel):
    source_ref: str = Field(min_length=1)
    type: Literal["text", "link", "image", "attachment", "structured_data"]
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")


class TextSummary(BaseModel):
    summary: str = Field(min_length=1)
    key_points: list[str] = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)


class ImageSummary(BaseModel):
    image_ref: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    ocr_text: str = ""
    description: str = ""
    source_refs: list[str] = Field(min_length=1)


class StoryArgumentRef(BaseModel):
    argument: str = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)
    block_ref: str | None = None


class StoryPlanEntry(BaseModel):
    slide_ref: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    title: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    source_refs: list[str] = Field(min_length=1)
    argument_refs: list[StoryArgumentRef] = Field(default_factory=list)


class StoryPlan(BaseModel):
    outline: list[StoryPlanEntry] = Field(min_length=1)


class ContentBundle(BaseModel):
    run_id: str = Field(min_length=1)
    bundle_version: int = Field(ge=1)
    bundle_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    language: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    theme: str = Field(min_length=1)
    source_index: list[SourceIndexEntry] = Field(min_length=1)
    text_summary: TextSummary
    images: list[ImageSummary] = Field(default_factory=list)
    story_plan: StoryPlan
    clarify_result: dict[str, Any] | None = None
    semantic_payload: dict[str, Any]


class ShapeMapEntry(BaseModel):
    page_ref: str = Field(min_length=1)
    svg_node_id: str = Field(min_length=1)
    ppt_shape_name: str = Field(min_length=1)
    ppt_shape_index: int = Field(ge=0)
    role: str = Field(min_length=1)


class SvgPageManifest(BaseModel):
    page_ref: str = Field(min_length=1)
    svg_path: str = Field(min_length=1)
    svg_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")


class SvgManifest(BaseModel):
    run_id: str = Field(min_length=1)
    bundle_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    svg_bundle_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    project_root: str = Field(min_length=1)
    pages: list[SvgPageManifest] = Field(min_length=1)


class ExportManifest(BaseModel):
    run_id: str = Field(min_length=1)
    bundle_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    svg_bundle_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    export_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    exporter_version: str = Field(min_length=1)
    pptx_path: str = Field(min_length=1)
    shape_map: list[ShapeMapEntry] = Field(min_length=1)
    shape_map_mode: Literal["mapped", "heuristic"] = "heuristic"


class SvgRequest(BaseModel):
    run_id: str = Field(min_length=1)
    bundle_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    content_bundle_path: str = Field(min_length=1)
    page_refs: list[str] = Field(min_length=1)


class QaIssue(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    issue_id: str = Field(min_length=1)
    class_: Literal["style", "layout", "schema", "mapping", "content"] = Field(alias="class")
    severity: Literal["warning", "high", "error"]
    repair_route: Literal["tune", "regenerate", "stop"]
    page_ref: str | None = None
    message: str = Field(min_length=1)


class QaReport(BaseModel):
    run_id: str = Field(min_length=1)
    status: Literal["passed", "repairable", "failed"]
    issues: list[QaIssue] = Field(default_factory=list)
    route: Literal["tune", "regenerate", "stop"] = "stop"
    checked_pptx_path: str | None = None
    workspace: str | None = None
    degraded_mode: bool = False
    degraded_reasons: list[str] = Field(default_factory=list)
    rewrite_round_limit: int = Field(default=0, ge=0)
    rewrite_rounds_used: int = Field(default=0, ge=0)
    rewrite_rounds: list[dict[str, Any]] = Field(default_factory=list)


class RunSummary(BaseModel):
    run_id: str = Field(min_length=1)
    final_state: str = Field(min_length=1)
    final_pptx: str | None = None
    bundle_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    export_hash: str = Field(pattern=r"^sha256:[0-9a-f]+$")
    shape_map_mode: Literal["mapped", "heuristic"] = "heuristic"
    degraded_mode: bool = False
    degraded_reasons: list[str] = Field(default_factory=list)
    retry_attempts_total: int = Field(default=0, ge=0)
    total_latency_ms: int = Field(default=0, ge=0)
    llm_input_tokens: int = Field(default=0, ge=0)
    llm_output_tokens: int = Field(default=0, ge=0)
    llm_total_tokens: int = Field(default=0, ge=0)
    llm_total_cost_usd: float = Field(default=0.0, ge=0.0)
    ai_five_stage_mode: str = "legacy"
