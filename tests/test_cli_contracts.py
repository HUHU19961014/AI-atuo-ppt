import json
from pathlib import Path

from tools.sie_autoppt import cli as cli_module


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_CONTRACTS_PATH = REPO_ROOT / "docs" / "CLI_CONTRACTS.json"
REQUIRED_FIELDS = {
    "command",
    "canonical_command",
    "primary_stage",
    "stage_chain",
    "input_schema",
    "output_schema",
    "ai_execution_mode",
    "requires_api_key",
    "fallback_mode",
    "retry_policy",
}
ALLOWED_STAGES = {
    "clarify",
    "outline",
    "semantic_deck",
    "quality_rewrite",
    "review_patch",
}
ALLOWED_AI_EXECUTION_MODES = {"agent_first", "runtime_api", "none"}


def _load_contract_commands() -> list[dict]:
    payload = json.loads(CLI_CONTRACTS_PATH.read_text(encoding="utf-8-sig"))
    assert isinstance(payload, dict)
    commands = payload.get("commands")
    assert isinstance(commands, list)
    assert commands
    return commands


def test_cli_contracts_file_exists():
    assert CLI_CONTRACTS_PATH.exists()


def test_cli_contracts_cover_all_workflow_commands():
    commands = _load_contract_commands()
    contract_commands = {entry["command"] for entry in commands}
    assert contract_commands == set(cli_module.WORKFLOW_COMMANDS)


def test_cli_contract_entries_have_required_fields_and_valid_values():
    commands = _load_contract_commands()

    for entry in commands:
        assert REQUIRED_FIELDS.issubset(entry.keys())
        assert entry["canonical_command"] in cli_module.WORKFLOW_COMMANDS
        assert entry["primary_stage"] in ALLOWED_STAGES
        assert isinstance(entry["stage_chain"], list)
        assert entry["stage_chain"]
        assert entry["primary_stage"] in entry["stage_chain"]
        assert set(entry["stage_chain"]).issubset(ALLOWED_STAGES)
        assert entry["ai_execution_mode"] in ALLOWED_AI_EXECUTION_MODES
        assert bool(str(entry["input_schema"]).strip())
        assert bool(str(entry["output_schema"]).strip())
        assert bool(str(entry["fallback_mode"]).strip())
        assert bool(str(entry["retry_policy"]).strip())

        requires_api_key = entry["requires_api_key"]
        assert isinstance(requires_api_key, dict)
        assert set(requires_api_key.keys()) == {"agent_first", "runtime_api", "none"}
        assert all(isinstance(value, bool) for value in requires_api_key.values())
        assert requires_api_key["none"] is False


def test_cli_contract_alias_entries_match_cli_alias_mappings():
    commands = _load_contract_commands()
    by_command = {entry["command"]: entry for entry in commands}

    for alias_name, canonical_name in cli_module.COMMAND_ALIASES.items():
        assert by_command[alias_name]["canonical_command"] == canonical_name


def test_readme_and_cli_reference_describe_agent_and_runtime_modes():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8").lower()
    cli_reference = (REPO_ROOT / "docs" / "CLI_REFERENCE.md").read_text(encoding="utf-8").lower()

    assert "--llm-mode" in readme
    assert "--llm-mode" in cli_reference
    assert "agent-first" in readme
    assert "runtime-api" in readme
    assert "agent-first" in cli_reference
    assert "runtime-api" in cli_reference


def test_cli_reference_mentions_all_workflow_commands():
    cli_reference = (REPO_ROOT / "docs" / "CLI_REFERENCE.md").read_text(encoding="utf-8")
    for command in cli_module.WORKFLOW_COMMANDS:
        assert command in cli_reference
