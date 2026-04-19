from __future__ import annotations

import json
import mimetypes
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from .contracts import (
    ContentBundle,
    ExportManifest,
    InputEnvelope,
    InputSource,
    QaReport,
    RunMetadata,
    RunSummary,
    SvgManifest,
)
from .dead_letter import write_dead_letter
from .export import resolve_run_artifact_path, verify_export_manifest_hash
from .hashing import sha256_file, sha256_text
from .input_guard import InputGuardConfig, validate_local_inputs, validate_text_input, validate_url
from .logging import log_error, log_usage, mark_state, write_json
from .preprocess import compute_content_bundle_hash
from .qa_router import route_qa_issues
from .state import BatchState, FailureCode, RetryPolicy
from .workspace import BatchWorkspace


@dataclass(frozen=True)
class BatchMakeRequest:
    topic: str
    brief: str
    audience: str
    language: str
    theme: str
    output_root: Path
    run_id: str
    model: str | None = None
    chapters: int | None = None
    min_slides: int | None = None
    max_slides: int | None = None
    clarify_result: dict[str, Any] | None = None
    semantic_candidate_count: int = 1
    links: tuple[str, ...] = ()
    image_files: tuple[Path, ...] = ()
    attachment_files: tuple[Path, ...] = ()
    structured_data_file: Path | None = None


class BatchRuntimeError(RuntimeError):
    def __init__(
        self,
        *,
        stage: BatchState,
        failure_code: FailureCode,
        message: str,
        retry_attempts: int = 0,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.failure_code = failure_code
        self.retry_attempts = retry_attempts


NON_RETRYABLE_BRIDGE_ERROR_PATTERNS = (
    "unsupported slide intent",
    "unsupported layout intent",
    "contract mismatch",
)

IMAGE_INPUT_GUARD = InputGuardConfig(
    max_bytes=10 * 1024 * 1024,
    allowed_suffixes={".png", ".jpg", ".jpeg", ".webp", ".bmp"},
)
ATTACHMENT_INPUT_GUARD = InputGuardConfig(
    max_bytes=20 * 1024 * 1024,
    allowed_suffixes={
        ".pdf",
        ".doc",
        ".docx",
        ".ppt",
        ".pptx",
        ".xls",
        ".xlsx",
        ".txt",
        ".md",
        ".markdown",
        ".csv",
        ".json",
    },
)
STRUCTURED_INPUT_GUARD = InputGuardConfig(max_bytes=10 * 1024 * 1024, allowed_suffixes={".json"})


def run_batch_make(
    *,
    request: BatchMakeRequest,
    preprocess_fn: Callable[..., dict[str, Any]],
    bridge_fn: Callable[..., dict[str, Any]],
    tuning_fn: Callable[..., Any],
    qa_fn: Callable[..., dict[str, Any]],
    bridge_root: Path,
    pre_export_qa_fn: Callable[..., dict[str, Any]] | None = None,
    review_patch_fn: Callable[..., dict[str, Any]] | None = None,
    retry_policy: RetryPolicy | None = None,
) -> dict[str, Any]:
    run_started_monotonic = time.monotonic()
    llm_usage_before = _read_llm_usage_counters()
    ai_five_stage_mode = "ai_five_stage" if (pre_export_qa_fn is not None or review_patch_fn is not None) else "legacy"

    try:
        workspace = BatchWorkspace.create(root=request.output_root, run_id=request.run_id)
    except FileExistsError as exc:
        return {
            "state": BatchState.FAILED.value,
            "run_id": request.run_id,
            "error": str(exc),
        }

    policy = retry_policy or RetryPolicy()
    current_state = BatchState.INIT
    run_meta = RunMetadata(run_id=request.run_id)
    bundle: dict[str, Any] | None = None
    export_manifest_payload: dict[str, Any] | None = None
    qa_report_payload: dict[str, Any] | None = None
    qa_report_model: QaReport | None = None
    review_patch_payload: dict[str, Any] | None = None

    try:
        (workspace.logs_dir / "spans.jsonl").touch(exist_ok=True)
        (workspace.logs_dir / "usage.jsonl").touch(exist_ok=True)
        (workspace.logs_dir / "errors.jsonl").touch(exist_ok=True)
        mark_state(workspace, current_state, "run initialized")
        log_usage(workspace, stage=current_state, payload={"run_id": request.run_id})
        write_json(
            workspace.run_dir / "run.json",
            {
                "run": run_meta.model_dump(mode="json"),
                "state": current_state.value,
            },
        )

        try:
            input_envelope = _build_input_envelope(
                request=request,
                workspace=workspace,
                run_meta=run_meta,
            )
        except ValueError as exc:
            raise BatchRuntimeError(
                stage=BatchState.INIT,
                failure_code=FailureCode.INPUT_INVALID,
                message=f"input validation failed: {exc}",
            ) from exc
        write_json(workspace.input_dir / "input_envelope.json", input_envelope.model_dump(mode="json"))
        current_state = BatchState.INPUT_VALIDATED
        mark_state(workspace, current_state, "input envelope accepted")
        log_usage(workspace, stage=current_state, payload={"inputs": len(input_envelope.inputs)})

        bundle = _run_with_retries(
            workspace=workspace,
            state=BatchState.PREPROCESSING,
            failure_code=FailureCode.PREPROCESS_FAILED,
            max_retries=policy.preprocess_max_retries,
            action=lambda: preprocess_fn(
                run_id=request.run_id,
                topic=request.topic,
                brief=request.brief,
                audience=request.audience,
                language=request.language,
                theme=request.theme,
                model=request.model,
                chapters=request.chapters,
                min_slides=request.min_slides,
                max_slides=request.max_slides,
                clarify_result=request.clarify_result,
                semantic_candidate_count=request.semantic_candidate_count,
                input_envelope=input_envelope.model_dump(mode="json"),
            ),
        )
        bundle = _normalize_bundle(run_id=request.run_id, bundle=bundle)
        write_json(workspace.preprocess_dir / "content_bundle.json", bundle)
        _write_preprocess_side_artifacts(workspace=workspace, bundle=bundle)
        current_state = BatchState.BUNDLE_READY
        mark_state(workspace, current_state, "content bundle ready")
        log_usage(workspace, stage=current_state, payload={"bundle_hash": bundle["bundle_hash"]})

        if pre_export_qa_fn is not None:
            pre_export_qa = QaReport.model_validate(pre_export_qa_fn(run_id=request.run_id, bundle=bundle))
            write_json(
                workspace.qa_dir / "pre_export_qa_report.json",
                pre_export_qa.model_dump(mode="json", by_alias=True),
            )
            if pre_export_qa.status != "passed":
                raise BatchRuntimeError(
                    stage=BatchState.BUNDLE_READY,
                    failure_code=FailureCode.PRE_EXPORT_QA_FAILED,
                    message=f"pre-export semantic QA blocked: route={pre_export_qa.route}",
                )

        export_manifest_payload = _run_generation_and_export(
            request=request,
            workspace=workspace,
            bridge_fn=bridge_fn,
            bridge_root=bridge_root,
            bundle=bundle,
            policy=policy,
        )
        current_state = BatchState.EXPORT_READY

        tuning_result: Any = None
        tune_attempt = 0
        regenerate_attempt = 0
        while True:
            tune_attempt += 1
            current_state = BatchState.TUNING
            mark_state(workspace, current_state, "tuning started", attempt=tune_attempt)
            log_usage(workspace, stage=current_state, payload={"attempt": tune_attempt})
            try:
                tuning_result = tuning_fn(
                    workspace=workspace,
                    export_manifest=export_manifest_payload,
                )
            except Exception as exc:
                log_error(
                    workspace,
                    stage=current_state,
                    error_code=FailureCode.TUNING_FAILED.value,
                    message=str(exc),
                    attempt=tune_attempt,
                )
                if tune_attempt <= policy.tune_max_retries:
                    continue
                raise BatchRuntimeError(
                    stage=current_state,
                    failure_code=FailureCode.TUNING_FAILED,
                    message=f"tuning failed after retries: {exc}",
                    retry_attempts=tune_attempt - 1,
                ) from exc
            if isinstance(tuning_result, dict):
                write_json(workspace.tune_dir / "tune_report.json", tuning_result)

            current_state = BatchState.QA_CHECKING
            mark_state(workspace, current_state, "post-export QA started", attempt=tune_attempt)
            log_usage(workspace, stage=current_state, payload={"attempt": tune_attempt})
            qa_report_model = QaReport.model_validate(
                qa_fn(
                    workspace=workspace,
                    export_manifest=export_manifest_payload,
                    tuning_result=tuning_result,
                )
            )
            qa_report_payload = qa_report_model.model_dump(mode="json", by_alias=True)
            write_json(workspace.qa_dir / "qa_report.json", qa_report_payload)
            if qa_report_model.status == "passed":
                break

            route = qa_report_model.route or route_qa_issues(
                [issue.model_dump(mode="json", by_alias=True) for issue in qa_report_model.issues]
            )
            if qa_report_model.status == "repairable" and route == "tune" and tune_attempt <= policy.tune_max_retries:
                continue
            if qa_report_model.status == "repairable" and route == "regenerate":
                regenerate_attempt += 1
                if regenerate_attempt > policy.qa_regenerate_max_retries:
                    raise BatchRuntimeError(
                        stage=current_state,
                        failure_code=FailureCode.RETRY_EXHAUSTED,
                        message=f"QA regenerate retries exhausted: {regenerate_attempt}",
                        retry_attempts=regenerate_attempt,
                    )
                export_manifest_payload = _run_generation_and_export(
                    request=request,
                    workspace=workspace,
                    bridge_fn=bridge_fn,
                    bridge_root=bridge_root,
                    bundle=bundle,
                    policy=policy,
                )
                tune_attempt = 0
                continue
            raise BatchRuntimeError(
                stage=current_state,
                failure_code=FailureCode.QA_FAILED,
                message=f"QA did not pass: status={qa_report_model.status}, route={route}",
            )

        tuned_pptx_path = _resolve_tuned_pptx_path(
            run_dir=workspace.run_dir,
            tuning_result=tuning_result,
            export_manifest=export_manifest_payload,
        )
        if review_patch_fn is not None:
            current_state = BatchState.REVIEW_PATCHING
            mark_state(workspace, current_state, "review patch stage started")
            log_usage(workspace, stage=current_state, payload={"mode": "single_round"})
            try:
                review_patch_payload = review_patch_fn(
                    workspace=workspace,
                    request=request,
                    bundle=bundle,
                    export_manifest=export_manifest_payload,
                    tuning_result=tuning_result,
                )
            except Exception as exc:
                log_error(
                    workspace,
                    stage=current_state,
                    error_code=FailureCode.REVIEW_PATCH_FAILED.value,
                    message=str(exc),
                )
                raise BatchRuntimeError(
                    stage=current_state,
                    failure_code=FailureCode.REVIEW_PATCH_FAILED,
                    message=f"review patch failed: {exc}",
                ) from exc
            if isinstance(review_patch_payload, dict):
                write_json(workspace.qa_dir / "review_patch_report.json", review_patch_payload)

        final_pptx_path = workspace.final_dir / "final.pptx"
        shutil.copy2(tuned_pptx_path, final_pptx_path)
        shape_map_mode = _resolve_shape_map_mode(export_manifest=export_manifest_payload)
        degraded_mode, degraded_reasons = _resolve_degraded_status(
            shape_map_mode=shape_map_mode,
            qa_report=qa_report_model,
        )
        llm_usage_delta = _diff_llm_usage(_read_llm_usage_counters(), llm_usage_before)
        run_summary = RunSummary(
            run_id=request.run_id,
            final_state=BatchState.SUCCEEDED.value,
            final_pptx=final_pptx_path.relative_to(workspace.run_dir).as_posix(),
            bundle_hash=str(bundle["bundle_hash"]),
            export_hash=str(export_manifest_payload["export_hash"]),
            shape_map_mode=shape_map_mode,
            degraded_mode=degraded_mode,
            degraded_reasons=degraded_reasons,
            retry_attempts_total=_count_retry_attempts(workspace=workspace),
            total_latency_ms=max(0, int((time.monotonic() - run_started_monotonic) * 1000)),
            llm_input_tokens=max(0, int(llm_usage_delta["input_tokens"])),
            llm_output_tokens=max(0, int(llm_usage_delta["output_tokens"])),
            llm_total_tokens=max(0, int(llm_usage_delta["total_tokens"])),
            llm_total_cost_usd=max(0.0, float(llm_usage_delta["total_cost_usd"])),
            ai_five_stage_mode=ai_five_stage_mode,
        )
        write_json(workspace.final_dir / "run_summary.json", run_summary.model_dump(mode="json"))

        current_state = BatchState.SUCCEEDED
        mark_state(workspace, current_state, "run succeeded")
        log_usage(workspace, stage=current_state, payload={"final_pptx": run_summary.final_pptx})
        return {
            "state": current_state.value,
            "run_id": request.run_id,
            "workspace": workspace,
            "final_pptx": str(final_pptx_path),
        }
    except BatchRuntimeError as exc:
        _write_failure_artifacts(
            workspace=workspace,
            run_id=request.run_id,
            stage=exc.stage,
            failure_code=exc.failure_code.value,
            message=str(exc),
            retry_attempts=exc.retry_attempts,
            bundle_hash=(bundle or {}).get("bundle_hash", ""),
            export_hash=(export_manifest_payload or {}).get("export_hash", ""),
            qa_route=(qa_report_payload or {}).get("route", ""),
        )
        return {
            "state": BatchState.FAILED.value,
            "run_id": request.run_id,
            "workspace": workspace,
            "error": str(exc),
        }
    except Exception as exc:
        _write_failure_artifacts(
            workspace=workspace,
            run_id=request.run_id,
            stage=current_state,
            failure_code=FailureCode.UNKNOWN.value,
            message=str(exc),
            retry_attempts=0,
            bundle_hash=(bundle or {}).get("bundle_hash", ""),
            export_hash=(export_manifest_payload or {}).get("export_hash", ""),
            qa_route=(qa_report_payload or {}).get("route", ""),
        )
        return {
            "state": BatchState.FAILED.value,
            "run_id": request.run_id,
            "workspace": workspace,
            "error": str(exc),
        }


def _normalize_bundle(*, run_id: str, bundle: dict[str, Any]) -> dict[str, Any]:
    normalized = ContentBundle.model_validate(bundle).model_dump(mode="json")
    normalized["run_id"] = run_id
    normalized["bundle_hash"] = compute_content_bundle_hash(normalized)
    return ContentBundle.model_validate(normalized).model_dump(mode="json")


def _run_with_retries(
    *,
    workspace: BatchWorkspace,
    state: BatchState,
    failure_code: FailureCode,
    max_retries: int,
    action: Callable[[], Any],
) -> Any:
    for attempt in range(1, max_retries + 2):
        mark_state(workspace, state, "attempt start", attempt=attempt)
        log_usage(workspace, stage=state, payload={"attempt": attempt})
        try:
            return action()
        except Exception as exc:
            log_error(
                workspace,
                stage=state,
                error_code=failure_code.value,
                message=str(exc),
                attempt=attempt,
            )
            if _is_non_retryable_error(state=state, exc=exc):
                raise BatchRuntimeError(
                    stage=state,
                    failure_code=failure_code,
                    message=f"{state.value} non-retryable failure: {exc}",
                    retry_attempts=attempt - 1,
                ) from exc
            if attempt > max_retries:
                raise BatchRuntimeError(
                    stage=state,
                    failure_code=failure_code,
                    message=f"{state.value} failed after retries: {exc}",
                    retry_attempts=attempt - 1,
                ) from exc
    raise AssertionError("retry loop exhausted unexpectedly")


def _run_generation_and_export(
    *,
    request: BatchMakeRequest,
    workspace: BatchWorkspace,
    bridge_fn: Callable[..., dict[str, Any]],
    bridge_root: Path,
    bundle: dict[str, Any],
    policy: RetryPolicy,
) -> dict[str, Any]:
    bridge_payload = _run_with_retries(
        workspace=workspace,
        state=BatchState.SVG_GENERATING,
        failure_code=FailureCode.BRIDGE_FAILED,
        max_retries=policy.bridge_max_retries,
        action=lambda: bridge_fn(
            workspace=workspace,
            bundle=bundle,
            bridge_root=bridge_root,
        ),
    )
    bridge_payload, bridge_attempt = _materialize_bridge_payload(
        workspace=workspace,
        bridge_payload=bridge_payload,
        bundle_hash=str(bundle["bundle_hash"]),
    )

    for export_attempt in range(1, policy.export_max_retries + 2):
        mark_state(workspace, BatchState.EXPORTING, "export verification attempt", attempt=export_attempt)
        log_usage(workspace, stage=BatchState.EXPORTING, payload={"attempt": export_attempt})
        try:
            export_manifest = ExportManifest(
                run_id=request.run_id,
                bundle_hash=str(bundle["bundle_hash"]),
                svg_bundle_hash=str(bridge_payload["svg_bundle_hash"]),
                export_hash=str(bridge_payload["export_hash"]),
                exporter_version=str(bridge_payload.get("exporter_version", "pptmaster-bridge-v1")),
                pptx_path=str(bridge_payload["pptx_path"]),
                shape_map=list(bridge_payload["shape_map"]),
                shape_map_mode=str(bridge_payload.get("shape_map_mode", "heuristic")),
            )
            verify_export_manifest_hash(
                run_dir=workspace.run_dir,
                pptx_path=export_manifest.pptx_path,
                expected_hash=export_manifest.export_hash,
            )
            payload = export_manifest.model_dump(mode="json")
            write_json(workspace.bridge_dir / "export_manifest.json", payload)
            _write_bridge_attempt_artifact(
                workspace=workspace,
                stem="export_manifest",
                attempt=bridge_attempt,
                payload=payload,
            )
            mark_state(workspace, BatchState.EXPORT_READY, "export manifest verified", attempt=export_attempt)
            log_usage(workspace, stage=BatchState.EXPORT_READY, payload={"export_hash": payload["export_hash"]})
            return payload
        except Exception as exc:
            log_error(
                workspace,
                stage=BatchState.EXPORTING,
                error_code=FailureCode.EXPORT_INVALID.value,
                message=str(exc),
                attempt=export_attempt,
            )
            if _is_non_retryable_error(state=BatchState.EXPORTING, exc=exc):
                raise BatchRuntimeError(
                    stage=BatchState.EXPORTING,
                    failure_code=FailureCode.EXPORT_INVALID,
                    message=f"export manifest validation failed: {exc}",
                    retry_attempts=export_attempt - 1,
                ) from exc
            if export_attempt > policy.export_max_retries:
                raise BatchRuntimeError(
                    stage=BatchState.EXPORTING,
                    failure_code=FailureCode.EXPORT_INVALID,
                    message=f"export verification failed after retries: {exc}",
                    retry_attempts=export_attempt - 1,
                ) from exc
            bridge_payload = bridge_fn(
                workspace=workspace,
                bundle=bundle,
                bridge_root=bridge_root,
            )
            bridge_payload, bridge_attempt = _materialize_bridge_payload(
                workspace=workspace,
                bridge_payload=bridge_payload,
                bundle_hash=str(bundle["bundle_hash"]),
            )
    raise AssertionError("export loop exhausted unexpectedly")


def _is_non_retryable_error(*, state: BatchState, exc: Exception) -> bool:
    if isinstance(exc, ValidationError):
        return True
    message = str(exc).lower()
    if state == BatchState.SVG_GENERATING:
        return any(pattern in message for pattern in NON_RETRYABLE_BRIDGE_ERROR_PATTERNS)
    return False


def _materialize_bridge_payload(
    *,
    workspace: BatchWorkspace,
    bridge_payload: dict[str, Any],
    bundle_hash: str,
) -> tuple[dict[str, Any], int]:
    attempt = _allocate_bridge_attempt(workspace=workspace)
    if "svg_manifest" in bridge_payload:
        svg_manifest = SvgManifest.model_validate(bridge_payload["svg_manifest"])
        payload = svg_manifest.model_dump(mode="json")
        write_json(workspace.bridge_dir / "svg_manifest.json", payload)
        _write_bridge_attempt_artifact(
            workspace=workspace,
            stem="svg_manifest",
            attempt=attempt,
            payload=payload,
        )
    mark_state(workspace, BatchState.SVG_READY, "svg manifest ready", attempt=attempt)
    log_usage(workspace, stage=BatchState.SVG_READY, payload={"bundle_hash": bundle_hash, "bridge_attempt": attempt})
    return bridge_payload, attempt


def _allocate_bridge_attempt(*, workspace: BatchWorkspace) -> int:
    attempts_dir = workspace.bridge_dir / "attempts"
    attempts_dir.mkdir(parents=True, exist_ok=True)
    max_attempt = 0
    for candidate in attempts_dir.glob("*.attempt-*.json"):
        marker = ".attempt-"
        suffix = candidate.name.split(marker, 1)[-1]
        raw_number = suffix.split(".", 1)[0]
        if raw_number.isdigit():
            max_attempt = max(max_attempt, int(raw_number))
    return max_attempt + 1


def _write_bridge_attempt_artifact(
    *,
    workspace: BatchWorkspace,
    stem: str,
    attempt: int,
    payload: dict[str, Any],
) -> None:
    attempts_dir = workspace.bridge_dir / "attempts"
    attempts_dir.mkdir(parents=True, exist_ok=True)
    write_json(attempts_dir / f"{stem}.attempt-{attempt:03d}.json", payload)


def _resolve_tuned_pptx_path(*, run_dir: Path, tuning_result: Any, export_manifest: dict[str, Any]) -> Path:
    if isinstance(tuning_result, dict):
        candidate = tuning_result.get("pptx_path")
        if candidate:
            return resolve_run_artifact_path(run_dir=run_dir, artifact_path=str(candidate))
    return resolve_run_artifact_path(run_dir=run_dir, artifact_path=str(export_manifest["pptx_path"]))


def _resolve_shape_map_mode(*, export_manifest: dict[str, Any]) -> str:
    mode = str(export_manifest.get("shape_map_mode", "heuristic") or "heuristic").strip().lower()
    return "mapped" if mode == "mapped" else "heuristic"


def _resolve_degraded_status(*, shape_map_mode: str, qa_report: QaReport | None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if qa_report is not None:
        reasons.extend(str(reason).strip() for reason in qa_report.degraded_reasons if str(reason).strip())
    if shape_map_mode == "heuristic" and not any("shape_map_mode=heuristic" in reason for reason in reasons):
        reasons.append("shape_map_mode=heuristic; fallback shape mapping in use.")
    degraded_mode = bool((qa_report.degraded_mode if qa_report is not None else False) or reasons)
    return degraded_mode, reasons


def _read_llm_usage_counters() -> dict[str, float]:
    try:
        from ..llm_openai import OpenAIResponsesClient

        counters = OpenAIResponsesClient.usage_counters()
    except Exception:
        counters = {}
    return {
        "input_tokens": float(counters.get("input_tokens", 0.0)),
        "output_tokens": float(counters.get("output_tokens", 0.0)),
        "total_tokens": float(counters.get("total_tokens", 0.0)),
        "total_cost_usd": float(counters.get("total_cost_usd", 0.0)),
    }


def _diff_llm_usage(current: dict[str, float], previous: dict[str, float]) -> dict[str, float]:
    return {
        "input_tokens": max(0.0, float(current.get("input_tokens", 0.0)) - float(previous.get("input_tokens", 0.0))),
        "output_tokens": max(
            0.0,
            float(current.get("output_tokens", 0.0)) - float(previous.get("output_tokens", 0.0)),
        ),
        "total_tokens": max(0.0, float(current.get("total_tokens", 0.0)) - float(previous.get("total_tokens", 0.0))),
        "total_cost_usd": max(
            0.0,
            float(current.get("total_cost_usd", 0.0)) - float(previous.get("total_cost_usd", 0.0)),
        ),
    }


def _count_retry_attempts(*, workspace: BatchWorkspace) -> int:
    usage_path = workspace.logs_dir / "usage.jsonl"
    if not usage_path.exists():
        return 0
    retry_attempts = 0
    for line in usage_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        usage_payload = payload.get("payload", {}) if isinstance(payload, dict) else {}
        if not isinstance(usage_payload, dict):
            continue
        attempt = usage_payload.get("attempt")
        if isinstance(attempt, int) and attempt > 1:
            retry_attempts += 1
    return retry_attempts


def _write_preprocess_side_artifacts(*, workspace: BatchWorkspace, bundle: dict[str, Any]) -> None:
    images = list(bundle.get("images") or [])
    clarify_result = bundle.get("clarify_result")
    if not isinstance(clarify_result, dict):
        text_summary = bundle.get("text_summary") if isinstance(bundle.get("text_summary"), dict) else {}
        clarify_result = {
            "status": "not_available",
            "topic": str(bundle.get("topic") or ""),
            "brief": str(text_summary.get("summary") or ""),
            "audience": str(bundle.get("audience") or ""),
        }
    write_json(workspace.preprocess_dir / "clarify_result.json", clarify_result)
    write_json(
        workspace.preprocess_dir / "planning.json",
        {
            "run_id": bundle.get("run_id"),
            "story_plan": bundle.get("story_plan") or {"outline": []},
        },
    )
    write_json(
        workspace.preprocess_dir / "ocr.json",
        {
            "run_id": bundle.get("run_id"),
            "images": [
                {
                    "image_ref": image.get("image_ref"),
                    "content_hash": image.get("content_hash"),
                    "ocr_text": image.get("ocr_text", ""),
                    "source_refs": image.get("source_refs", []),
                }
                for image in images
            ],
        },
    )
    write_json(
        workspace.preprocess_dir / "image_descriptions.json",
        {
            "run_id": bundle.get("run_id"),
            "images": [
                {
                    "image_ref": image.get("image_ref"),
                    "content_hash": image.get("content_hash"),
                    "description": image.get("description", ""),
                    "source_refs": image.get("source_refs", []),
                }
                for image in images
            ],
        },
    )


def _build_input_envelope(
    *,
    request: BatchMakeRequest,
    workspace: BatchWorkspace,
    run_meta: RunMetadata,
) -> InputEnvelope:
    inputs: list[InputSource] = []
    input_text = "\n".join(part for part in (request.topic, request.brief) if part).strip() or request.topic
    validate_text_input(input_text)
    topic_path = workspace.input_source_dir / "topic.txt"
    topic_path.write_text(input_text, encoding="utf-8")
    inputs.append(
        InputSource(
            source_ref="src-topic",
            type="text",
            path=topic_path.relative_to(workspace.run_dir).as_posix(),
            content_hash=sha256_text(input_text),
            mime_type="text/plain",
            size_bytes=len(input_text.encode("utf-8")),
            safe=True,
        )
    )

    for index, link in enumerate(request.links, start=1):
        normalized_link = validate_text_input(link, max_bytes=8 * 1024)
        validate_url(normalized_link)
        link_path = workspace.input_source_dir / f"link-{index:03d}.url"
        link_path.write_text(normalized_link, encoding="utf-8")
        inputs.append(
            InputSource(
                source_ref=f"src-link-{index:03d}",
                type="link",
                path=link_path.relative_to(workspace.run_dir).as_posix(),
                content_hash=sha256_text(normalized_link),
                mime_type="text/uri-list",
                size_bytes=len(normalized_link.encode("utf-8")),
                safe=True,
            )
        )

    for index, image_path in enumerate(request.image_files, start=1):
        inputs.append(
            _stage_file_input(
                workspace=workspace,
                source_path=image_path,
                source_ref=f"src-image-{index:03d}",
                input_type="image",
                staged_name=f"image-{index:03d}{image_path.suffix.lower()}",
                default_mime="image/*",
                guard_config=IMAGE_INPUT_GUARD,
            )
        )

    for index, attachment_path in enumerate(request.attachment_files, start=1):
        inputs.append(
            _stage_file_input(
                workspace=workspace,
                source_path=attachment_path,
                source_ref=f"src-attachment-{index:03d}",
                input_type="attachment",
                staged_name=f"attachment-{index:03d}{attachment_path.suffix.lower()}",
                default_mime="application/octet-stream",
                guard_config=ATTACHMENT_INPUT_GUARD,
            )
        )

    if request.structured_data_file is not None:
        structured_path = request.structured_data_file
        suffix = structured_path.suffix.lower() or ".json"
        inputs.append(
            _stage_file_input(
                workspace=workspace,
                source_path=structured_path,
                source_ref="src-data-001",
                input_type="structured_data",
                staged_name=f"structured-data-001{suffix}",
                default_mime="application/json",
                guard_config=STRUCTURED_INPUT_GUARD,
            )
        )

    return InputEnvelope(
        run_id=run_meta.run_id,
        created_at=run_meta.created_at,
        mode=run_meta.mode,
        inputs=inputs,
    )


def _stage_file_input(
    *,
    workspace: BatchWorkspace,
    source_path: Path,
    source_ref: str,
    input_type: str,
    staged_name: str,
    default_mime: str,
    guard_config: InputGuardConfig,
) -> InputSource:
    validate_local_inputs([source_path], config=guard_config)
    staged_path = workspace.input_source_dir / staged_name
    shutil.copy2(source_path, staged_path)
    mime_type = mimetypes.guess_type(source_path.name)[0] or default_mime
    size_bytes = staged_path.stat().st_size
    return InputSource(
        source_ref=source_ref,
        type=input_type,
        path=staged_path.relative_to(workspace.run_dir).as_posix(),
        content_hash=sha256_file(staged_path),
        mime_type=mime_type,
        size_bytes=size_bytes,
        safe=True,
    )


def _write_failure_artifacts(
    *,
    workspace: BatchWorkspace,
    run_id: str,
    stage: BatchState,
    failure_code: str,
    message: str,
    retry_attempts: int,
    bundle_hash: str,
    export_hash: str,
    qa_route: str,
) -> None:
    write_dead_letter(
        run_dir=workspace.run_dir,
        payload={
            "run_id": run_id,
            "stage": stage.value,
            "failure_code": failure_code,
            "error_code": failure_code,
            "message": message,
            "retry_attempts": retry_attempts,
            "bundle_hash": bundle_hash,
            "export_hash": export_hash,
            "qa_route": qa_route,
        },
    )
    log_error(
        workspace,
        stage=stage,
        error_code=failure_code,
        message=message,
        attempt=max(1, retry_attempts),
    )
    mark_state(workspace, BatchState.FAILED, "run failed")
    log_usage(workspace, stage=BatchState.FAILED, payload={"failure_code": failure_code})
