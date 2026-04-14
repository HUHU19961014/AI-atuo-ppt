from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Sequence


def command_was_explicit(argv: list[str], workflow_commands: Sequence[str]) -> bool:
    for token in argv:
        if token.startswith("-"):
            continue
        return token in workflow_commands
    return False


def normalize_command_alias(command_name: str, command_aliases: dict[str, str]) -> str:
    return command_aliases.get(command_name, command_name)


def resolve_effective_command(
    argv: list[str],
    args,
    *,
    workflow_commands: Sequence[str],
    command_aliases: dict[str, str],
) -> tuple[str, bool]:
    explicit = command_was_explicit(argv, workflow_commands)
    normalized_command = normalize_command_alias(args.command, command_aliases)
    delivery_target = str(getattr(args, "delivery_target", "auto") or "auto").strip().lower()
    if explicit:
        if normalized_command == "make":
            return "v2-make", explicit
        return normalized_command, explicit
    if delivery_target == "sie-template":
        return "sie-render", explicit
    if delivery_target == "v2":
        return "v2-make", explicit
    if args.full_pipeline or normalized_command == "make":
        return "v2-make", explicit
    if args.topic.strip() or args.outline_json.strip():
        return "v2-make", explicit
    return normalized_command, explicit


def validate_command_name(
    command_name: str,
    parser,
    *,
    workflow_commands: Sequence[str],
    command_aliases: dict[str, str],
    primary_commands: Sequence[str],
    advanced_commands: Sequence[str],
) -> None:
    normalized = normalize_command_alias(command_name, command_aliases)
    if normalized in workflow_commands:
        return
    parser.error(
        "unknown command "
        f"'{command_name}'. Use one of the primary commands ({', '.join(primary_commands)}) "
        f"or advanced commands ({', '.join(advanced_commands)})."
    )


def emit_command_notice(explicit: bool, parsed_command: str, effective_command: str, command_aliases: dict[str, str]) -> str | None:
    if parsed_command in command_aliases:
        return f"INFO: '{parsed_command}' maps to '{effective_command}'."
    if effective_command == "v2-make" and parsed_command == "make":
        return "INFO: compatibility alias: 'make' routes to semantic v2-make; legacy template generation has been removed."
    return None


def option_was_explicit(argv: list[str], option_name: str) -> bool:
    return any(token == option_name or token.startswith(f"{option_name}=") for token in argv)


def is_v2_command(command_name: str) -> bool:
    return command_name.startswith("v2-")


def validate_v2_option_compatibility(argv: list[str], *, effective_command: str, parser) -> None:
    if not (is_v2_command(effective_command) or effective_command == "make"):
        return
    if option_was_explicit(argv, "--template"):
        parser.error(
            "--template is no longer supported. Use --theme with the V2 semantic workflow."
        )
    explicit_theme_values: list[str] = []
    for index, token in enumerate(argv):
        if token == "--theme" and index + 1 < len(argv):
            explicit_theme_values.append(str(argv[index + 1]).strip())
            continue
        if token.startswith("--theme="):
            explicit_theme_values.append(token.split("=", 1)[1].strip())
    if any(value and value != "sie_consulting_fixed" for value in explicit_theme_values):
        parser.error(
            "--theme is fixed to 'sie_consulting_fixed' for SIE consulting workflow."
        )


def validate_delivery_target_compatibility(*, args, explicit_command: bool, effective_command: str, parser) -> None:
    delivery_target = str(getattr(args, "delivery_target", "auto") or "auto").strip().lower()
    if explicit_command and args.command == "make" and delivery_target == "sie-template":
        parser.error("--delivery-target sie-template cannot be combined with explicit 'make'")
    if is_v2_command(effective_command) and delivery_target == "sie-template":
        parser.error("--delivery-target sie-template conflicts with V2 commands")
    if effective_command == "sie-render" and delivery_target == "v2":
        parser.error("--delivery-target v2 conflicts with SIE template commands")


def resolve_v2_output_dir(*, output_dir: Path, args) -> Path:
    if not bool(getattr(args, "isolate_output", False)):
        return output_dir
    raw_run_id = str(getattr(args, "run_id", "") or "").strip()
    run_id = raw_run_id or datetime.now().strftime("run-%Y%m%d-%H%M%S")
    safe_run_id = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in run_id).strip("-_")
    if not safe_run_id:
        safe_run_id = datetime.now().strftime("run-%Y%m%d-%H%M%S")
    return output_dir / "runs" / safe_run_id

