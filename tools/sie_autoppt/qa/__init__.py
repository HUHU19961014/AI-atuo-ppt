from pathlib import Path

from .models import QaResult
from .report_json import write_qa_json_report
from .report_text import write_qa_text_report
from .rules import build_qa_result


def write_qa_report(pptx_path: Path, chapter_count: int, pattern_ids=None, chapter_lines=None) -> Path:
    result = build_qa_result(
        pptx_path,
        chapter_count,
        pattern_ids=pattern_ids,
        chapter_lines=chapter_lines,
    )
    write_qa_json_report(result, pptx_path)
    return write_qa_text_report(result, pptx_path)


__all__ = ["QaResult", "build_qa_result", "write_qa_report"]
