import re

from ..models import InputPayload


def strip_tags(s: str) -> str:
    return re.sub(r"<.*?>", "", s).strip()


def clean_heading_text(text: str) -> str:
    cleaned = strip_tags(text)
    cleaned = re.sub(r"^[^\w\u4e00-\u9fff]+", "", cleaned)
    return cleaned.strip()


def extract_single(html: str, cls: str) -> str:
    match = re.search(rf'<div class="{cls}">(.*?)</div>', html, flags=re.S)
    return strip_tags(match.group(1)) if match else ""


def extract_list(html: str, cls: str) -> list[str]:
    return [strip_tags(item) for item in re.findall(rf'<div class="{cls}">(.*?)</div>', html, flags=re.S)]


def extract_first_tag_text(html: str, tag: str) -> str:
    match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", html, flags=re.S)
    return strip_tags(match.group(1)) if match else ""


def extract_tag_with_class(html: str, tag: str, class_name: str) -> str:
    match = re.search(rf'<{tag}[^>]*class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>(.*?)</{tag}>', html, flags=re.S)
    return strip_tags(match.group(1)) if match else ""


def extract_tag_inside_block(html: str, block_class_pattern: str, tag: str) -> str:
    match = re.search(
        rf'<div class="{block_class_pattern}">.*?<{tag}[^>]*>(.*?)</{tag}>',
        html,
        flags=re.S,
    )
    return strip_tags(match.group(1)) if match else ""


def extract_list_items_from_block(html: str, class_pattern: str) -> list[str]:
    match = re.search(
        rf'<div class="{class_pattern}">.*?<ul>(.*?)</ul>',
        html,
        flags=re.S,
    )
    if not match:
        return []
    return [strip_tags(item) for item in re.findall(r"<li>(.*?)</li>", match.group(1), flags=re.S)]


def extract_steps(html: str) -> list[tuple[str, str]]:
    return [
        (clean_heading_text(title), strip_tags(desc))
        for title, desc in re.findall(
            r'<div class="step">\s*<div class="step-number">.*?</div>\s*<h3>(.*?)</h3>\s*<p>(.*?)</p>\s*</div>',
            html,
            flags=re.S,
        )
    ]


def extract_phases(html: str) -> list[dict[str, str]]:
    phase_keys = ("phase-time", "phase-name", "phase-code", "phase-func", "phase-owner")
    values = {key: extract_list(html, key) for key in phase_keys}
    phase_count = max((len(items) for items in values.values()), default=0)
    phases = []
    for index in range(phase_count):
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


def parse_html_payload(html: str) -> InputPayload:
    return InputPayload(
        title=extract_single(html, "title"),
        subtitle=extract_single(html, "subtitle"),
        scope_title=extract_single(html, "scope-title"),
        scope_subtitle=extract_single(html, "scope-subtitle"),
        focus_title=extract_single(html, "focus-title"),
        focus_subtitle=extract_single(html, "focus-subtitle"),
        footer=extract_single(html, "footer"),
        phases=extract_phases(html),
        scenarios=extract_list(html, "scenario"),
        notes=extract_list(html, "note"),
    )


def validate_payload(payload: InputPayload):
    has_meaningful_content = any(
        [
            payload.title,
            payload.subtitle,
            payload.footer,
            payload.phases,
            payload.scenarios,
            payload.notes,
        ]
    )
    if not has_meaningful_content:
        raise ValueError(
            "输入 HTML 未识别到可用内容。请至少提供 title、subtitle、phase-*、scenario、note、footer 中的一部分。"
        )

    if not payload.phases and not payload.scenarios and not payload.notes:
        raise ValueError(
            "输入 HTML 缺少正文内容。请至少补充一组 phase-*、scenario 或 note，才能生成有意义的正文页。"
        )
