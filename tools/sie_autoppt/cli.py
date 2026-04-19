from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from tools.scenario_generators.sie_onepage_designer import build_onepage_brief_from_structure, build_onepage_slide

from . import cli_routing
from .batch.input_guard import InputGuardConfig, validate_local_inputs, validate_text_input, validate_url
from .batch.orchestrator import BatchMakeRequest, run_batch_make
from .batch.pptmaster_bridge import BridgeConfig, resolve_bridge_root, run_pptmaster_bridge
from .batch.preprocess import build_content_bundle, load_content_bundle_artifact
from .batch.qa_router import run_basic_qa, run_pre_export_semantic_qa
from .batch.review_patch import run_batch_review_patch_once
from .batch.rollout import resolve_ai_five_stage_rollout
from .batch.tuning import run_noop_tuning
from .clarifier import DEFAULT_AUDIENCE_HINT, clarify_user_input, derive_planning_context, load_clarifier_session
from .clarify_web import serve_clarifier_web
from .cli_parser import build_main_parser
from .cli_sie import handle_pre_v2_command
from .cli_utils import (
    build_template_output_stem,
    emit_progress,
    load_brief_text,
    validate_slide_args,
    write_json_artifact,
)
from .cli_v2_commands import V2CommandContext, handle_v2_and_health_command
from .config import (
    DEFAULT_OUTPUT_DIR,
)
from .deck_spec_io import load_deck_spec
from .exceptions import (
    CliExecutionError,
)
from .healthcheck import run_ai_healthcheck
from .llm_openai import (
    OpenAIConfigurationError,
    OpenAIResponsesError,
)
from .models import StructureSpec
from .v2 import (
    compile_semantic_deck_payload,
    default_deck_output_path,
    default_log_output_path,
    default_outline_output_path,
    default_ppt_output_path,
    default_semantic_output_path,
    generate_outline_with_ai,
    generate_semantic_deck_with_ai,
    generate_semantic_decks_with_ai_batch,
    load_deck_document,
    load_outline_document,
    make_v2_ppt,
    write_deck_document,
    write_outline_document,
    write_semantic_document,
)
from .v2 import (
    generate_ppt as generate_v2_ppt,
)
from .v2.io import DEFAULT_V2_OUTPUT_DIR
from .v2.review_patch import apply_patch as apply_review_patch
from .v2.review_patch import review_once as review_patch_once
from .v2.services import ensure_generation_context
from .v2.visual_review import iterate_visual_review
from .visual_service import generate_visual_draft_artifacts

LOGGER = logging.getLogger(__name__)
apply_patch_set = apply_review_patch
review_deck_once = review_patch_once

WORKFLOW_COMMANDS = (
    "make",
    "batch-make",
    "onepage",
    "ai-check",
    "clarify",
    "clarify-web",
    "v2-outline",
    "v2-plan",
    "v2-compile",
    "v2-patch",
    "v2-render",
    "v2-make",
    "v2-review",
    "v2-iterate",
    "review",
    "iterate",
    "visual-draft",
)
PRIMARY_COMMANDS = ("make", "review", "iterate")
ADVANCED_COMMANDS = (
    "onepage",
    "batch-make",
    "v2-plan",
    "v2-render",
    "v2-compile",
    "v2-patch",
    "v2-outline",
    "v2-make",
    "v2-review",
    "v2-iterate",
    "clarify",
    "clarify-web",
    "ai-check",
    "visual-draft",
)
COMMAND_ALIASES = {
    "review": "v2-review",
    "iterate": "v2-iterate",
}


def command_was_explicit(argv: list[str]) -> bool:
    return cli_routing.command_was_explicit(argv, WORKFLOW_COMMANDS)


def normalize_command_alias(command_name: str) -> str:
    return cli_routing.normalize_command_alias(command_name, COMMAND_ALIASES)


def validate_command_name(command_name: str, parser: argparse.ArgumentParser) -> None:
    cli_routing.validate_command_name(
        command_name,
        parser,
        workflow_commands=WORKFLOW_COMMANDS,
        command_aliases=COMMAND_ALIASES,
        primary_commands=PRIMARY_COMMANDS,
        advanced_commands=ADVANCED_COMMANDS,
    )


def resolve_effective_command(argv: list[str], args) -> tuple[str, bool]:
    return cli_routing.resolve_effective_command(
        argv,
        args,
        workflow_commands=WORKFLOW_COMMANDS,
        command_aliases=COMMAND_ALIASES,
    )


def emit_command_notice(explicit: bool, parsed_command: str, effective_command: str) -> None:
    message = cli_routing.emit_command_notice(explicit, parsed_command, effective_command, COMMAND_ALIASES)
    if message:
        print(message, file=sys.stderr)


def option_was_explicit(argv: list[str], option_name: str) -> bool:
    return cli_routing.option_was_explicit(argv, option_name)


def is_v2_command(command_name: str) -> bool:
    return cli_routing.is_v2_command(command_name)


def validate_v2_option_compatibility(
    argv: list[str],
    *,
    effective_command: str,
    parser: argparse.ArgumentParser,
) -> None:
    cli_routing.validate_v2_option_compatibility(argv, effective_command=effective_command, parser=parser)


def validate_delivery_target_compatibility(
    *,
    args,
    explicit_command: bool,
    effective_command: str,
    parser: argparse.ArgumentParser,
) -> None:
    cli_routing.validate_delivery_target_compatibility(
        args=args,
        explicit_command=explicit_command,
        effective_command=effective_command,
        parser=parser,
    )


def resolve_v2_output_dir(*, output_dir: Path, args) -> Path:
    return cli_routing.resolve_v2_output_dir(output_dir=output_dir, args=args)


def _resolve_run_id(raw_value: str) -> str:
    run_id = raw_value.strip() or datetime.now().strftime("run-%Y%m%d-%H%M%S")
    safe_run_id = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in run_id).strip("-_")
    if not safe_run_id:
        safe_run_id = datetime.now().strftime("run-%Y%m%d-%H%M%S")
    return safe_run_id


def resolve_v2_clarified_context(
    args,
    *,
    brief_text: str,
    effective_command: str,
    parser: argparse.ArgumentParser,
) -> tuple[str, str, str, int | None, int | None, int | None, str]:
    if not args.topic.strip():
        return (
            "",
            brief_text,
            args.audience,
            args.chapters,
            args.min_slides,
            args.max_slides,
            args.theme.strip() or "business_red",
        )

    context = derive_planning_context(
        topic=args.topic,
        brief=brief_text,
        audience=args.audience,
        theme=args.theme.strip(),
        chapters=args.chapters,
        min_slides=args.min_slides,
        max_slides=args.max_slides,
        prefer_llm=True,
    )

    if context.requirements.template:
        parser.exit(
            status=1,
            message=(
                "V2 workflows do not support PPTX templates. "
                f"Requested template: {context.requirements.template}. "
                "Use --theme instead.\n"
            ),
        )

    if context.status == "needs_clarification" and not context.skipped:
        parser.exit(
            status=1,
            message=f"Clarification required before '{effective_command}':\n{context.message}\n",
        )

    return (
        context.topic,
        context.brief or brief_text,
        context.audience.strip() or DEFAULT_AUDIENCE_HINT,
        context.chapters,
        context.min_slides,
        context.max_slides,
        args.theme.strip() or context.requirements.theme or "business_red",
    )


def resolve_batch_clarified_context(
    args,
    *,
    topic: str,
    brief_text: str,
    audience: str,
) -> tuple[str, str, str, int | None, int | None, int | None, str, dict[str, object] | None]:
    fallback_topic = topic.strip()
    fallback_brief = brief_text
    fallback_audience = audience.strip() or DEFAULT_AUDIENCE_HINT
    fallback_theme = args.theme.strip() or "sie_consulting_fixed"
    if not fallback_topic:
        return (
            fallback_topic,
            fallback_brief,
            fallback_audience,
            args.chapters,
            args.min_slides,
            args.max_slides,
            fallback_theme,
            None,
        )

    try:
        context = derive_planning_context(
            topic=fallback_topic,
            brief=fallback_brief,
            audience=fallback_audience,
            theme=fallback_theme,
            chapters=args.chapters,
            min_slides=args.min_slides,
            max_slides=args.max_slides,
            model=args.llm_model or None,
            prefer_llm=True,
        )
    except Exception as exc:
        LOGGER.warning("batch clarify stage failed, falling back to raw input: %s", exc)
        return (
            fallback_topic,
            fallback_brief,
            fallback_audience,
            args.chapters,
            args.min_slides,
            args.max_slides,
            fallback_theme,
            {
                "status": "fallback_error",
                "message": str(exc),
                "topic": fallback_topic,
                "brief": fallback_brief,
                "audience": fallback_audience,
            },
        )

    clarify_payload = context.to_dict()
    resolved_topic = context.topic.strip() or fallback_topic
    resolved_brief = context.brief or fallback_brief
    resolved_audience = context.audience.strip() or fallback_audience
    resolved_theme = args.theme.strip() or context.requirements.theme or fallback_theme
    return (
        resolved_topic,
        resolved_brief,
        resolved_audience,
        context.chapters,
        context.min_slides,
        context.max_slides,
        resolved_theme,
        clarify_payload,
    )


def _allocate_rollback_run_id(*, base_run_id: str, output_root: Path) -> str:
    runs_root = output_root / "runs"
    candidate = f"{base_run_id}-rollback"
    if not (runs_root / candidate).exists():
        return candidate
    suffix = 2
    while True:
        candidate = f"{base_run_id}-rollback-{suffix:02d}"
        if not (runs_root / candidate).exists():
            return candidate
        suffix += 1


def _write_ai_five_stage_rollback_record(
    *,
    failed_result: dict[str, object],
    fallback_run_id: str,
    reason: str,
) -> None:
    workspace_obj = failed_result.get("workspace")
    run_dir = getattr(workspace_obj, "run_dir", None)
    if not isinstance(run_dir, Path):
        return
    final_dir = run_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    write_json_artifact(
        final_dir / "ai_five_stage_rollback.json",
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "failed_error": str(failed_result.get("error") or ""),
            "fallback_run_id": fallback_run_id,
        },
    )


def main():
    parser = build_main_parser()
    raw_argv = sys.argv[1:]
    args = parser.parse_args()
    validate_command_name(args.command, parser)
    validate_slide_args(args, parser)
    effective_command, explicit_command = resolve_effective_command(raw_argv, args)
    validate_v2_option_compatibility(raw_argv, effective_command=effective_command, parser=parser)
    validate_delivery_target_compatibility(
        args=args,
        explicit_command=explicit_command,
        effective_command=effective_command,
        parser=parser,
    )
    emit_command_notice(explicit_command, args.command, effective_command)

    # --- CLI AI overrides: patch env vars from --api-key / --base-url / --api-style ---
    _patched_keys: list[str] = []
    cli_api_key = getattr(args, "api_key", "").strip()
    cli_base_url = getattr(args, "base_url", "").strip()
    cli_api_style = getattr(args, "api_style", "").strip()
    cli_llm_mode = str(getattr(args, "llm_mode", "agent_first") or "agent_first").strip().lower()
    os.environ["SIE_AUTOPPT_LLM_MODE"] = cli_llm_mode
    if option_was_explicit(raw_argv, "--llm-mode"):
        _patched_keys.append("SIE_AUTOPPT_LLM_MODE")
    if cli_api_key:
        os.environ["OPENAI_API_KEY"] = cli_api_key
        _patched_keys.append("OPENAI_API_KEY")
    if cli_base_url:
        os.environ["OPENAI_BASE_URL"] = cli_base_url
        _patched_keys.append("OPENAI_BASE_URL")
    if cli_api_style:
        os.environ["SIE_AUTOPPT_LLM_API_STYLE"] = cli_api_style
        _patched_keys.append("SIE_AUTOPPT_LLM_API_STYLE")
    if _patched_keys:
        LOGGER.info("CLI AI overrides applied: %s", ", ".join(_patched_keys))
        print(f"[config] AI overrides from CLI: {', '.join(_patched_keys)}", file=sys.stderr)

    output_dir = Path(args.output_dir)
    brief_text = load_brief_text(args.brief, args.brief_file)
    v2_theme = args.theme.strip() or "business_red"
    v2_output_dir = DEFAULT_V2_OUTPUT_DIR if output_dir == DEFAULT_OUTPUT_DIR else output_dir
    v2_output_dir = resolve_v2_output_dir(output_dir=v2_output_dir, args=args)
    resolved_topic = args.topic.strip()
    resolved_brief = brief_text
    resolved_audience = args.audience
    resolved_chapters = args.chapters
    resolved_min_slides = args.min_slides
    resolved_max_slides = args.max_slides

    if effective_command in {"v2-outline", "v2-plan", "v2-make"} and args.topic.strip():
        (
            resolved_topic,
            resolved_brief,
            resolved_audience,
            resolved_chapters,
            resolved_min_slides,
            resolved_max_slides,
            v2_theme,
        ) = resolve_v2_clarified_context(
            args,
            brief_text=brief_text,
            effective_command=effective_command,
            parser=parser,
        )

    if handle_pre_v2_command(
        effective_command=effective_command,
        args=args,
        parser=parser,
        output_dir=output_dir,
        brief_text=brief_text,
        load_clarifier_session=load_clarifier_session,
        clarify_user_input=clarify_user_input,
        serve_clarifier_web=serve_clarifier_web,
        build_template_output_stem=build_template_output_stem,
        emit_progress=emit_progress,
        structure_spec_cls=StructureSpec,
        openai_configuration_error_cls=OpenAIConfigurationError,
        openai_responses_error_cls=OpenAIResponsesError,
        build_onepage_brief_from_structure=build_onepage_brief_from_structure,
        build_onepage_slide=build_onepage_slide,
        write_json_artifact=write_json_artifact,
        load_deck_spec=load_deck_spec,
        generate_visual_draft_artifacts=generate_visual_draft_artifacts,
        cli_execution_error_cls=CliExecutionError,
    ):
        return

    if effective_command == "batch-make":
        brief_file = str(args.brief_file or "").strip()
        if brief_file:
            try:
                validate_local_inputs(
                    [Path(brief_file)],
                    config=InputGuardConfig(
                        max_bytes=2 * 1024 * 1024,
                        allowed_suffixes={".txt", ".md", ".markdown"},
                    ),
                )
            except ValueError as exc:
                parser.error(f"{exc}\n")

        bundle_json = str(args.content_bundle_json or "").strip()
        if bundle_json:
            try:
                validate_local_inputs(
                    [Path(bundle_json)],
                    config=InputGuardConfig(max_bytes=10 * 1024 * 1024, allowed_suffixes={".json"}),
                )
            except ValueError as exc:
                parser.error(f"{exc}\n")

        raw_links = tuple(str(value).strip() for value in (args.link or []) if str(value).strip())
        for link in raw_links:
            try:
                validate_url(link)
            except ValueError as exc:
                parser.error(f"{exc}\n")

        image_paths = tuple(Path(value) for value in (args.image_file or []) if str(value).strip())
        if image_paths:
            try:
                validate_local_inputs(
                    list(image_paths),
                    config=InputGuardConfig(
                        max_bytes=10 * 1024 * 1024,
                        allowed_suffixes={".png", ".jpg", ".jpeg", ".webp", ".bmp"},
                    ),
                )
            except ValueError as exc:
                parser.error(f"{exc}\n")

        attachment_paths = tuple(Path(value) for value in (args.attachment_file or []) if str(value).strip())
        if attachment_paths:
            try:
                validate_local_inputs(
                    list(attachment_paths),
                    config=InputGuardConfig(
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
                    ),
                )
            except ValueError as exc:
                parser.error(f"{exc}\n")

        structured_data_json = str(args.structured_data_json or "").strip()
        structured_data_path: Path | None = None
        if structured_data_json:
            try:
                validated = validate_local_inputs(
                    [Path(structured_data_json)],
                    config=InputGuardConfig(max_bytes=10 * 1024 * 1024, allowed_suffixes={".json"}),
                )
            except ValueError as exc:
                parser.error(f"{exc}\n")
            structured_data_path = validated[0]

        if resolved_topic:
            try:
                validate_text_input(resolved_topic)
            except ValueError as exc:
                parser.error(f"{exc}\n")
        if resolved_brief:
            try:
                validate_text_input(resolved_brief)
            except ValueError as exc:
                parser.error(f"{exc}\n")

        try:
            resolved_bridge_root = resolve_bridge_root(
                config=BridgeConfig(pptmaster_root=str(args.pptmaster_root or "").strip())
            )
        except FileNotFoundError as exc:
            parser.error(f"{exc}\n")

        resolved_run_id = _resolve_run_id(str(args.run_id or ""))
        external_bundle: dict[str, object] | None = None
        if bundle_json:
            external_bundle = load_content_bundle_artifact(
                path=Path(bundle_json),
                run_id=resolved_run_id,
            )
        if not resolved_topic and external_bundle is None:
            parser.error("batch-make requires --topic or --content-bundle-json.")

        batch_clarify_result: dict[str, object] | None = None
        batch_chapters: int | None = args.chapters
        batch_min_slides: int | None = args.min_slides
        batch_max_slides: int | None = args.max_slides

        batch_topic = str(external_bundle["topic"]) if external_bundle is not None else resolved_topic
        batch_brief = str(external_bundle["text_summary"]["summary"]) if external_bundle is not None else resolved_brief
        batch_audience = (
            str(external_bundle["audience"])
            if external_bundle is not None
            else (resolved_audience.strip() or DEFAULT_AUDIENCE_HINT)
        )
        batch_language = str(external_bundle["language"]) if external_bundle is not None else args.language
        batch_theme = (
            str(external_bundle["theme"])
            if external_bundle is not None
            else (args.theme.strip() or "sie_consulting_fixed")
        )
        if external_bundle is None:
            (
                batch_topic,
                batch_brief,
                batch_audience,
                batch_chapters,
                batch_min_slides,
                batch_max_slides,
                batch_theme,
                batch_clarify_result,
            ) = resolve_batch_clarified_context(
                args,
                topic=batch_topic,
                brief_text=batch_brief,
                audience=batch_audience,
            )
        else:
            clarify_result = external_bundle.get("clarify_result")
            if isinstance(clarify_result, dict):
                batch_clarify_result = dict(clarify_result)
            else:
                batch_clarify_result = {
                    "status": "external_bundle",
                    "message": "clarify_result not provided in content bundle; synthesized fallback metadata.",
                    "topic": batch_topic,
                    "brief": batch_brief,
                    "audience": batch_audience,
                }
                external_bundle["clarify_result"] = dict(batch_clarify_result)

        batch_request = BatchMakeRequest(
            topic=batch_topic,
            brief=batch_brief,
            audience=batch_audience,
            language=batch_language,
            theme=batch_theme,
            output_root=output_dir,
            run_id=resolved_run_id,
            model=args.llm_model.strip() or None,
            chapters=batch_chapters,
            min_slides=batch_min_slides,
            max_slides=batch_max_slides,
            clarify_result=batch_clarify_result,
            semantic_candidate_count=max(1, int(getattr(args, "batch_size", 1))),
            links=raw_links,
            image_files=image_paths,
            attachment_files=attachment_paths,
            structured_data_file=structured_data_path,
        )
        rollout_decision = resolve_ai_five_stage_rollout(run_id=batch_request.run_id)
        emit_progress(bool(args.progress), "batch-make", f"run_id={batch_request.run_id}")
        batch_make_kwargs = {
            "request": batch_request,
            "preprocess_fn": (lambda **kwargs: dict(external_bundle))
            if external_bundle is not None
            else build_content_bundle,
            "bridge_fn": run_pptmaster_bridge,
            "tuning_fn": run_noop_tuning,
            "qa_fn": run_basic_qa,
            "bridge_root": resolved_bridge_root,
            "pre_export_qa_fn": run_pre_export_semantic_qa if rollout_decision.enabled else None,
        }
        if rollout_decision.enabled and args.with_ai_review:
            batch_make_kwargs["review_patch_fn"] = (
                lambda **callback_kwargs: run_batch_review_patch_once(
                    workspace=callback_kwargs["workspace"],
                    bundle=callback_kwargs["bundle"],
                    model=batch_request.model,
                    theme_name=batch_theme,
                )
            )
        result = run_batch_make(**batch_make_kwargs)
        if result["state"] != "SUCCEEDED" and rollout_decision.enabled and rollout_decision.auto_rollback:
            fallback_run_id = _allocate_rollback_run_id(base_run_id=batch_request.run_id, output_root=output_dir)
            print(
                f"[warn] batch-make five-stage failed; fallback to legacy pipeline with run_id={fallback_run_id}",
                file=sys.stderr,
            )
            emit_progress(
                bool(args.progress),
                "batch-make",
                f"five-stage failed; fallback to legacy pipeline with run_id={fallback_run_id}",
            )
            _write_ai_five_stage_rollback_record(
                failed_result=result,
                fallback_run_id=fallback_run_id,
                reason=rollout_decision.reason,
            )
            rollback_request = replace(batch_request, run_id=fallback_run_id)
            rollback_kwargs = dict(batch_make_kwargs)
            rollback_kwargs["request"] = rollback_request
            rollback_kwargs["pre_export_qa_fn"] = None
            rollback_kwargs.pop("review_patch_fn", None)
            result = run_batch_make(**rollback_kwargs)
        if result["state"] != "SUCCEEDED":
            parser.exit(status=1, message=f"batch-make failed: {result.get('error', 'unknown error')}\n")
        print(result["final_pptx"])
        return

    if handle_v2_and_health_command(
        effective_command=effective_command,
        args=args,
        parser=parser,
        context=V2CommandContext(
            resolved_topic=resolved_topic,
            resolved_brief=resolved_brief,
            resolved_audience=resolved_audience,
            resolved_chapters=resolved_chapters,
            resolved_min_slides=resolved_min_slides,
            resolved_max_slides=resolved_max_slides,
            v2_theme=v2_theme,
            v2_output_dir=v2_output_dir,
            brief_text=brief_text,
            emit_progress=emit_progress,
            default_outline_output_path=default_outline_output_path,
            default_semantic_output_path=default_semantic_output_path,
            default_deck_output_path=default_deck_output_path,
            default_log_output_path=default_log_output_path,
            default_ppt_output_path=default_ppt_output_path,
            load_outline_document=load_outline_document,
            write_outline_document=write_outline_document,
            write_semantic_document=write_semantic_document,
            write_deck_document=write_deck_document,
            load_deck_document=load_deck_document,
            compile_semantic_deck_payload=compile_semantic_deck_payload,
            generate_outline_with_ai=generate_outline_with_ai,
            generate_semantic_deck_with_ai=generate_semantic_deck_with_ai,
            generate_semantic_decks_with_ai_batch=generate_semantic_decks_with_ai_batch,
            ensure_generation_context=ensure_generation_context,
            make_v2_ppt=make_v2_ppt,
            generate_v2_ppt=generate_v2_ppt,
            apply_patch_set=apply_patch_set,
            review_deck_once=review_deck_once,
            iterate_visual_review=iterate_visual_review,
            run_ai_healthcheck=run_ai_healthcheck,
        ),
    ):
        return
    parser.error(f"unsupported command '{effective_command}'.")


if __name__ == "__main__":
    main()
