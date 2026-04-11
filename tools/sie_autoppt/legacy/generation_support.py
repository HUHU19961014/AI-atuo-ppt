import datetime
import re
import warnings
from pathlib import Path

from .openxml_slide_ops import copy_slide_xml_assets, import_slides_from_presentation, slide_assets_preserved
from .body_renderers import resolve_render_pattern
from ..models import BodyPageSpec, PageRenderTrace
from .reference_styles import build_reference_import_plan
from ..template_manifest import TemplateManifest


LEGACY_CLONE_DEPRECATION_MESSAGE = (
    "Legacy runtime slide cloning is deprecated. Please migrate this template to a preallocated slide pool."
)


def build_output_path(output_dir: Path, output_prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_prefix = re.sub(r'[<>:"/\\\\|?*]+', "_", output_prefix).strip(" ._") or "Enterprise-AI-PPT"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return output_dir / f"{safe_prefix}_{timestamp}.pptx"


def validate_slide_pool_configuration(manifest: TemplateManifest, body_page_count: int, slide_count: int) -> list[str]:
    notes: list[str] = []
    if not manifest.slide_pools:
        notes.append("template manifest does not define a preallocated slide pool; legacy runtime cloning will be used")
        return notes

    directory_pool = list(manifest.slide_pools.directory)
    body_pool = list(manifest.slide_pools.body)
    if len(directory_pool) != len(body_pool):
        raise ValueError("Template manifest slide pool is invalid: directory/body pool lengths do not match.")
    if manifest.slide_pools.ending is None:
        raise ValueError("Template manifest slide pool is invalid: ending slide is not configured.")
    if len(directory_pool) < body_page_count or len(body_pool) < body_page_count:
        raise ValueError(
            "Template manifest slide pool is too small for this deck: "
            f"requested {body_page_count} body pages, "
            f"but only {min(len(directory_pool), len(body_pool))} preallocated pairs are configured in "
            f"{manifest.manifest_path}."
        )

    used_indices = directory_pool[:body_page_count] + body_pool[:body_page_count] + [manifest.slide_pools.ending]
    if any(index < 0 for index in used_indices):
        raise ValueError("Template manifest slide pool is invalid: negative slide index detected.")
    if max(used_indices, default=-1) >= slide_count:
        raise ValueError("Template manifest slide pool is invalid: slide index exceeds the template slide count.")
    if len(set(used_indices)) != len(used_indices):
        raise ValueError("Template manifest slide pool is invalid: duplicate slide index detected.")
    return notes


def reference_import_unavailable_reason(body_pages: list[BodyPageSpec], reference_body_path: Path | None) -> str:
    if not any(page.reference_style_id for page in body_pages):
        return ""
    if reference_body_path is None or not reference_body_path.exists():
        return "reference body slide library is unavailable"
    return ""


def build_page_render_traces(
    body_pages: list[BodyPageSpec],
    reference_import_applied: bool,
    reference_import_reason: str,
) -> list[PageRenderTrace]:
    traces = []
    for page in body_pages:
        actual_pattern_id = resolve_render_pattern(page.pattern_id)
        if page.reference_style_id:
            if reference_import_applied:
                render_route = f"reference_import:{page.reference_style_id}"
                fallback_reason = ""
            else:
                render_route = f"native_fallback:{actual_pattern_id}"
                fallback_reason = reference_import_reason or "reference style import was not applied"
        else:
            render_route = f"native_renderer:{actual_pattern_id}"
            fallback_reason = ""
        traces.append(
            PageRenderTrace(
                page_key=page.page_key,
                title=page.title,
                requested_pattern_id=page.pattern_id,
                actual_pattern_id=actual_pattern_id,
                reference_style_id=page.reference_style_id,
                render_route=render_route,
                fallback_reason=fallback_reason,
            )
        )
    return traces


def apply_reference_body_slides(
    pptx_path: Path,
    reference_body_path: Path | None,
    body_pages: list[BodyPageSpec],
    manifest: TemplateManifest,
) -> bool:
    import_plan = build_reference_import_plan(body_pages, reference_body_path=reference_body_path, manifest=manifest)
    if not import_plan or reference_body_path is None or not reference_body_path.exists():
        return False
    try:
        if import_slides_from_presentation(pptx_path, reference_body_path, import_plan):
            return True
    except Exception as exc:
        warnings.warn(
            f"Reference body slide import failed during native package merge: {exc}",
            stacklevel=2,
        )
    return False


def warn_if_reference_import_disabled(body_pages: list[BodyPageSpec], reference_body_path: Path | None):
    if not any(page.reference_style_id for page in body_pages):
        return
    if reference_body_path is None or not reference_body_path.exists():
        warnings.warn(
            "Reference style library is unavailable; using native fallback renderers for reference-style pages.",
            stacklevel=2,
        )


def refresh_preallocated_directory_assets(pptx_path: Path, body_page_count: int, manifest: TemplateManifest) -> bool:
    if not manifest.slide_pools:
        return True
    target_indices = [index + 1 for index in manifest.slide_pools.directory[1:body_page_count]]
    if not target_indices:
        return True
    source_idx = manifest.slide_pools.directory[0] + 1
    if not copy_slide_xml_assets(pptx_path, source_idx=source_idx, target_indices=target_indices):
        return False
    return slide_assets_preserved(pptx_path, source_idx=source_idx, target_indices=target_indices)


def build_preflight_notes(
    body_pages: list[BodyPageSpec],
    manifest: TemplateManifest,
    slide_count: int,
    reference_body_path: Path | None,
) -> list[str]:
    notes = validate_slide_pool_configuration(manifest, len(body_pages), slide_count)
    reference_reason = reference_import_unavailable_reason(body_pages, reference_body_path)
    if reference_reason:
        notes.append(reference_reason)
    if any(len(re.sub(r"\s+", " ", bullet).strip()) > 120 for page in body_pages for bullet in page.bullets):
        notes.append("some bullet content is unusually long and may require manual layout review")
    return notes


__all__ = [
    "LEGACY_CLONE_DEPRECATION_MESSAGE",
    "apply_reference_body_slides",
    "build_output_path",
    "build_page_render_traces",
    "build_preflight_notes",
    "refresh_preallocated_directory_assets",
    "reference_import_unavailable_reason",
    "validate_slide_pool_configuration",
    "warn_if_reference_import_disabled",
]
