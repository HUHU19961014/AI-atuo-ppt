from pathlib import Path
import subprocess

from tools.sie_autoppt import cli as cli_module


REPO_ROOT = Path(__file__).resolve().parents[1]

DISALLOWED_TRACKED_PREFIXES = (
    ".tmp_ppt_master_research/",
    ".tmp_pytest_cache/",
    ".tmp_test_runtime/",
    ".tmp_test_workspace/",
    ".mypy_cache/",
    ".ruff_cache/",
    "__pycache__/",
    "output/runs/",
)


def _tracked_repo_paths() -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def test_testing_doc_does_not_reference_missing_scripts():
    testing_doc = (REPO_ROOT / "docs" / "TESTING.md").read_text(encoding="utf-8")
    assert "tools/check_legacy_boundary.py" not in testing_doc
    assert "tools/stress_test_v2.py" not in testing_doc


def test_cli_reference_mentions_batch_make():
    cli_doc = (REPO_ROOT / "docs" / "CLI_REFERENCE.md").read_text(encoding="utf-8")
    assert "batch-make" in cli_doc


def test_cli_reference_does_not_advertise_missing_main_commands():
    cli_doc = (REPO_ROOT / "docs" / "CLI_REFERENCE.md").read_text(encoding="utf-8")
    assert "| `svg-pipeline` |" not in cli_doc
    assert "| `svg-export` |" not in cli_doc
    assert "| `sie-render` |" not in cli_doc
    assert "main.py svg-pipeline" not in cli_doc
    assert "main.py svg-export" not in cli_doc


def test_readme_does_not_advertise_missing_main_commands():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    documented_missing = {"enterprise-ai-ppt svg-pipeline", "enterprise-ai-ppt svg-export"}
    for command in documented_missing:
        assert command not in readme


def test_docs_do_not_advertise_removed_cli_flags():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    cli_doc = (REPO_ROOT / "docs" / "CLI_REFERENCE.md").read_text(encoding="utf-8")
    testing_doc = (REPO_ROOT / "docs" / "TESTING.md").read_text(encoding="utf-8")
    llm_doc = (REPO_ROOT / "docs" / "LLM_COMPATIBILITY.md").read_text(encoding="utf-8")
    assert "--vision-provider" not in readme
    assert "--vision-provider" not in cli_doc
    assert "--graceful-timeout-fallback" not in testing_doc
    assert "SIE_AUTOPPT_REQUIRE_API_KEY" not in readme
    assert "SIE_AUTOPPT_REQUIRE_API_KEY" not in cli_doc
    assert "SIE_AUTOPPT_REQUIRE_API_KEY" not in llm_doc


def test_cli_reference_command_examples_use_real_main_commands():
    cli_doc = (REPO_ROOT / "docs" / "CLI_REFERENCE.md").read_text(encoding="utf-8")
    for command in cli_module.WORKFLOW_COMMANDS:
        if command == "make":
            assert "main.py make" in cli_doc
            break


def test_gitignore_covers_repo_temp_directories():
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".tmp_ppt_master_research/" in gitignore
    assert ".tmp_pytest_cache/" in gitignore
    assert ".tmp_test_runtime/" in gitignore
    assert ".tmp_test_workspace/" in gitignore
    assert ".mypy_cache/" in gitignore
    assert ".ruff_cache/" in gitignore
    assert "__pycache__/" in gitignore
    assert "output/runs/" in gitignore


def test_repo_does_not_track_temp_or_cache_artifacts():
    tracked = _tracked_repo_paths()
    unexpected = [path for path in tracked if path.startswith(DISALLOWED_TRACKED_PREFIXES)]
    assert unexpected == []


def test_architecture_doc_tracks_current_cli_surface():
    architecture_doc = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "batch-make" in architecture_doc
    assert "`sie-render`" not in architecture_doc
    assert "SIE Template Render Flow" not in architecture_doc


def test_testing_doc_tracks_current_entrypoints_only():
    testing_doc = (REPO_ROOT / "docs" / "TESTING.md").read_text(encoding="utf-8")
    assert "scripts\\quality_gate.ps1" in testing_doc
    assert "python -m pytest tests -q" in testing_doc
    assert "tools/run_unit_tests.ps1" not in testing_doc
    assert "tools/v2_regression_check.ps1" not in testing_doc
    assert "tools/legacy_html_regression_check.ps1" not in testing_doc
