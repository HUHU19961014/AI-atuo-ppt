import re

from bs4 import BeautifulSoup, Tag

from ..models import InputPayload


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _class_tokens(class_pattern: str) -> list[str]:
    return [token.strip() for token in class_pattern.split() if token.strip()]


def _has_all_classes(tag: Tag, class_pattern: str) -> bool:
    classes = set(tag.get("class", []))
    return all(token in classes for token in _class_tokens(class_pattern))


def _find_first_by_classes(root: Tag | BeautifulSoup, class_pattern: str) -> Tag | None:
    tokens = _class_tokens(class_pattern)
    if not tokens:
        return None
    return root.find(lambda tag: isinstance(tag, Tag) and all(token in set(tag.get("class", [])) for token in tokens))


def _find_all_by_class(root: Tag | BeautifulSoup, class_name: str) -> list[Tag]:
    return root.find_all(class_=lambda classes: classes and class_name in classes)


def _tag_text(node: Tag | None) -> str:
    if node is None:
        return ""
    text = " ".join(node.get_text(" ", strip=True).split())
    text = re.sub(r"\s+([:：;；,.，。!?！？])", r"\1", text)
    text = re.sub(r"([(/（【])\s+", r"\1", text)
    return text.strip()


def strip_tags(s: str) -> str:
    return _tag_text(_soup(s))


def clean_heading_text(text: str) -> str:
    cleaned = strip_tags(text)
    cleaned = re.sub(r"^[^\w\u4e00-\u9fff]+", "", cleaned)
    return cleaned.strip()


def extract_single(html: str, cls: str) -> str:
    return _tag_text(_find_first_by_classes(_soup(html), cls))


def extract_list(html: str, cls: str) -> list[str]:
    return [_tag_text(node) for node in _find_all_by_class(_soup(html), cls)]


def extract_first_tag_text(html: str, tag: str) -> str:
    return _tag_text(_soup(html).find(tag))


def extract_tag_with_class(html: str, tag: str, class_name: str) -> str:
    soup = _soup(html)
    return _tag_text(
        soup.find(
            lambda node: isinstance(node, Tag) and node.name == tag and class_name in set(node.get("class", []))
        )
    )


def extract_tag_inside_block(html: str, block_class_pattern: str, tag: str) -> str:
    block = _find_first_by_classes(_soup(html), block_class_pattern)
    return _tag_text(block.find(tag) if block else None)


def extract_list_items_from_block(html: str, class_pattern: str) -> list[str]:
    block = _find_first_by_classes(_soup(html), class_pattern)
    if block is None:
        return []
    item_root = block.find("ul")
    if item_root is None:
        return []
    return [_tag_text(item) for item in item_root.find_all("li")]


def extract_steps(html: str) -> list[tuple[str, str]]:
    soup = _soup(html)
    steps = []
    for step_node in _find_all_by_class(soup, "step"):
        title = clean_heading_text(_tag_text(step_node.find("h3")))
        desc = _tag_text(step_node.find("p"))
        if title or desc:
            steps.append((title, desc))
    return steps


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
            "杈撳叆 HTML 鏈瘑鍒埌鍙敤鍐呭銆傝鑷冲皯鎻愪緵 title銆乻ubtitle銆乸hase-*銆乻cenario銆乶ote銆乫ooter 涓殑涓€閮ㄥ垎銆?"
        )

    if not payload.phases and not payload.scenarios and not payload.notes:
        raise ValueError(
            "杈撳叆 HTML 缂哄皯姝ｆ枃鍐呭銆傝鑷冲皯琛ュ厖涓€缁?phase-*銆乻cenario 鎴?note锛屾墠鑳界敓鎴愭湁鎰忎箟鐨勬鏂囬〉銆?"
        )
