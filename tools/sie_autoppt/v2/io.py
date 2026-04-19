from __future__ import annotations

import datetime
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .schema import DeckDocument, OutlineDocument, validate_deck_payload


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_V2_OUTPUT_DIR = PROJECT_ROOT / "output"


def _safe_prefix(prefix: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", prefix).strip(" ._") or "Enterprise-AI-PPT-V2"


def _timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def _read_json_file(json_path: Path) -> object:
    return json.loads(json_path.read_text(encoding="utf-8-sig"))


def build_outline_output_path(output_dir: Path, output_prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{_safe_prefix(output_prefix)}_{_timestamp()}.outline.json"


def build_deck_output_path(output_dir: Path, output_prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{_safe_prefix(output_prefix)}_{_timestamp()}.deck.v2.json"


def build_semantic_output_path(output_dir: Path, output_prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{_safe_prefix(output_prefix)}_{_timestamp()}.semantic.v2.json"


def build_ppt_output_path(output_dir: Path, output_prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{_safe_prefix(output_prefix)}_{_timestamp()}.pptx"


def build_log_output_path(output_dir: Path, output_prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{_safe_prefix(output_prefix)}_{_timestamp()}.log.txt"


def default_outline_output_path(output_dir: Path | None = None) -> Path:
    target_dir = output_dir or DEFAULT_V2_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "generated_outline.json"


def default_deck_output_path(output_dir: Path | None = None) -> Path:
    target_dir = output_dir or DEFAULT_V2_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "generated_deck.json"


def default_semantic_output_path(output_dir: Path | None = None) -> Path:
    target_dir = output_dir or DEFAULT_V2_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "generated_semantic_deck.json"


def default_ppt_output_path(output_dir: Path | None = None) -> Path:
    target_dir = output_dir or DEFAULT_V2_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "Enterprise-AI-PPT_Presentation.pptx"


def default_log_output_path(output_dir: Path | None = None) -> Path:
    target_dir = output_dir or DEFAULT_V2_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "log.txt"


def write_outline_document(outline: OutlineDocument, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(outline.to_payload(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def load_outline_document(outline_path: Path) -> OutlineDocument:
    data = _read_json_file(outline_path)
    if isinstance(data, list):
        return OutlineDocument.model_validate({"pages": data})
    if isinstance(data, dict) and "pages" in data:
        return OutlineDocument.model_validate(data)
    raise ValueError("outline JSON must be either an array of pages or an object with a pages field.")


def write_deck_document(deck: DeckDocument, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(deck.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def write_semantic_document(payload: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def load_semantic_document(semantic_path: Path) -> dict:
    data = _read_json_file(semantic_path)
    if not isinstance(data, dict):
        raise ValueError("semantic deck JSON must be an object.")
    return data


def _is_semantic_deck_payload(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    slides = data.get("slides", [])
    if not isinstance(slides, list) or not slides:
        return False
    first_slide = slides[0]
    return isinstance(first_slide, dict) and ("intent" in first_slide or "blocks" in first_slide)


def is_semantic_deck_document(deck_path: Path) -> bool:
    return _is_semantic_deck_payload(_read_json_file(deck_path))


def load_deck_document(deck_path: Path) -> DeckDocument:
    data = _read_json_file(deck_path)
    if not isinstance(data, dict):
        raise ValueError("deck JSON must be an object.")
    if _is_semantic_deck_payload(data):
        from .deck_director import compile_semantic_deck_payload

        return compile_semantic_deck_payload(data).deck
    return validate_deck_payload(data).deck


@dataclass
class RenderLog:
    lines: list[str] = field(default_factory=list)

    def info(self, message: str) -> None:
        self.lines.append(f"INFO: {message}")

    def warn(self, message: str) -> None:
        self.lines.append(f"WARN: {message}")

    def error(self, message: str) -> None:
        self.lines.append(f"ERROR: {message}")

    def extend(self, messages: Iterable[str]) -> None:
        for message in messages:
            self.warn(str(message))

    def write(self, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(self.lines).strip()
        output_path.write_text(content + ("\n" if content else ""), encoding="utf-8")
        return output_path
