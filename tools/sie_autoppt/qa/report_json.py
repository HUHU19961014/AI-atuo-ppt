import json
from pathlib import Path

from .models import QaResult


def write_qa_json_report(result: QaResult, pptx_path: Path) -> Path:
    report = pptx_path.with_name(pptx_path.stem + "_QA.json")
    report.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report
