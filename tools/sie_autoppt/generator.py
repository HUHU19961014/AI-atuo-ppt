import gc
import datetime
import re
import shutil
import subprocess
import sys
import textwrap
import time
import warnings
import zipfile
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree

try:
    import win32com.client  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    win32com = None

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Pt

from .config import (
    COLOR_ACTIVE,
    COLOR_INACTIVE,
    DEFAULT_MIN_TEMPLATE_SLIDES,
    DEFAULT_OUTPUT_DIR,
    FONT_NAME,
    IDX_BODY_TEMPLATE,
    IDX_DIRECTORY,
    IDX_THEME,
)
from .models import BodyPageSpec
from .pipeline import plan_deck_from_html
from .reference_styles import build_reference_import_plan, populate_reference_body_pages
from .template_manifest import (
    BODY_RENDER_AREA_BOUNDS,
    BODY_SUBTITLE_BOUNDS,
    BODY_TITLE_BOUNDS,
    BODY_TITLE_FALLBACK_BOX,
    DIRECTORY_TITLE_BOUNDS,
    THEME_TITLE_BOUNDS,
)


THEME_TITLE_FONT_PT = 40
DIRECTORY_TITLE_FONT_PT = 24


def set_shape_text(shape, text: str, size_pt: int = 18, bold: bool = False, align=PP_ALIGN.LEFT):
    if not getattr(shape, "has_text_frame", False):
        return
    text_frame = shape.text_frame
    text_frame.clear()
    paragraph = text_frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.name = FONT_NAME
    run.font.size = Pt(size_pt)
    run.font.bold = bold


def normalize_text_for_box(text: str, max_chars: int = 44) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    lines = textwrap.wrap(compact, width=max_chars)
    return "\n".join(lines[:4])


def choose_title_font_size(text: str, default: int = 24) -> int:
    n = len(text)
    if n > 28:
        return 16
    if n > 22:
        return 18
    if n > 16:
        return 20
    return default


def choose_font_size_by_length(text: str, base: int = 13) -> int:
    n = len(text)
    if n > 120:
        return max(10, base - 3)
    if n > 90:
        return max(11, base - 2)
    if n > 70:
        return max(12, base - 1)
    return base


def replace_text_preserve_runs(shape, text: str, force_color=None, font_size_pt: int | None = None):
    if not getattr(shape, "has_text_frame", False):
        return
    text_frame = shape.text_frame
    text_frame.word_wrap = True
    if not text_frame.paragraphs:
        return
    paragraph = text_frame.paragraphs[0]
    if paragraph.runs:
        paragraph.runs[0].text = text
        paragraph.runs[0].font.name = FONT_NAME
        if font_size_pt is not None:
            paragraph.runs[0].font.size = Pt(font_size_pt)
        if force_color is not None:
            paragraph.runs[0].font.color.rgb = RGBColor(*force_color)
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        run = paragraph.add_run()
        run.text = text
        run.font.name = FONT_NAME
        if font_size_pt is not None:
            run.font.size = Pt(font_size_pt)
        if force_color is not None:
            run.font.color.rgb = RGBColor(*force_color)
    for extra_paragraph in text_frame.paragraphs[1:]:
        for run in extra_paragraph.runs:
            run.text = ""


def set_shape_text_with_color(shape, text: str, color, size_pt=None, bold=None):
    if not getattr(shape, "has_text_frame", False):
        return
    text_frame = shape.text_frame
    text_frame.text = text
    text_frame.word_wrap = True
    for paragraph in text_frame.paragraphs:
        paragraph.alignment = PP_ALIGN.LEFT
        for run in paragraph.runs:
            run.font.name = FONT_NAME
            run.font.color.rgb = RGBColor(*color)
            if size_pt is not None:
                run.font.size = Pt(size_pt)
            if bold is not None:
                run.font.bold = bold


def pick_text_shapes(slide):
    return [shape for shape in slide.shapes if getattr(shape, "has_text_frame", False)]


def clone_slide_after(prs: Presentation, source_idx: int, insert_after_idx: int, keep_rel_ids: bool = True):
    source = prs.slides[source_idx]
    new_slide = prs.slides.add_slide(source.slide_layout)
    for shape in list(new_slide.shapes):
        element = shape._element
        element.getparent().remove(element)
    for shape in source.shapes:
        new_element = deepcopy(shape.element)
        new_slide.shapes._spTree.insert_element_before(new_element, "p:extLst")
    for rel in source.part.rels.values():
        if "notesSlide" in rel.reltype:
            continue
        try:
            if keep_rel_ids:
                new_slide.part.rels.add_relationship(rel.reltype, rel._target, rel.rId)
            else:
                new_slide.part.rels.add_relationship(rel.reltype, rel._target)
        except Exception:
            pass
    slide_id_list = prs.slides._sldIdLst
    new_id = slide_id_list[-1]
    del slide_id_list[-1]
    slide_id_list.insert(insert_after_idx + 1, new_id)
    return prs.slides[insert_after_idx + 1]


def ensure_last_slide_is_thanks(prs: Presentation, thanks_slide_id: int):
    slide_id_list = prs.slides._sldIdLst
    target = None
    for item in slide_id_list:
        if int(item.id) == int(thanks_slide_id):
            target = item
            break
    if target is None:
        return
    slide_id_list.remove(target)
    slide_id_list.append(target)


def fill_directory_slide(slide, chapter_lines, active_chapter_index: int):
    texts = sorted(pick_text_shapes(slide), key=lambda shape: (shape.top, shape.left))
    title_boxes = [shape for shape in texts if DIRECTORY_TITLE_BOUNDS.matches(shape)]
    title_boxes = sorted(title_boxes, key=lambda shape: (shape.top, shape.left))
    safe_active_index = max(0, min(active_chapter_index, len(chapter_lines) - 1))
    for i, shape in enumerate(title_boxes[: len(chapter_lines)]):
        color = COLOR_ACTIVE if i == safe_active_index else COLOR_INACTIVE
        replace_text_preserve_runs(
            shape,
            chapter_lines[i],
            force_color=color,
            font_size_pt=DIRECTORY_TITLE_FONT_PT,
        )


def repair_directory_slides_with_com(pptx_path: Path, source_idx: int, target_indices: list[int]) -> bool:
    if win32com is None:
        return False
    helper = Path(__file__).resolve().parents[1] / "repair_directory_slides.py"
    command = [
        sys.executable,
        str(helper),
        str(pptx_path.resolve()),
        "--source-idx",
        str(source_idx),
        "--targets",
        *[str(target) for target in target_indices],
    ]
    for _ in range(5):
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            return True
        time.sleep(1.0)
    return False


def copy_directory_slide_xml_assets(pptx_path: Path, source_idx: int, target_indices: list[int]) -> bool:
    if not target_indices:
        return True
    source_slide_name = f"ppt/slides/slide{source_idx}.xml"
    source_rel_name = f"ppt/slides/_rels/slide{source_idx}.xml.rels"
    target_slide_names = {f"ppt/slides/slide{target}.xml" for target in target_indices}
    target_rel_names = {f"ppt/slides/_rels/slide{target}.xml.rels" for target in target_indices}
    rebuilt_path = pptx_path.with_name(pptx_path.stem + "_rebuilt.pptx")

    with zipfile.ZipFile(pptx_path, "r") as source_package:
        if source_slide_name not in source_package.namelist():
            return False
        slide_root = ElementTree.fromstring(source_package.read(source_slide_name))
        slide_ns = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
        source_sp_tree = slide_root.find(f".//{slide_ns}spTree")
        source_pics = [deepcopy(pic) for pic in source_sp_tree.findall(f"{slide_ns}pic")] if source_sp_tree is not None else []
        rel_bytes = source_package.read(source_rel_name) if source_rel_name in source_package.namelist() else None
        source_image_rels = []
        if rel_bytes is not None:
            source_rel_root = ElementTree.fromstring(rel_bytes)
            source_image_rels = [
                deepcopy(rel)
                for rel in source_rel_root
                if rel.attrib.get("Type", "").endswith("/image")
            ]

        slide_replacements: dict[str, bytes] = {}
        rel_replacements: dict[str, bytes] = {}
        rel_root_tag = (
            ElementTree.fromstring(rel_bytes).tag
            if rel_bytes is not None
            else "{http://schemas.openxmlformats.org/package/2006/relationships}Relationships"
        )

        for target_slide_name in target_slide_names:
            if target_slide_name not in source_package.namelist():
                continue
            target_root = ElementTree.fromstring(source_package.read(target_slide_name))
            target_sp_tree = target_root.find(f".//{slide_ns}spTree")
            if target_sp_tree is not None and not target_sp_tree.findall(f"{slide_ns}pic") and source_pics:
                insert_at = next(
                    (index for index, child in enumerate(list(target_sp_tree)) if child.tag == f"{slide_ns}extLst"),
                    len(target_sp_tree),
                )
                for pic in source_pics:
                    target_sp_tree.insert(insert_at, deepcopy(pic))
                    insert_at += 1
            slide_replacements[target_slide_name] = ElementTree.tostring(
                target_root,
                encoding="utf-8",
                xml_declaration=True,
            )

        for target_rel_name in target_rel_names:
            if target_rel_name in source_package.namelist():
                target_rel_root = ElementTree.fromstring(source_package.read(target_rel_name))
            else:
                target_rel_root = ElementTree.Element(rel_root_tag)
            existing_image_targets = {
                rel.attrib.get("Target", "")
                for rel in target_rel_root
                if rel.attrib.get("Type", "").endswith("/image")
            }
            for image_rel in source_image_rels:
                if image_rel.attrib.get("Target", "") in existing_image_targets:
                    continue
                target_rel_root.append(deepcopy(image_rel))
            rel_replacements[target_rel_name] = ElementTree.tostring(
                target_rel_root,
                encoding="utf-8",
                xml_declaration=True,
            )

        with zipfile.ZipFile(rebuilt_path, "w", zipfile.ZIP_DEFLATED) as rebuilt:
            for info in source_package.infolist():
                data = source_package.read(info.filename)
                if info.filename in slide_replacements:
                    data = slide_replacements[info.filename]
                elif info.filename in rel_replacements:
                    data = rel_replacements[info.filename]
                rebuilt.writestr(info, data)

            for target_slide_name, data in slide_replacements.items():
                if target_slide_name not in source_package.namelist():
                    rebuilt.writestr(target_slide_name, data)
            for target_rel_name, data in rel_replacements.items():
                if target_rel_name not in source_package.namelist():
                    rebuilt.writestr(target_rel_name, data)

    rebuilt_path.replace(pptx_path)
    return True


def apply_reference_body_slides_with_com(pptx_path: Path, reference_body_path: Path | None, body_pages: list[BodyPageSpec]) -> bool:
    import_plan = build_reference_import_plan(body_pages)
    if not import_plan:
        return True
    if win32com is None or reference_body_path is None or not reference_body_path.exists():
        return False
    helper = Path(__file__).resolve().parents[1] / "apply_reference_body_slides.py"
    command = [
        sys.executable,
        str(helper),
        str(pptx_path.resolve()),
        str(reference_body_path.resolve()),
        "--mapping",
        *[f"{target}={source}" for target, source in import_plan],
    ]
    last_error = ""
    for _ in range(5):
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            return True
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        last_error = stderr or stdout or f"exit code {result.returncode}"
        time.sleep(1.0)
    warnings.warn(f"Reference body slide import failed after retries: {last_error}", stacklevel=2)
    return False


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


def directory_assets_preserved(pptx_path: Path, source_idx: int, target_indices: list[int]) -> bool:
    source_targets = _slide_image_targets(pptx_path, source_idx)
    if not source_targets:
        return True
    for slide_no in target_indices:
        target_assets = _slide_image_targets(pptx_path, slide_no)
        if not source_targets.issubset(target_assets):
            return False
    return True


def _render_cards_2x2(slide, bullets: list[str]):
    x0, y0 = 576088, 1450000
    card_w, card_h = 5000000, 1200000
    gap_x, gap_y = 350000, 260000
    for i, text in enumerate(bullets[:4]):
        row, col = divmod(i, 2)
        left = x0 + col * (card_w + gap_x)
        top = y0 + row * (card_h + gap_y)
        card = slide.shapes.add_shape(1, left, top, card_w, card_h)
        card.fill.solid()
        card.fill.fore_color.rgb = RGBColor(248, 250, 252)
        card.line.color.rgb = RGBColor(220, 223, 230)
        textbox = slide.shapes.add_textbox(left + 180000, top + 180000, card_w - 360000, card_h - 360000)
        safe_text = normalize_text_for_box(text, 38)
        font_size = choose_font_size_by_length(safe_text, 13)
        set_shape_text(textbox, safe_text, size_pt=font_size, bold=False)


def _render_process_flow(slide, bullets: list[str]):
    start_x, y = 620000, 2050000
    step_w, step_h, gap = 2500000, 1200000, 220000
    for i, text in enumerate(bullets[:4]):
        left = start_x + i * (step_w + gap)
        box = slide.shapes.add_shape(1, left, y, step_w, step_h)
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(246, 249, 252)
        box.line.color.rgb = RGBColor(210, 218, 226)
        number = slide.shapes.add_textbox(left + 100000, y + 90000, 260000, 220000)
        set_shape_text(number, f"{i + 1:02d}", size_pt=12, bold=True)
        textbox = slide.shapes.add_textbox(left + 100000, y + 360000, step_w - 200000, step_h - 460000)
        safe_text = normalize_text_for_box(text, 24)
        set_shape_text(textbox, safe_text, size_pt=11, bold=False)


def _extract_system_tags(bullets: list[str]) -> list[str]:
    systems = []
    for bullet in bullets:
        for system in re.findall(r"\b[A-Z][A-Z0-9/-]{1,}\b", bullet):
            if system not in systems:
                systems.append(system)
    return systems[:5]


def _render_architecture_layers(slide, bullets: list[str]):
    x = 900000
    y0 = 1650000
    width = 10100000
    layer_h = 720000
    gap = 150000
    palette = [
        ((245, 247, 250), (210, 218, 228), (173, 5, 61)),
        ((248, 250, 252), (214, 222, 231), (60, 76, 96)),
        ((250, 251, 253), (218, 225, 233), (60, 76, 96)),
        ((243, 246, 250), (206, 216, 226), (173, 5, 61)),
    ]
    for i, text in enumerate(bullets[:4]):
        y = y0 + i * (layer_h + gap)
        fill, line, accent = palette[i]
        layer = slide.shapes.add_shape(1, x, y, width, layer_h)
        layer.fill.solid()
        layer.fill.fore_color.rgb = RGBColor(*fill)
        layer.line.color.rgb = RGBColor(*line)

        tag = slide.shapes.add_shape(1, x + 120000, y + 120000, 1100000, layer_h - 240000)
        tag.fill.solid()
        tag.fill.fore_color.rgb = RGBColor(*accent)
        tag.line.color.rgb = RGBColor(*accent)
        tag_text = slide.shapes.add_textbox(x + 170000, y + 175000, 980000, 240000)
        set_shape_text_with_color(tag_text, f"L{i + 1:02d}", (255, 255, 255), size_pt=14, bold=True)

        text_box = slide.shapes.add_textbox(x + 1450000, y + 130000, width - 1750000, layer_h - 220000)
        safe_text = normalize_text_for_box(text, 40)
        set_shape_text(text_box, safe_text, size_pt=12, bold=False)

    banner = slide.shapes.add_shape(1, 900000, 1250000, 2500000, 230000)
    banner.fill.solid()
    banner.fill.fore_color.rgb = RGBColor(*COLOR_ACTIVE)
    banner.line.color.rgb = RGBColor(*COLOR_ACTIVE)
    banner_text = slide.shapes.add_textbox(1020000, 1225000, 2200000, 260000)
    set_shape_text_with_color(banner_text, "ERP ARCHITECTURE", (255, 255, 255), size_pt=11, bold=True)

    system_tags = _extract_system_tags(bullets)
    if system_tags:
        chip_left = 8650000
        chip_top = 1240000
        chip_w = 800000
        chip_h = 240000
        gap_x = 120000
        for idx, system in enumerate(system_tags[:4]):
            left = chip_left + idx * (chip_w + gap_x)
            chip = slide.shapes.add_shape(1, left, chip_top, chip_w, chip_h)
            chip.fill.solid()
            chip.fill.fore_color.rgb = RGBColor(243, 246, 250)
            chip.line.color.rgb = RGBColor(210, 218, 226)
            chip_text = slide.shapes.add_textbox(left, chip_top + 20000, chip_w, chip_h)
            set_shape_text(chip_text, system, size_pt=9, bold=True, align=PP_ALIGN.CENTER)


def _render_governance_grid(slide, bullets: list[str]):
    x0, y0 = 900000, 1780000
    card_w, card_h = 4700000, 1180000
    gap_x, gap_y = 380000, 260000
    for i, text in enumerate(bullets[:4]):
        row, col = divmod(i, 2)
        left = x0 + col * (card_w + gap_x)
        top = y0 + row * (card_h + gap_y)
        card = slide.shapes.add_shape(1, left, top, card_w, card_h)
        card.fill.solid()
        card.fill.fore_color.rgb = RGBColor(247, 249, 252)
        card.line.color.rgb = RGBColor(214, 221, 229)

        num = slide.shapes.add_shape(1, left + 110000, top + 120000, 620000, 260000)
        num.fill.solid()
        num.fill.fore_color.rgb = RGBColor(*COLOR_ACTIVE)
        num.line.color.rgb = RGBColor(*COLOR_ACTIVE)
        num_text = slide.shapes.add_textbox(left + 110000, top + 132000, 620000, 220000)
        set_shape_text_with_color(num_text, f"重点 {i + 1}", (255, 255, 255), size_pt=10, bold=True)

        text_box = slide.shapes.add_textbox(left + 110000, top + 470000, card_w - 220000, card_h - 560000)
        safe_text = normalize_text_for_box(text, 32)
        set_shape_text(text_box, safe_text, size_pt=11, bold=False)

    footer_bar = slide.shapes.add_shape(1, 900000, 4580000, 10100000, 260000)
    footer_bar.fill.solid()
    footer_bar.fill.fore_color.rgb = RGBColor(239, 243, 247)
    footer_bar.line.color.rgb = RGBColor(215, 222, 230)
    footer_text = slide.shapes.add_textbox(1050000, 4605000, 9700000, 220000)
    set_shape_text(footer_text, "从主数据、接口、流程到上线切换，治理规则需要贯穿实施全周期。", size_pt=10, bold=False)


PATTERN_RENDERERS = {
    "process_flow": _render_process_flow,
    "solution_architecture": _render_architecture_layers,
    "org_governance": _render_governance_grid,
    "general_business": _render_cards_2x2,
}


def _clear_body_render_area(slide, protected_shapes=None):
    protected_shapes = list(protected_shapes or [])
    removable = []
    for shape in slide.shapes:
        if any(shape is protected for protected in protected_shapes):
            continue
        if BODY_RENDER_AREA_BOUNDS.matches(shape):
            removable.append(shape)
    for shape in removable:
        element = shape._element
        element.getparent().remove(element)


def fill_body_slide(slide, page: BodyPageSpec):
    texts = sorted(pick_text_shapes(slide), key=lambda shape: (shape.top, shape.left))
    title_candidates = [shape for shape in texts if BODY_TITLE_BOUNDS.matches(shape)]
    if title_candidates:
        replace_text_preserve_runs(
            title_candidates[0],
            page.title,
            force_color=COLOR_ACTIVE,
            font_size_pt=choose_title_font_size(page.title),
        )
    else:
        textbox = slide.shapes.add_textbox(
            BODY_TITLE_FALLBACK_BOX.left,
            BODY_TITLE_FALLBACK_BOX.top,
            BODY_TITLE_FALLBACK_BOX.width,
            BODY_TITLE_FALLBACK_BOX.height,
        )
        set_shape_text_with_color(
            textbox,
            page.title,
            COLOR_ACTIVE,
            size_pt=choose_title_font_size(page.title),
            bold=True,
        )

    subtitle_candidates = [
        shape
        for shape in texts
        if BODY_SUBTITLE_BOUNDS.matches(shape) and shape not in title_candidates
    ]
    if subtitle_candidates:
        replace_text_preserve_runs(subtitle_candidates[0], page.subtitle)

    protected_shapes = title_candidates + subtitle_candidates[:1]
    _clear_body_render_area(slide, protected_shapes=protected_shapes)
    renderer = PATTERN_RENDERERS.get(page.pattern_id, _render_cards_2x2)
    renderer(slide, page.bullets)


def build_output_path(output_dir: Path, output_prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_prefix = re.sub(r'[<>:"/\\\\|?*]+', "_", output_prefix).strip(" ._") or "SIE_AutoPPT"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return output_dir / f"{safe_prefix}_{timestamp}.pptx"


def apply_theme_title(prs: Presentation, title: str):
    theme_texts = pick_text_shapes(prs.slides[IDX_THEME])
    title_candidates = [shape for shape in theme_texts if THEME_TITLE_BOUNDS.matches(shape)]
    if title_candidates:
        main_title = max(title_candidates, key=lambda shape: shape.width)
        set_shape_text_with_color(main_title, title, COLOR_ACTIVE, size_pt=THEME_TITLE_FONT_PT)


def render_body_pages(prs: Presentation, body_pages: list[BodyPageSpec], chapter_lines: list[str], active_start: int):
    directory_slides = [prs.slides[IDX_DIRECTORY]]
    body_slides = [prs.slides[IDX_BODY_TEMPLATE]]
    insert_after = IDX_BODY_TEMPLATE
    for _ in body_pages[1:]:
        new_directory = clone_slide_after(prs, IDX_DIRECTORY, insert_after, keep_rel_ids=True)
        directory_slides.append(new_directory)
        insert_after += 1

        new_body = clone_slide_after(prs, IDX_BODY_TEMPLATE, insert_after, keep_rel_ids=False)
        body_slides.append(new_body)
        insert_after += 1

    for chapter_idx, directory_slide in enumerate(directory_slides):
        fill_directory_slide(directory_slide, chapter_lines, active_start + chapter_idx)
    for page, body_slide in zip(body_pages, body_slides):
        if page.reference_style_id:
            continue
        fill_body_slide(body_slide, page)


def refresh_directory_clones(pptx_path: Path, chapter_lines: list[str], active_start: int, body_page_count: int):
    targets = [IDX_DIRECTORY + 1 + i * 2 for i in range(1, body_page_count)]
    if not targets:
        return True

    source_idx = IDX_DIRECTORY + 1
    for strategy in ("zip", "com"):
        for _ in range(3):
            if strategy == "zip":
                if not copy_directory_slide_xml_assets(pptx_path, source_idx=source_idx, target_indices=targets):
                    continue
            else:
                if not repair_directory_slides_with_com(pptx_path, source_idx=source_idx, target_indices=targets):
                    continue

            prs_reloaded = Presentation(str(pptx_path))
            fill_directory_slide(prs_reloaded.slides[IDX_DIRECTORY], chapter_lines, active_start)
            for offset, directory_slide_no in enumerate(targets, start=1):
                slide_index = directory_slide_no - 1
                if slide_index < len(prs_reloaded.slides):
                    fill_directory_slide(prs_reloaded.slides[slide_index], chapter_lines, active_start + offset)
            prs_reloaded.save(str(pptx_path))
            prs_reloaded = None
            gc.collect()

            if directory_assets_preserved(pptx_path, source_idx=source_idx, target_indices=targets):
                return True
            time.sleep(1.0)

    return False


def generate_ppt(
    template_path: Path,
    html_path: Path,
    reference_body_path: Path | None,
    output_prefix: str,
    chapters: int,
    active_start: int,
    output_dir: Path | None = None,
):
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    if not html_path.exists():
        raise FileNotFoundError(f"HTML not found: {html_path}")

    deck_plan = plan_deck_from_html(html_path, chapters)
    deck = deck_plan.deck
    body_pages = deck.body_pages
    chapter_lines = deck_plan.chapter_lines
    pattern_ids = deck_plan.pattern_ids

    final_output_dir = output_dir or DEFAULT_OUTPUT_DIR
    out = build_output_path(final_output_dir, output_prefix)
    shutil.copy2(template_path, out)

    prs = Presentation(str(out))
    if len(prs.slides) < DEFAULT_MIN_TEMPLATE_SLIDES:
        raise ValueError(
            f"\u6a21\u677f\u9875\u6570\u4e0d\u8db3\uff0c\u81f3\u5c11\u9700\u8981 {DEFAULT_MIN_TEMPLATE_SLIDES} \u9875\uff0c\u5b9e\u9645\u4e3a {len(prs.slides)} \u9875\u3002"
        )

    apply_theme_title(prs, deck.cover_title)
    thanks_slide_id = int(prs.slides._sldIdLst[len(prs.slides) - 1].id)
    render_body_pages(prs, body_pages, chapter_lines, active_start)
    ensure_last_slide_is_thanks(prs, thanks_slide_id)
    prs.save(str(out))
    prs = None
    gc.collect()

    if not apply_reference_body_slides_with_com(out, reference_body_path, body_pages):
        raise RuntimeError("Reference body slide import failed: could not apply reference PPT styles.")
    if not refresh_directory_clones(out, chapter_lines, active_start, len(body_pages)):
        warnings.warn(
            "Directory slide clone repair did not fully preserve template image assets; keeping generated deck and surfacing the risk in QA.",
            stacklevel=2,
        )
    populate_reference_body_pages(out, body_pages)
    return out, pattern_ids, chapter_lines
