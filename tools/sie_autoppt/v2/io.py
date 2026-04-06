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
    return re.sub(r'[<>:"/\\|?*]+', "_", prefix).strip(" ._") or "SIE_AutoPPT_V2"


def _timestamp() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def build_outline_output_path(output_dir: Path, output_prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{_safe_prefix(output_prefix)}_{_timestamp()}.outline.json"


def build_deck_output_path(output_dir: Path, output_prefix: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{_safe_prefix(output_prefix)}_{_timestamp()}.deck.v2.json"


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


def default_ppt_output_path(output_dir: Path | None = None) -> Path:
    target_dir = output_dir or DEFAULT_V2_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "generated.pptx"


def default_log_output_path(output_dir: Path | None = None) -> Path:
    target_dir = output_dir or DEFAULT_V2_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "log.txt"


def write_outline_document(outline: OutlineDocument, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(outline.to_list(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def load_outline_document(outline_path: Path) -> OutlineDocument:
    data = json.loads(outline_path.read_text(encoding="utf-8"))
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


def load_deck_document(deck_path: Path) -> DeckDocument:
    data = json.loads(deck_path.read_text(encoding="utf-8"))
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
