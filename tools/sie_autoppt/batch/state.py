from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BatchState(StrEnum):
    INIT = "INIT"
    INPUT_VALIDATED = "INPUT_VALIDATED"
    PREPROCESSING = "PREPROCESSING"
    BUNDLE_READY = "BUNDLE_READY"
    SVG_GENERATING = "SVG_GENERATING"
    SVG_READY = "SVG_READY"
    EXPORTING = "EXPORTING"
    EXPORT_READY = "EXPORT_READY"
    TUNING = "TUNING"
    QA_CHECKING = "QA_CHECKING"
    REVIEW_PATCHING = "REVIEW_PATCHING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class FailureCode(StrEnum):
    RUN_ID_CONFLICT = "run_id_conflict"
    INPUT_INVALID = "input_invalid"
    PREPROCESS_FAILED = "preprocess_failed"
    PRE_EXPORT_QA_FAILED = "pre_export_qa_failed"
    BRIDGE_FAILED = "bridge_failed"
    EXPORT_INVALID = "export_invalid"
    TUNING_FAILED = "tuning_failed"
    QA_FAILED = "qa_failed"
    REVIEW_PATCH_FAILED = "review_patch_failed"
    RETRY_EXHAUSTED = "retry_exhausted"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RetryPolicy:
    preprocess_max_retries: int = 2
    bridge_max_retries: int = 3
    export_max_retries: int = 2
    tune_max_retries: int = 1
    qa_regenerate_max_retries: int = 2
