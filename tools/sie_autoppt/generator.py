import datetime
import re
import shutil
import textwrap
from copy import deepcopy
from pathlib import Path

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
from .patterns import infer_pattern


def strip_tags(s: str) -> str:
    return re.sub(r"<.*?>", "", s).strip()


def extract_single(html: str, cls: str) -> str:
    match = re.search(rf'<div class="{cls}">(.*?)</div>', html, flags=re.S)
    return strip_tags(match.group(1)) if match else ""


def extract_list(html: str, cls: str) -> list[str]:
    return [strip_tags(item) for item in re.findall(rf'<div class="{cls}">(.*?)</div>', html, flags=re.S)]


def extract_phases(html: str) -> list[dict[str, str]]:
    keys = ("phase-time", "phase-name", "phase-code", "phase-func", "phase-owner")
    values = {key: extract_list(html, key) for key in keys}
    count = max((len(items) for items in values.values()), default=0)
    phases = []
    for index in range(count):
        phase = {
            "time": values["phase-time"][index] if index < len(values["phase-time"]) else "",
            "name": values["phase-name"][index] if index < len(values["phase-name"]) else "",
            "code": values["phase-code"][index] if index < len(values["phase-code"]) else "",
            "func": values["phase-func"][index] if index < len(values["phase-func"]) else "",
            "owner": values["phase-owner"][index] if index < len(values["phase-owner"]) else "",
        }
        if any(phase.values()):
            phases.append(phase)
    return phases


def validate_html_input(html: str):
    title = extract_single(html, "title")
    subtitle = extract_single(html, "subtitle")
    footer = extract_single(html, "footer")
    phases = extract_phases(html)
    scenarios = extract_list(html, "scenario")
    notes = extract_list(html, "note")

    has_meaningful_content = any(
        [
            title,
            subtitle,
            footer,
            phases,
            scenarios,
            notes,
        ]
    )
    if not has_meaningful_content:
        raise ValueError(
            "输入 HTML 未识别到可用内容。请至少提供 title、subtitle、phase-*、scenario、note、footer 中的一部分。"
        )

    if not phases and not scenarios and not notes:
        raise ValueError(
            "输入 HTML 缺少正文内容。请至少补充一组 phase-*、scenario 或 note，才能生成有意义的正文页。"
        )

    return {
        "title": title,
        "subtitle": subtitle,
        "footer": footer,
        "phases": phases,
        "scenarios": scenarios,
        "notes": notes,
    }


def build_body_pages(html: str) -> list[dict[str, object]]:
    payload = validate_html_input(html)
    title = payload["title"] or "项目概览与UAT阶段计划"
    subtitle = payload["subtitle"] or "根据输入 HTML 自动归纳测试章节与核心要点。"
    footer = payload["footer"]
    phases = payload["phases"]
    scenarios = payload["scenarios"]
    notes = payload["notes"]

    overview_bullets = []
    for phase in phases[:4]:
        prefix = phase["name"]
        if phase["time"]:
            prefix = f"{prefix}（{phase['time']}）" if prefix else phase["time"]
        detail = phase["func"] or phase["code"] or phase["owner"]
        bullet = f"{prefix}：{detail}".strip("：")
        if bullet:
            overview_bullets.append(bullet)
    if not overview_bullets:
        overview_bullets = [item for item in (subtitle, footer) if item][:4]
    if not overview_bullets:
        overview_bullets = ["补充 phase-* 内容后，可自动生成项目概览页。"]

    scope_bullets = scenarios[:4] or [phase["name"] for phase in phases if phase["name"]][:4]
    if not scope_bullets:
        scope_bullets = ["补充 scenario 内容后，可自动生成测试范围与关键场景页。"]

    focus_bullets = notes[:4]
    if footer:
        focus_bullets.append(footer)
    focus_bullets = focus_bullets[:4]
    if not focus_bullets:
        focus_bullets = ["补充 note 或 footer 内容后，可自动生成测试关注点与验收标准页。"]

    return [
        {
            "title": title,
            "subtitle": subtitle,
            "bullets": overview_bullets,
        },
        {
            "title": "测试范围与关键场景",
            "subtitle": "根据输入场景自动归纳测试覆盖范围。",
            "bullets": scope_bullets,
        },
        {
            "title": "测试关注点与验收标准",
            "subtitle": footer or "根据输入关注点自动生成验收提示。",
            "bullets": focus_bullets,
        },
    ]


def build_directory_lines(body_pages: list[dict[str, object]]) -> list[str]:
    lines = [str(page["title"]) for page in body_pages[:5]]
    for fallback in ("总结与行动", "Q&A"):
        if len(lines) >= 5:
            break
        lines.append(fallback)
    while len(lines) < 5:
        lines.append(f"章节{len(lines) + 1}")
    return lines[:5]


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


def choose_font_size_by_length(text: str, base: int = 13) -> int:
    n = len(text)
    if n > 120:
        return max(10, base - 3)
    if n > 90:
        return max(11, base - 2)
    if n > 70:
        return max(12, base - 1)
    return base


def replace_text_preserve_runs(shape, text: str, force_color=None):
    if not getattr(shape, "has_text_frame", False):
        return
    text_frame = shape.text_frame
    if not text_frame.paragraphs:
        return
    paragraph = text_frame.paragraphs[0]
    if paragraph.runs:
        paragraph.runs[0].text = text
        paragraph.runs[0].font.name = FONT_NAME
        if force_color is not None:
            paragraph.runs[0].font.color.rgb = RGBColor(*force_color)
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        run = paragraph.add_run()
        run.text = text
        run.font.name = FONT_NAME
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
    title_boxes = [shape for shape in texts if shape.width > 3000000 and 1800000 < shape.top < 5200000]
    title_boxes = sorted(title_boxes, key=lambda shape: (shape.top, shape.left))
    safe_active_index = max(0, min(active_chapter_index, len(chapter_lines) - 1))
    for i, shape in enumerate(title_boxes[: len(chapter_lines)]):
        color = COLOR_ACTIVE if i == safe_active_index else COLOR_INACTIVE
        replace_text_preserve_runs(shape, chapter_lines[i], force_color=color)


def repair_directory_slides_with_com(pptx_path: Path, source_idx: int, target_indices: list[int]) -> bool:
    if win32com is None:
        return False
    try:
        app = win32com.client.Dispatch("PowerPoint.Application")
        app.Visible = 1
        pres = app.Presentations.Open(str(pptx_path), WithWindow=False)
    except Exception:
        return False

    try:
        for target in sorted(target_indices, reverse=True):
            pres.Slides(target).Delete()
            duplicate = pres.Slides(source_idx).Duplicate()
            duplicate.Item(1).MoveTo(target)
        pres.Save()
        return True
    finally:
        pres.Close()
        app.Quit()


def _render_cards_2x2(slide, bullets):
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


def _render_process_flow(slide, bullets):
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


def _render_architecture_two_column(slide, bullets):
    left_x, right_x = 700000, 6200000
    y0, row_h = 1850000, 900000
    for i, text in enumerate(bullets[:4]):
        y = y0 + i * row_h
        left_box = slide.shapes.add_shape(1, left_x, y, 5000000, 680000)
        left_box.fill.solid()
        left_box.fill.fore_color.rgb = RGBColor(245, 247, 250)
        left_box.line.color.rgb = RGBColor(215, 222, 230)
        left_text = slide.shapes.add_textbox(left_x + 160000, y + 180000, 4680000, 360000)
        set_shape_text(left_text, f"模块{i + 1}", size_pt=12, bold=True)

        right_box = slide.shapes.add_shape(1, right_x, y, 5000000, 680000)
        right_box.fill.solid()
        right_box.fill.fore_color.rgb = RGBColor(250, 252, 255)
        right_box.line.color.rgb = RGBColor(220, 226, 233)
        right_text = slide.shapes.add_textbox(right_x + 160000, y + 140000, 4680000, 420000)
        safe_text = normalize_text_for_box(text, 34)
        set_shape_text(right_text, safe_text, size_pt=11, bold=False)


def _clear_body_render_area(slide):
    removable = []
    for shape in slide.shapes:
        if 1700000 < shape.top < 6200000:
            removable.append(shape)
    for shape in removable:
        element = shape._element
        element.getparent().remove(element)


def fill_body_slide(slide, page_title: str, page_subtitle: str, bullets, pattern_id: str = "general_business"):
    texts = sorted(pick_text_shapes(slide), key=lambda shape: (shape.top, shape.left))
    title_candidates = [shape for shape in texts if shape.top < 300000 and shape.width > 7000000]
    if title_candidates:
        replace_text_preserve_runs(title_candidates[0], page_title, force_color=COLOR_ACTIVE)
    else:
        textbox = slide.shapes.add_textbox(166370, 36830, 10034086, 480060)
        set_shape_text_with_color(textbox, page_title, COLOR_ACTIVE, size_pt=24, bold=True)

    subtitle_candidates = [
        shape
        for shape in texts
        if 300000 < shape.top < 1600000 and shape.width > 7000000 and shape not in title_candidates
    ]
    if subtitle_candidates:
        replace_text_preserve_runs(subtitle_candidates[0], page_subtitle)

    _clear_body_render_area(slide)
    if pattern_id == "process_flow":
        _render_process_flow(slide, bullets)
    elif pattern_id == "solution_architecture":
        _render_architecture_two_column(slide, bullets)
    else:
        _render_cards_2x2(slide, bullets)


def build_output_path(output_dir: Path, output_prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_prefix = re.sub(r'[<>:"/\\\\|?*]+', "_", output_prefix).strip(" ._") or "SIE_AutoPPT"
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return output_dir / f"{safe_prefix}_{timestamp}.pptx"


def generate_ppt(
    template_path: Path,
    html_path: Path,
    output_prefix: str,
    chapters: int,
    active_start: int,
    output_dir: Path | None = None,
):
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    if not html_path.exists():
        raise FileNotFoundError(f"HTML not found: {html_path}")

    html = html_path.read_text(encoding="utf-8")
    requested_chapters = max(1, min(chapters, 3))
    body_pages = build_body_pages(html)[:requested_chapters]
    pattern_ids = [infer_pattern(str(page["title"]), list(page["bullets"])) for page in body_pages]
    chapter_lines = build_directory_lines(body_pages)

    final_output_dir = output_dir or DEFAULT_OUTPUT_DIR
    out = build_output_path(final_output_dir, output_prefix)
    shutil.copy2(template_path, out)

    prs = Presentation(str(out))
    if len(prs.slides) < DEFAULT_MIN_TEMPLATE_SLIDES:
        raise ValueError(f"模板页数不足，至少需要 {DEFAULT_MIN_TEMPLATE_SLIDES} 页，实际为 {len(prs.slides)} 页。")

    theme_texts = pick_text_shapes(prs.slides[IDX_THEME])
    title_candidates = [shape for shape in theme_texts if 1500000 < shape.top < 2300000 and shape.width > 5000000]
    if title_candidates:
        main_title = max(title_candidates, key=lambda shape: shape.width)
        set_shape_text_with_color(main_title, str(body_pages[0]["title"]), COLOR_ACTIVE)

    fill_directory_slide(prs.slides[IDX_DIRECTORY], chapter_lines, active_start)

    thanks_slide_id = int(prs.slides._sldIdLst[len(prs.slides) - 1].id)
    fill_body_slide(
        prs.slides[IDX_BODY_TEMPLATE],
        str(body_pages[0]["title"]),
        str(body_pages[0]["subtitle"]),
        list(body_pages[0]["bullets"]),
        pattern_id=pattern_ids[0],
    )

    insert_after = IDX_BODY_TEMPLATE
    for chapter_idx, page in enumerate(body_pages[1:], start=1):
        new_directory = clone_slide_after(prs, IDX_DIRECTORY, insert_after, keep_rel_ids=True)
        fill_directory_slide(new_directory, chapter_lines, active_start + chapter_idx)
        insert_after += 1

        new_body = clone_slide_after(prs, IDX_BODY_TEMPLATE, insert_after, keep_rel_ids=False)
        fill_body_slide(
            new_body,
            str(page["title"]),
            str(page["subtitle"]),
            list(page["bullets"]),
            pattern_id=pattern_ids[chapter_idx],
        )
        insert_after += 1

    ensure_last_slide_is_thanks(prs, thanks_slide_id)
    prs.save(str(out))

    targets = [IDX_DIRECTORY + 1 + i * 2 for i in range(1, len(body_pages))]
    if targets and repair_directory_slides_with_com(out, source_idx=IDX_DIRECTORY + 1, target_indices=targets):
        prs_reloaded = Presentation(str(out))
        fill_directory_slide(prs_reloaded.slides[IDX_DIRECTORY], chapter_lines, active_start)
        for offset, directory_slide_no in enumerate(targets, start=1):
            slide_index = directory_slide_no - 1
            if slide_index < len(prs_reloaded.slides):
                fill_directory_slide(prs_reloaded.slides[slide_index], chapter_lines, active_start + offset)
        prs_reloaded.save(str(out))

    return out, pattern_ids, chapter_lines
