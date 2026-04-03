import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from pptx import Presentation

from .config import IDX_THEME


EXPECTED_THEME_TITLE_FONT_PT = 40.0
EXPECTED_DIRECTORY_TITLE_FONT_PT = 24.0


def _slide_text(slide) -> str:
    texts = []
    for shape in slide.shapes:
        if getattr(shape, "has_text_frame", False):
            text = re.sub(r"\s+", " ", shape.text_frame.text).strip()
            if text:
                texts.append(text)
    return " ".join(texts)


def _is_ending_slide(slide) -> bool:
    text = _slide_text(slide).lower()
    if not text and len(slide.shapes) <= 2:
        return True
    return any(keyword in text for keyword in ("thanks", "thank you", "q&a", "谢谢", "感谢"))


def _is_directory_slide(slide, chapter_lines: list[str]) -> bool:
    text = _slide_text(slide)
    if not text:
        return False
    lowered = text.lower()
    if "目录" in text or "content" in lowered:
        return True
    return False


def _iter_text_run_sizes(shape) -> list[float]:
    sizes = []
    if not getattr(shape, "has_text_frame", False):
        return sizes
    for paragraph in shape.text_frame.paragraphs:
        for run in paragraph.runs:
            if run.text.strip() and run.font.size is not None:
                sizes.append(round(run.font.size.pt, 1))
    return sizes


def _theme_title_font_ok(prs: Presentation) -> bool:
    if IDX_THEME >= len(prs.slides):
        return False
    slide = prs.slides[IDX_THEME]
    candidates = [
        shape
        for shape in slide.shapes
        if getattr(shape, "has_text_frame", False)
        and 1500000 < shape.top < 2300000
        and shape.width > 5000000
    ]
    if not candidates:
        return False
    title_shape = max(candidates, key=lambda shape: shape.width)
    sizes = _iter_text_run_sizes(title_shape)
    return bool(sizes) and all(size == EXPECTED_THEME_TITLE_FONT_PT for size in sizes)


def _directory_title_font_ok(prs: Presentation, directory_slides: list[int], chapter_lines: list[str]) -> bool:
    if not directory_slides or not chapter_lines:
        return False
    for slide_no in directory_slides:
        slide = prs.slides[slide_no - 1]
        title_boxes = [
            shape
            for shape in slide.shapes
            if getattr(shape, "has_text_frame", False)
            and shape.width > 3000000
            and 1800000 < shape.top < 5200000
        ]
        title_boxes = sorted(title_boxes, key=lambda shape: (shape.top, shape.left))[: len(chapter_lines)]
        if len(title_boxes) < len(chapter_lines):
            return False
        for shape in title_boxes:
            sizes = _iter_text_run_sizes(shape)
            if not sizes or any(size != EXPECTED_DIRECTORY_TITLE_FONT_PT for size in sizes):
                return False
    return True


def _slide_image_targets(pptx_path: Path, slide_no: int) -> set[str]:
    rel_path = f"ppt/slides/_rels/slide{slide_no}.xml.rels"
    targets: set[str] = set()
    with zipfile.ZipFile(pptx_path) as package:
        try:
            root = ElementTree.fromstring(package.read(rel_path))
        except KeyError:
            return targets
    for rel in root:
        rel_type = rel.attrib.get("Type", "")
        if rel_type.endswith("/image"):
            target = rel.attrib.get("Target", "")
            if target:
                targets.add(target)
    return targets


def _directory_assets_preserved(pptx_path: Path, directory_slides: list[int]) -> bool:
    if len(directory_slides) <= 1:
        return True
    source_assets = _slide_image_targets(pptx_path, directory_slides[0])
    if not source_assets:
        return True
    for slide_no in directory_slides[1:]:
        if not source_assets.issubset(_slide_image_targets(pptx_path, slide_no)):
            return False
    return True


def write_qa_report(pptx_path: Path, chapter_count: int, pattern_ids=None, chapter_lines=None) -> Path:
    prs = Presentation(str(pptx_path))
    chapter_lines = chapter_lines or []
    lines = []
    lines.append("SIE AutoPPT QA Report")
    lines.append(f"file: {pptx_path}")
    lines.append(f"slides: {len(prs.slides)}")

    has_ending_last = _is_ending_slide(prs.slides[-1])
    lines.append(f"check_ending_last: {'PASS' if has_ending_last else 'WARN'}")

    expected_dirs = [3 + i * 2 for i in range(chapter_count)]
    actual_dirs = [i for i, slide in enumerate(prs.slides, start=1) if _is_directory_slide(slide, chapter_lines)]
    lines.append(f"expected_directory_pages: {expected_dirs}")
    lines.append(f"actual_directory_pages:   {actual_dirs}")
    if pattern_ids:
        lines.append(f"semantic_patterns: {pattern_ids}")
    lines.append(f"check_theme_title_font_40: {'PASS' if _theme_title_font_ok(prs) else 'WARN'}")
    lines.append(
        f"check_directory_title_font_24: {'PASS' if _directory_title_font_ok(prs, actual_dirs, chapter_lines) else 'WARN'}"
    )
    lines.append(
        f"check_directory_assets_preserved: {'PASS' if _directory_assets_preserved(pptx_path, actual_dirs) else 'WARN'}"
    )

    risk = 0
    for slide in prs.slides:
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False):
                text = re.sub(r"\s+", " ", shape.text_frame.text).strip()
                if len(text) > 180:
                    risk += 1
    lines.append(f"overflow_risk_boxes: {risk}")
    lines.append("note: overflow_risk_boxes > 0 means manual review recommended.")

    report = pptx_path.with_name(pptx_path.stem + "_QA.txt")
    report.write_text("\n".join(lines), encoding="utf-8")
    return report
